# Smoke test: memory HTTP daemon + (optional) sociality compose recall path.
# Reduces hand-work before mission-A human chat checks on :8090 / CLI.
#
# Usage:
#   .\scripts\test-memory-stack.ps1
#   .\scripts\test-memory-stack.ps1 -RequireSociality   # fail if :18901 down
#
# Prereqs:
#   memory-mcp-http-daemon on :18900 (.\scripts\run-memory-daemon.ps1 or logon task)
#   For compose leg: sociality-mcp listening on :18901 (Claude session or manual uv run)

param(
    [int]$MemoryPort = $(if ($env:MEMORY_HTTP_PORT) { [int]$env:MEMORY_HTTP_PORT } else { 18900 }),
    [int]$SocialityPort = $(if ($env:SOCIALITY_HTTP_PORT) { [int]$env:SOCIALITY_HTTP_PORT } else { 18901 }),
    [switch]$RequireSociality
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Label, [string]$Status, [string]$Detail = "") {
    $color = switch ($Status) {
        "PASS" { "Green" }
        "FAIL" { "Red" }
        "SKIP" { "DarkGray" }
        "WARN" { "Yellow" }
        default { "White" }
    }
    $line = "  [$Status] $Label"
    if ($Detail) { $line += " — $Detail" }
    Write-Host $line -ForegroundColor $color
}

function Invoke-HttpJson {
    param(
        [string]$Method = "GET",
        [string]$Url,
        [object]$Body = $null,
        [int]$TimeoutSec = 30
    )
    if ($Method -eq "GET") {
        return Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec $TimeoutSec
    }
    $json = if ($Body -is [string]) { $Body } else { $Body | ConvertTo-Json -Compress -Depth 6 }
    return Invoke-RestMethod -Uri $Url -Method Post -Body $json -ContentType "application/json; charset=utf-8" -TimeoutSec $TimeoutSec
}

Write-Host "== memory stack smoke test ==" -ForegroundColor Cyan
Write-Host "  memory :$MemoryPort  sociality :$SocialityPort"

$failed = 0
# Unique fact per run — avoid top-N collision with older "青い傘 backlog-smoke-*" entries.
$marker = "stack-smoke-$(Get-Date -Format 'yyyyMMdd-HHmmss-fff')"
$fact = "[$marker] 琥珀色の傘を持って駅の改札前で待ち合わせしていた"
$query = "琥珀色 傘 改札 待ち合わせ"

# 1. memory /health
try {
    $health = Invoke-HttpJson -Url "http://127.0.0.1:$MemoryPort/health" -TimeoutSec 3
    if ($health.ok) {
        Write-Step "memory /health" "PASS" "ready=$($health.ready)"
    } else {
        Write-Step "memory /health" "FAIL" "ok=false"
        $failed++
    }
} catch {
    Write-Step "memory /health" "FAIL" $_.Exception.Message
    Write-Host "  Hint: .\scripts\run-memory-daemon.ps1 or install-memory-daemon-task.ps1" -ForegroundColor DarkGray
    exit 1
}

# 2. remember
try {
    $remember = Invoke-HttpJson -Method POST -Url "http://127.0.0.1:$MemoryPort/remember" -Body @{
        content    = $fact
        category   = "daily"
        emotion    = "neutral"
        importance = 3
        auto_link  = $false
    } -TimeoutSec 45
    if ($remember.ok) {
        Write-Step "memory POST /remember" "PASS" "id=$($remember.id)"
    } else {
        Write-Step "memory POST /remember" "FAIL" ($remember.error | Out-String)
        $failed++
    }
} catch {
    Write-Step "memory POST /remember" "FAIL" $_.Exception.Message
    $failed++
}

# 3. recall (paraphrase) — retry for E5 embed lag after remember
$recallPassed = $false
try {
    $q = [uri]::EscapeDataString($query)
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        if ($attempt -gt 1) { Start-Sleep -Seconds 2 }
        $recall = Invoke-HttpJson -Url "http://127.0.0.1:$MemoryPort/recall?q=$q&n=15" -TimeoutSec 45
        $hit = $false
        if ($recall -is [array]) {
            foreach ($item in $recall) {
                if ($item.content -like "*$marker*") { $hit = $true; break }
            }
        }
        if ($hit) {
            $detail = if ($attempt -gt 1) { "marker in top results (attempt $attempt)" } else { "marker in top results" }
            Write-Step "memory GET /recall" "PASS" $detail
            $recallPassed = $true
            break
        }
    }
    if (-not $recallPassed) {
        Write-Step "memory GET /recall" "FAIL" "marker not in recall results after 3 attempts"
        $failed++
    }
} catch {
    Write-Step "memory GET /recall" "FAIL" $_.Exception.Message
    $failed++
}

# 4. sociality /interaction_context (same compose path as :8090 gateway)
$socialityUp = $false
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:$SocialityPort/ingest?text=healthcheck&person_id=ma" -TimeoutSec 2 -UseBasicParsing | Out-Null
    $socialityUp = $true
} catch {
    $socialityUp = $false
}

if (-not $socialityUp) {
    if ($RequireSociality) {
        Write-Step "sociality compose" "FAIL" "port $SocialityPort not reachable"
        $failed++
    } else {
        Write-Step "sociality compose" "SKIP" "start Claude (sociality-mcp) or uv run sociality-mcp"
    }
} else {
    try {
        $tq = [uri]::EscapeDataString($query)
        $ctx = Invoke-HttpJson -Url "http://127.0.0.1:$SocialityPort/interaction_context?person_id=ma&channel=chat&text=$tq&max_chars=8000" -TimeoutSec 45
        $memTexts = @($ctx.relevant_memories | ForEach-Object { $_.content })
        $composeHit = $false
        foreach ($t in $memTexts) {
            if ($t -like "*$marker*") { $composeHit = $true; break }
        }
        if ($composeHit) {
            Write-Step "sociality GET /interaction_context" "PASS" "marker in relevant_memories"
        } else {
            Write-Step "sociality GET /interaction_context" "FAIL" "marker not in relevant_memories ($($memTexts.Count) hits)"
            $failed++
        }
    } catch {
        $detail = $_.Exception.Message
        if ($_.ErrorDetails.Message) {
            try {
                $errJson = $_.ErrorDetails.Message | ConvertFrom-Json
                if ($errJson.error) { $detail = $errJson.error }
            } catch { }
        }
        Write-Step "sociality GET /interaction_context" "FAIL" $detail
        $failed++
    }
}

Write-Host ""
if ($failed -eq 0) {
    Write-Host "All automated checks passed." -ForegroundColor Green
    Write-Host "Human leg (optional): one chat on :8090 or CLI — paraphrase the marker and confirm Koyori mentions it." -ForegroundColor DarkGray
    exit 0
}

Write-Host "$failed check(s) failed. See .\scripts\check-mcp-processes.ps1" -ForegroundColor Red
exit 1
