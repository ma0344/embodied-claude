# Rebuild presence-ui's copies of sociality packages after compose/relationship changes.
#
# Path deps are installed as wheels into .venv — `restart-presence-ui` alone does NOT
# pick up interaction-orchestrator-mcp edits until this runs (worker also does this @ start).
#
# Usage:
#   .\scripts\sync-presence-deps.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$PresenceDir = Join-Path $Repo "presence-ui"

if (-not (Test-Path $PresenceDir)) {
    Write-Error "Missing $PresenceDir"
}

Push-Location $PresenceDir
try {
    Write-Host "==> sync-presence-deps (orchestrator + relationship + social-state + wifi-cam)"
    uv sync --extra dev `
        --reinstall-package interaction-orchestrator-mcp `
        --reinstall-package relationship-mcp `
        --reinstall-package social-state-mcp `
        --reinstall-package wifi-cam-mcp
    Write-Host "OK"
} finally {
    Pop-Location
}
