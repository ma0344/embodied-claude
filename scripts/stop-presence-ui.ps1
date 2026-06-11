# Stop presence-ui on ma-home (scheduled task + daemon + port listener).
#
# Usage:
#   .\scripts\stop-presence-ui.ps1

param(
    [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
    [string]$TaskName = "EmbodiedClaude-PresenceUI"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")

Write-Host "==> stop-presence-ui"
$Stopped = Stop-PresenceUiMaHome -Port $Port -TaskName $TaskName

if ($Stopped.Count -eq 0) {
    Write-Host "    nothing was running on port $Port"
} else {
    foreach ($Line in $Stopped) {
        Write-Host "    stopped $Line"
    }
}

Write-Host "    port $Port is free"
