# Run presence-ui in the foreground (used by -Foreground, daemon, scheduled task).
#
# Do not call directly unless debugging — use .\scripts\run-presence-ui.ps1

param(
    [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
    [string]$BackendPort = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" })
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$PresenceDir = Join-Path $Repo "presence-ui"
. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")

$LogFile = if ($env:PRESENCE_UI_LOG_FILE) { $env:PRESENCE_UI_LOG_FILE } else { Get-PresenceUiLogFile }

if (-not (Test-Path $PresenceDir)) {
    Write-Error "Missing $PresenceDir"
}

New-Item -ItemType Directory -Force -Path (Split-Path $LogFile -Parent) | Out-Null

function Write-Log([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Host $line
}

Initialize-PresenceUiEnv -Repo $Repo -Port $Port -BackendPort $BackendPort

Push-Location $PresenceDir
try {
    if (-not (Test-Path "uv.lock")) {
        Write-Log "uv sync"
        uv sync 2>&1 | ForEach-Object { Write-Log $_ }
    }

    Write-Log "starting presence-ui port=$Port backend=$env:CLAUDE_CODE_BACKEND_URL"
    uv run presence-ui 2>&1 | ForEach-Object { Write-Log $_ }
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    Write-Log "presence-ui exited code=$exitCode"
    exit $exitCode
} finally {
    Pop-Location
}
