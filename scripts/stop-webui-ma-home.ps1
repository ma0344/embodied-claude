# Stop claude-code-webui on ma-home (scheduled task + daemon + port listener).
#
# Usage:
#   .\scripts\stop-webui-ma-home.ps1

param(
    [string]$Port = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
    [string]$TaskName = "EmbodiedClaude-WebUI"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "webui-ma-home-lib.ps1")

Write-Host "==> stop-webui-ma-home"
$Stopped = Stop-WebuiMaHome -Port $Port -TaskName $TaskName

if ($Stopped.Count -eq 0) {
    Write-Host "    nothing was running on port $Port"
} else {
    foreach ($Line in $Stopped) {
        Write-Host "    stopped $Line"
    }
}

Write-Host "    port $Port is free"
