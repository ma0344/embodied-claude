# Start Koyori's Room Presence UI (FastAPI gateway on port 8090 by default).
#
# Default: background — terminal returns immediately (hidden process + log file).
# Debug:     .\scripts\run-presence-ui.ps1 -Foreground
#
# Requires claude-code-webui on :8080 (brain). This script is the window (:8090).
#
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\run-presence-ui.ps1

param(
    [switch]$Foreground,
    [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
    [string]$BackendPort = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
    [string]$TaskName = "EmbodiedClaude-PresenceUI"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$PresenceDir = Join-Path $Repo "presence-ui"
$Worker = Join-Path $PSScriptRoot "run-presence-ui-worker.ps1"
$Daemon = Join-Path $PSScriptRoot "run-presence-ui-daemon.ps1"

. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")

if (-not (Test-Path $PresenceDir)) {
    Write-Error "Missing $PresenceDir"
}

function Test-PortListen {
    param([string]$LocalPort)
    return (Get-PresenceUiPortListeners -Port $LocalPort).Count -gt 0
}

$PresenceUrl = Get-PresenceUiUrl -Port $Port
$LogFile = Get-PresenceUiLogFile

Write-Host "==> presence-ui (window)  $PresenceUrl"

if (-not (Test-PortListen $BackendPort)) {
    Write-Warning @"
Claude Code backend (:$BackendPort) is not listening.
Start it first:
  .\scripts\run-webui-ma-home.ps1
"@
}

$Listeners = Get-PresenceUiPortListeners -Port $Port
if ($Listeners.Count -gt 0) {
    $OwnerPid = $Listeners[0].OwningProcess
    $Proc = Get-Process -Id $OwnerPid -ErrorAction SilentlyContinue
    $ProcLabel = if ($Proc) { "$($Proc.ProcessName) (PID $OwnerPid)" } else { "PID $OwnerPid" }
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "Port $Port is already in use by $ProcLabel."
    if ($Task -and $Task.State -eq "Running") {
        Write-Host "Scheduled task $TaskName is running — presence-ui is already up."
    } else {
        Write-Host "Another presence-ui (or process) is already listening."
    }
    Write-Host ""
    Write-Host "Open:   $PresenceUrl"
    Write-Host "Log:    $LogFile"
    Write-Host ""
    Write-Host "To restart:"
    Write-Host "  .\scripts\restart-presence-ui.ps1"
    exit 0
}

Initialize-PresenceUiEnv -Repo $Repo -Port $Port -BackendPort $BackendPort

if ($Foreground) {
    Write-Host "    Claude Code (brain)   $env:CLAUDE_CODE_BACKEND_URL"
    Write-Host "    mode: foreground (Ctrl+C to stop)"
    Write-Host ""
    & $Worker -Port $Port -BackendPort $BackendPort
    exit $LASTEXITCODE
}

$Shell = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $Shell) {
    $Shell = Get-Command powershell -ErrorAction SilentlyContinue
}
if (-not $Shell) {
    Write-Error "PowerShell not found"
}

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Start-ScheduledTask -TaskName $TaskName
    $Listener = Wait-PresenceUiPortReady -Port $Port -TimeoutSeconds 30
    if (-not $Listener) {
        Write-Warning "Task started but port $Port did not open within 30s. Check log:"
        Write-Host "    $LogFile"
        exit 1
    }
    $OwnerPid = $Listener.OwningProcess
    $Proc = Get-Process -Id $OwnerPid -ErrorAction SilentlyContinue
    $ProcLabel = if ($Proc) { "$($Proc.ProcessName) (PID $OwnerPid)" } else { "PID $OwnerPid" }
    Write-Host "    started via $TaskName ($ProcLabel)"
} else {
    $Argument = @(
        "-NoProfile"
        "-ExecutionPolicy", "Bypass"
        "-WindowStyle", "Hidden"
        "-File", "`"$Daemon`""
        "-Port", $Port
        "-BackendPort", $BackendPort
    ) -join " "

    Start-Process -FilePath $Shell.Source -ArgumentList $Argument -WorkingDirectory $Repo -WindowStyle Hidden | Out-Null

    $Listener = Wait-PresenceUiPortReady -Port $Port -TimeoutSeconds 45
    if (-not $Listener) {
        Write-Warning "Background start failed — port $Port did not open within 45s."
        Write-Host "    log: $LogFile"
        Write-Host "    try: .\scripts\run-presence-ui.ps1 -Foreground"
        exit 1
    }
    $OwnerPid = $Listener.OwningProcess
    $Proc = Get-Process -Id $OwnerPid -ErrorAction SilentlyContinue
    $ProcLabel = if ($Proc) { "$($Proc.ProcessName) (PID $OwnerPid)" } else { "PID $OwnerPid" }
    Write-Host "    started in background ($ProcLabel)"
}

Write-Host "    Claude Code (brain)   $env:CLAUDE_CODE_BACKEND_URL"
Write-Host ""
Write-Host "Open:   $PresenceUrl"
Write-Host "Log:    $LogFile"
Write-Host ""
Write-Host "Stop:       .\scripts\stop-presence-ui.ps1"
Write-Host "Restart:    .\scripts\restart-presence-ui.ps1"
Write-Host "Foreground: .\scripts\run-presence-ui.ps1 -Foreground"
Write-Host "Install @ logon: .\scripts\install-presence-ui-task.ps1"
