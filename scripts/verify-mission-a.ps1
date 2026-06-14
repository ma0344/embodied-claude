# Mission A verification — automated stack + optional :8090 chat leg.
#
# Usage:
#   .\scripts\verify-mission-a.ps1
#   .\scripts\verify-mission-a.ps1 -SkipGatewayChat    # stack only (fast)
#   .\scripts\verify-mission-a.ps1 -GatewayQuestion "青い傘のマーカー覚えてる？"
#
# Human leg (when automated passes):
#   :8090/ or CLI — paraphrase a known memory; Koyori should mention it without hanging.

param(
    [switch]$SkipGatewayChat,
    [string]$GatewayQuestion = "昨日の煎餅の話、覚えてる？",
    [string]$ProjectPath = "C:/Users/ma/src/embodied-claude",
    [string]$SessionId = "",
    [int]$GatewayTimeoutSec = 120
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
Set-Location $Repo

Write-Host "== Mission A verify ==" -ForegroundColor Cyan
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
Write-Host "Step 3/3: :8090 gateway chat (needs LM Studio + :8080)" -ForegroundColor Yellow

if (-not $SessionId) {
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
        Write-Host "  [WARN] could not list sessions: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$verifyPy = Join-Path $env:TEMP "verify_mission_a_gateway.py"
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

$kw = "煎餅,お煎餅,甘い"
python $verifyPy $GatewayQuestion $SessionId $ProjectPath $GatewayTimeoutSec $kw
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
