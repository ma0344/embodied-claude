# MEM-5g DB repair + MEM-5f-c dream digest rebuild (ma-home)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $Root "presence-ui")
try {
    uv sync --reinstall-package social-core --extra dev | Out-Null
    uv run python (Join-Path $Root "scripts\repair_stm_and_rebuild_digest.py")
} finally {
    Pop-Location
}
