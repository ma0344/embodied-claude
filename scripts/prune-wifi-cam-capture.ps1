# One-shot cleanup for %TEMP%\wifi-cam-mcp (or CAPTURE_DIR).
# Usage: .\scripts\prune-wifi-cam-capture.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $Repo "scripts\presence-ui-ma-home-lib.ps1")
Set-PresenceMaHomeEnv -Repo $Repo

Push-Location (Join-Path $Repo "presence-ui")
try {
    uv run python -c @"
from presence_ui.services.capture_cache import prune_startup
n = prune_startup()
print(f'Pruned {n} file(s) under capture dir')
"@
} finally {
    Pop-Location
}
