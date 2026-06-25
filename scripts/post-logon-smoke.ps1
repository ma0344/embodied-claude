# B1b: post-logon / post-reboot smoke for ma-home embodied stack.
#
# Verifies logon Scheduled Tasks (memory / webui / presence / watchdog).
# Does NOT require sociality :18901 — that starts when Claude Code spawns MCPs.
#
# Native chat (PRESENCE_NATIVE_CHAT=1): :8080 / EmbodiedClaude-WebUI are OPTIONAL.
# Legacy proxy mode: use -RequireWebUI to enforce :8080.
#
# Run after Windows logon:
#   .\scripts\post-logon-smoke.ps1
#   .\scripts\post-logon-smoke.ps1 -RequireWebUI   # legacy stack
#
# Full stack (incl. compose): start Claude, then verify-mission-a.ps1

param(
    [switch]$RequireWebUI
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
Set-Location $Repo

. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")
Initialize-PresenceUiEnv -Repo $Repo
$nativeChat = Test-PresenceNativeChatEnabled -QueryUiConfig
$webuiOptional = $nativeChat -and -not $RequireWebUI

$failures = @()

function Test-PortListening([int]$Port) {
    return $null -ne (
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    )
}

# Hidden VBS launchers exit quickly (Task → Ready) while the daemon keeps listening.
$daemonTaskPorts = @{
    "EmbodiedClaude-MemoryHTTP" = 18900
    "EmbodiedClaude-PresenceUI" = 8090
    "EmbodiedClaude-AivisTTS"    = 10101
}

function Test-TaskRunning([string]$Name) {
    $t = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if (-not $t) { return "missing" }
    if ($t.State -eq "Running") { return "running" }
    $info = Get-ScheduledTaskInfo -TaskName $Name
    return "state=$($t.State) last=$($info.LastRunTime)"
}

Write-Host "== B1b post-logon smoke ==" -ForegroundColor Cyan
if ($webuiOptional) {
    Write-Host "mode: Native chat — :8080 webui optional (use -RequireWebUI to enforce)" -ForegroundColor DarkGray
} elseif ($RequireWebUI) {
    Write-Host "mode: legacy — :8080 webui required" -ForegroundColor DarkGray
}

Write-Host "`n-- Scheduled tasks --" -ForegroundColor Yellow
$taskNames = @(
    "EmbodiedClaude-MemoryHTTP",
    "EmbodiedClaude-AivisTTS",
    "EmbodiedClaude-WebUI",
    "EmbodiedClaude-PresenceUI",
    "EmbodiedClaude-Watchdog"
)
foreach ($name in $taskNames) {
    $status = Test-TaskRunning $name
    $isWatchdog = ($name -eq "EmbodiedClaude-Watchdog")
    $isWebui = ($name -eq "EmbodiedClaude-WebUI")
    $daemonPort = $daemonTaskPorts[$name]
    $daemonPortUp = $daemonPort -and (Test-PortListening $daemonPort)
    $ok = ($status -eq "running") -or (
        $isWatchdog -and $status -match "^state=Ready"
    ) -or (
        $daemonPort -and $daemonPortUp -and $status -match "^state=Ready"
    )
    if ($isWebui -and $webuiOptional -and $status -ne "running") {
        Write-Host "  $name : $status (optional — Native chat)" -ForegroundColor DarkGray
        continue
    }
    if ($name -eq "EmbodiedClaude-AivisTTS" -and $status -eq "missing") {
        Write-Host "  $name : missing (recommended — kiosk TTS)" -ForegroundColor Yellow
        continue
    }
    if ($daemonPort -and $daemonPortUp -and $status -match "^state=Ready") {
        Write-Host "  $name : $status (daemon up :$daemonPort)" -ForegroundColor Green
    } else {
        $color = if ($ok) { "Green" } else { "Yellow" }
        Write-Host "  $name : $status" -ForegroundColor $color
    }
    if ($status -eq "missing") {
        if ($isWebui -and $webuiOptional) { continue }
        $failures += "task $name missing"
    } elseif (-not $ok -and -not $isWatchdog) {
        if ($isWebui -and $webuiOptional) { continue }
        $failures += "task $name not running ($status)"
    }
}

Write-Host "`n-- Ports --" -ForegroundColor Yellow
$portChecks = @(
    @{ Port = 18900; Label = "memory HTTP"; Optional = $false },
    @{ Port = 10101; Label = "Aivis TTS"; Optional = $false },
    @{ Port = 8080; Label = "webui"; Optional = $webuiOptional },
    @{ Port = 8090; Label = "presence-ui"; Optional = $false }
)
foreach ($entry in $portChecks) {
    $listen = Get-NetTCPConnection -LocalPort $entry.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listen) {
        Write-Host "  $($entry.Label) :$($entry.Port) LISTEN pid=$($listen.OwningProcess)" -ForegroundColor Green
    } elseif ($entry.Optional) {
        Write-Host "  $($entry.Label) :$($entry.Port) not listening (optional — Native chat)" -ForegroundColor DarkGray
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
    $nativeFlag = if ($h.details.native_chat) { " native_chat=1" } else { "" }
    $ttsFlag = if ($null -ne $h.details.surface_tts_ready) {
        if ($h.details.surface_tts_ready) { " surface_tts=ready" } else { " surface_tts=DOWN" }
    } else { "" }
    $color = if ($h.status -eq "ok") { "Green" } else { "Yellow" }
    Write-Host "  :8090 $($h.details.mode)$nativeFlag$ttsFlag status=$($h.status)" -ForegroundColor $color
    if ($h.details.surface_tts_ready -eq $false) {
        $failures += "surface TTS not ready ($($h.details.surface_tts_status))"
    }
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
