# B1b: post-logon / post-reboot smoke for ma-home embodied stack.
#
# Verifies logon Scheduled Tasks (memory / webui / presence / watchdog).
# Does NOT require sociality :18901 — that starts when Claude Code spawns MCPs.
#
# Run after Windows logon:
#   .\scripts\post-logon-smoke.ps1
#
# Full stack (incl. compose): start Claude, then verify-mission-a.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
Set-Location $Repo

$failures = @()

function Test-TaskRunning([string]$Name) {
    $t = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if (-not $t) { return "missing" }
    if ($t.State -eq "Running") { return "running" }
    $info = Get-ScheduledTaskInfo -TaskName $Name
    return "state=$($t.State) last=$($info.LastRunTime)"
}

Write-Host "== B1b post-logon smoke ==" -ForegroundColor Cyan

Write-Host "`n-- Scheduled tasks --" -ForegroundColor Yellow
foreach ($name in @(
        "EmbodiedClaude-MemoryHTTP",
        "EmbodiedClaude-WebUI",
        "EmbodiedClaude-PresenceUI",
        "EmbodiedClaude-Watchdog"
    )) {
    $status = Test-TaskRunning $name
    $ok = ($status -eq "running") -or ($name -eq "EmbodiedClaude-Watchdog" -and $status -match "^state=Ready")
    $color = if ($ok) { "Green" } else { "Yellow" }
    Write-Host "  $name : $status" -ForegroundColor $color
    if ($status -eq "missing") { $failures += "task $name missing" }
    elseif (-not $ok -and $name -ne "EmbodiedClaude-Watchdog") { $failures += "task $name not running ($status)" }
}

Write-Host "`n-- Ports --" -ForegroundColor Yellow
foreach ($entry in @(
        @{ Port = 18900; Label = "memory HTTP" },
        @{ Port = 8080; Label = "webui" },
        @{ Port = 8090; Label = "presence-ui" }
    )) {
    $listen = Get-NetTCPConnection -LocalPort $entry.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listen) {
        Write-Host "  $($entry.Label) :$($entry.Port) LISTEN pid=$($listen.OwningProcess)" -ForegroundColor Green
    } else {
        Write-Host "  $($entry.Label) :$($entry.Port) NOT listening" -ForegroundColor Red
        $failures += "$($entry.Label) port $($entry.Port) down"
    }
}

Write-Host "`n-- memory HTTP (daemon) --" -ForegroundColor Yellow
& (Join-Path $PSScriptRoot "test-memory-stack.ps1")
if ($LASTEXITCODE -ne 0) { $failures += "memory stack failed ($LASTEXITCODE)" }

Write-Host "`n-- sociality :18901 (optional at logon) --" -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:18901/ingest?text=healthcheck&person_id=ma" -TimeoutSec 2 -UseBasicParsing | Out-Null
    Write-Host "  :18901 reachable (Claude or manual sociality-mcp)" -ForegroundColor Green
} catch {
    Write-Host "  :18901 not up — normal until Claude Code starts (8090 compose uses in-process path)" -ForegroundColor DarkGray
}

Write-Host "`n-- presence health --" -ForegroundColor Yellow
try {
    $h = Invoke-RestMethod http://localhost:8090/api/v1/health -TimeoutSec 5
    Write-Host "  :8090 $($h.details.mode) ok" -ForegroundColor Green
} catch {
    Write-Host "  :8090 FAIL $($_.Exception.Message)" -ForegroundColor Red
    $failures += "8090 health fail"
}

Write-Host ""
if ($failures.Count -eq 0) {
    Write-Host "B1b smoke: PASS" -ForegroundColor Green
    exit 0
}

Write-Host "B1b smoke: FAIL" -ForegroundColor Red
$failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
exit 1
