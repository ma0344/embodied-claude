# Restart claude-code-webui on ma-home after settings / script changes.
#
# Default: stop then re-start the logon Scheduled Task (daemon, auto-recover).
# Foreground: stop then run in this terminal (debug).
#
# Usage:
#   .\scripts\restart-webui-ma-home.ps1
#   .\scripts\restart-webui-ma-home.ps1 -Foreground
#   .\scripts\stop-webui-ma-home.ps1          # stop only

param(
    [switch]$Foreground,
    [string]$Port = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
    [string]$HostBind = $(if ($env:WEBUI_HOST) { $env:WEBUI_HOST } else { "0.0.0.0" }),
    [string]$TaskName = "EmbodiedClaude-WebUI",
    [string]$ClaudePath = $(if ($env:CLAUDE_EXE_PATH) { $env:CLAUDE_EXE_PATH } else { "" })
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "webui-ma-home-lib.ps1")

Write-Host "==> restart-webui-ma-home"

$Stopped = Stop-WebuiMaHome -Port $Port -TaskName $TaskName
if ($Stopped.Count -eq 0) {
    Write-Host "    was not running"
} else {
    foreach ($Line in $Stopped) {
        Write-Host "    stopped $Line"
    }
}

$ProjectUrl = Get-WebuiProjectUrl -Repo $Repo -Port $Port

if ($Foreground) {
    Write-Host "    starting foreground (Ctrl+C to stop)"
    Write-Host "    open:   $ProjectUrl"
    Write-Host ""
    & (Join-Path $PSScriptRoot "run-webui-ma-home.ps1") -Port $Port -HostBind $HostBind -ClaudePath $ClaudePath
    exit $LASTEXITCODE
}

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $Task) {
    Write-Warning "Scheduled task '$TaskName' is not installed. Starting foreground instead."
    Write-Host "    install: .\scripts\install-webui-task.ps1"
    Write-Host ""
    & (Join-Path $PSScriptRoot "run-webui-ma-home.ps1") -Port $Port -HostBind $HostBind -ClaudePath $ClaudePath
    exit $LASTEXITCODE
}

Start-ScheduledTask -TaskName $TaskName

$Listener = Wait-WebuiPortReady -Port $Port -TimeoutSeconds 30
if (-not $Listener) {
    Write-Warning "Task started but port $Port did not open within 30s. Check log:"
    Write-Host "    $env:USERPROFILE\.config\embodied-claude\logs\webui.log"
    exit 1
}

$OwnerPid = $Listener.OwningProcess
$Proc = Get-Process -Id $OwnerPid -ErrorAction SilentlyContinue
$ProcLabel = if ($Proc) { "$($Proc.ProcessName) (PID $OwnerPid)" } else { "PID $OwnerPid" }

Write-Host "    started via $TaskName ($ProcLabel)"
Write-Host "    open:   $ProjectUrl"
Write-Host "    log:    $env:USERPROFILE\.config\embodied-claude\logs\webui.log"
Write-Host ""
Write-Host "Stop only:  .\scripts\stop-webui-ma-home.ps1"
Write-Host "Foreground: .\scripts\restart-webui-ma-home.ps1 -Foreground"
