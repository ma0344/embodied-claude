# Restart presence-ui on ma-home after code / config changes.
#
# Default: stop then start in background (terminal returns immediately).
# Foreground: stop then run in this terminal (debug).
#
# Usage:
#   .\scripts\restart-presence-ui.ps1
#   .\scripts\restart-presence-ui.ps1 -Foreground

param(
    [switch]$Foreground,
    [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
    [string]$BackendPort = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
    [string]$TaskName = "EmbodiedClaude-PresenceUI"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")

Write-Host "==> restart-presence-ui"

& (Join-Path $PSScriptRoot "sync-presence-deps.ps1")

$Stopped = Stop-PresenceUiMaHome -Port $Port -TaskName $TaskName
if ($Stopped.Count -eq 0) {
    Write-Host "    was not running"
} else {
    foreach ($Line in $Stopped) {
        Write-Host "    stopped $Line"
    }
}

$Runner = Join-Path $PSScriptRoot "run-presence-ui.ps1"
if ($Foreground) {
    & $Runner -Foreground -Port $Port -BackendPort $BackendPort
} else {
    & $Runner -Port $Port -BackendPort $BackendPort
}
exit $LASTEXITCODE
