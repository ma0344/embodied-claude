# Run presence-ui in a restart loop with file logging (for Scheduled Task / background).
#
# Foreground test:
#   .\scripts\run-presence-ui-daemon.ps1
#
# Install as logon task:
#   .\scripts\install-presence-ui-task.ps1

param(
    [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
    [string]$BackendPort = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
    [int]$RestartSeconds = $(if ($env:PRESENCE_UI_RESTART_SECONDS) { [int]$env:PRESENCE_UI_RESTART_SECONDS } else { 15 })
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")

$LogFile = Get-PresenceUiLogFile
$Worker = Join-Path $PSScriptRoot "run-presence-ui-worker.ps1"
$env:PRESENCE_UI_LOG_FILE = $LogFile

New-Item -ItemType Directory -Force -Path (Split-Path $LogFile -Parent) | Out-Null

function Write-Log([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Host $line
}

Write-Log "daemon start repo=$Repo port=$Port backend=$BackendPort"

while ($true) {
    try {
        Write-Log "starting worker"
        & $Worker -Port $Port -BackendPort $BackendPort
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) { $exitCode = 0 }
        Write-Log "worker exited code=$exitCode"
    } catch {
        Write-Log "worker error: $($_.Exception.Message)"
    }

    Write-Log "restart in ${RestartSeconds}s"
    Start-Sleep -Seconds $RestartSeconds
}
