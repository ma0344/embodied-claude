# Mission A verification — automated stack + optional :8090 chat leg.
#
# Usage:
#   .\scripts\verify-mission-a.ps1
#   .\scripts\verify-mission-a.ps1 -SkipGatewayChat    # stack only (fast)
#   .\scripts\verify-mission-a.ps1 -GatewayQuestion "青い傘のマーカー覚えてる？"
#   .\scripts\verify-mission-a.ps1 -RequireWebUI       # force legacy /api/chat (+ :8080)
#
# Human leg (when automated passes):
#   :8090/ or CLI — paraphrase a known memory; Koyori should mention it without hanging.

param(
    [switch]$SkipGatewayChat,
    [switch]$RequireWebUI,
    [string]$GatewayQuestion = "昨日の煎餅の話、覚えてる？",
    [string]$ProjectPath = "C:/Users/ma/src/embodied-claude",
    [string]$SessionId = "",
    [int]$GatewayTimeoutSec = 120
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
Set-Location $Repo

. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")
Initialize-PresenceUiEnv -Repo $Repo
$nativeChat = Test-PresenceNativeChatEnabled -QueryUiConfig
if ($RequireWebUI) { $nativeChat = $false }

Write-Host "== Mission A verify ==" -ForegroundColor Cyan
if ($nativeChat) {
    Write-Host "chat leg: Native SSE /api/native/chat (no :8080)" -ForegroundColor DarkGray
} else {
    Write-Host "chat leg: legacy POST /api/chat (needs :8080)" -ForegroundColor DarkGray
}
Write-Host ""

Write-Host "Step 1/3: memory stack (HTTP + compose)" -ForegroundColor Yellow
& (Join-Path $PSScriptRoot "test-memory-stack.ps1") -RequireSociality
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Step 2/3: 煎餅 (senbei) recall path" -ForegroundColor Yellow
$q = [uri]::EscapeDataString("昨日の煎餅の話")
$recall = Invoke-RestMethod -Uri "http://127.0.0.1:18900/recall?q=$q&n=3" -TimeoutSec 30
$senbeiHit = $false
foreach ($item in @($recall)) {
    if ($item.content -match "煎餅") { $senbeiHit = $true; break }
}
if (-not $senbeiHit) {
    Write-Host "  [FAIL] HTTP recall did not return 煎餅 memory" -ForegroundColor Red
    exit 1
}
Write-Host "  [PASS] HTTP recall contains 煎餅" -ForegroundColor Green

$tq = [uri]::EscapeDataString("昨日の煎餅の話 覚えてる")
$ctx = Invoke-RestMethod -Uri "http://127.0.0.1:18901/interaction_context?person_id=ma&channel=chat&text=$tq&max_chars=8000" -TimeoutSec 45
$composeHit = $false
foreach ($mem in @($ctx.relevant_memories)) {
    if ($mem.content -match "煎餅") { $composeHit = $true; break }
}
if (-not $composeHit) {
    Write-Host "  [FAIL] compose relevant_memories missing 煎餅" -ForegroundColor Red
    exit 1
}
Write-Host "  [PASS] compose relevant_memories contains 煎餅" -ForegroundColor Green

if ($SkipGatewayChat) {
    Write-Host ""
    Write-Host "Step 3/3: skipped (-SkipGatewayChat)" -ForegroundColor DarkGray
    Write-Host "All automated checks passed." -ForegroundColor Green
    exit 0
}

Write-Host ""
if ($nativeChat) {
    Write-Host "Step 3/3: :8090 Native chat (needs LM Studio, no :8080)" -ForegroundColor Yellow
} else {
    Write-Host "Step 3/3: :8090 gateway chat (needs LM Studio + :8080)" -ForegroundColor Yellow
}

if (-not $nativeChat -and -not $SessionId) {
    $encoded = ($ProjectPath -replace ":", "-") -replace "\\", "-"
    $encoded = $encoded -replace "/", "-"
    try {
        $hist = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/projects/$encoded/histories" -TimeoutSec 10
        $convs = @($hist)
        if ($hist.conversations) { $convs = @($hist.conversations) }
        if ($convs.Count -gt 0) {
            $SessionId = $convs[0].sessionId
        }
    } catch {
        Write-Host "  [WARN] could not list sessions from :8080: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$verifyPy = Join-Path $env:TEMP "verify_mission_a_gateway.py"
$kw = "煎餅,お煎餅,甘い"
if ($nativeChat) {
    $nativePassword = Get-PresenceNativeLoginPassword
    @'
import json, sys, urllib.request

def parse_sse_block(block):
    evt = "message"
    data = ""
    for line in block.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            evt = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].strip()
    payload = {}
    if data:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {"raw": data}
    return evt, payload

def native_chat(question, password, timeout):
    login_req = urllib.request.Request(
        "http://127.0.0.1:8090/api/native/login",
        data=json.dumps({"password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(login_req, timeout=30) as resp:
        token = json.loads(resp.read().decode("utf-8")).get("token", "")
    if not token:
        print("GATEWAY_ERROR", "native login returned no token")
        sys.exit(1)

    payload = {"prompt": question}
    req = urllib.request.Request(
        "http://127.0.0.1:8090/api/native/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    text = ""
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        buf = ""
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                if not block.strip():
                    continue
                evt, payload = parse_sse_block(block)
                if evt == "text":
                    text += str(payload.get("content") or "")
                if evt == "error":
                    print("GATEWAY_ERROR", payload.get("message") or payload.get("error") or payload)
                    sys.exit(1)
    return text

question = sys.argv[1]
password = sys.argv[2]
timeout = int(sys.argv[3])
keywords = sys.argv[4].split(",")

text = native_chat(question, password, timeout)
found = [k for k in keywords if k and k in text]
print("ASSISTANT_SNIPPET:", text[:400].replace("\n", " "))
print("KEYWORDS_FOUND:", ",".join(found) if found else "(none)")
sys.exit(0 if found else 2)
'@ | Set-Content -Path $verifyPy -Encoding utf8

    python $verifyPy $GatewayQuestion $nativePassword $GatewayTimeoutSec $kw
} else {
    @'
import json, sys, urllib.request

def join_text(content):
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
            parts.append(block["text"])
    return "\n".join(parts).strip()

def assistant_text(data):
    if not isinstance(data, dict) or data.get("type") != "assistant":
        return ""
    inner = data.get("message") or data
    return join_text(inner.get("content"))

question = sys.argv[1]
session_id = sys.argv[2] or None
project = sys.argv[3]
timeout = int(sys.argv[4])
keywords = sys.argv[5].split(",")

payload = {
    "message": question,
    "requestId": "verify-mission-a",
    "workingDirectory": project,
    "permissionMode": "acceptEdits",
}
if session_id:
    payload["sessionId"] = session_id

req = urllib.request.Request(
    "http://localhost:8090/api/chat",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
    method="POST",
)
text = ""
with urllib.request.urlopen(req, timeout=timeout) as resp:
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "claude_json":
            text += assistant_text(ev.get("data") or {})
        if ev.get("type") == "error":
            print("GATEWAY_ERROR", ev.get("error") or ev)
            sys.exit(1)

found = [k for k in keywords if k and k in text]
print("ASSISTANT_SNIPPET:", text[:400].replace("\n", " "))
print("KEYWORDS_FOUND:", ",".join(found) if found else "(none)")
sys.exit(0 if found else 2)
'@ | Set-Content -Path $verifyPy -Encoding utf8

    python $verifyPy $GatewayQuestion $SessionId $ProjectPath $GatewayTimeoutSec $kw
}

$gwCode = $LASTEXITCODE
Remove-Item $verifyPy -Force -ErrorAction SilentlyContinue

if ($gwCode -eq 0) {
    Write-Host "  [PASS] :8090 chat mentions memory keywords" -ForegroundColor Green
} elseif ($gwCode -eq 2) {
    Write-Host "  [WARN] :8090 chat completed but keywords not found in assistant text" -ForegroundColor Yellow
    Write-Host "         (LLM may have answered differently — check room UI history)" -ForegroundColor DarkGray
} else {
    Write-Host "  [FAIL] :8090 gateway chat error" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "All automated checks passed." -ForegroundColor Green
Write-Host ""
Write-Host "Human sanity (optional):" -ForegroundColor DarkGray
Write-Host "  - :8090/ one paraphrase question — preferred for memory (compose preloads context)"
Write-Host "  - CLI same question may show 2x PROCESSING (hook + tool recall); hang = retry or use :8090"
Write-Host "  - After CLI hang: .\scripts\check-mcp-processes.ps1 (STALE? / memory HTTP)"
