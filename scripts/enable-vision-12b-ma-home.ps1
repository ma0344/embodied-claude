# ma-home — vision describe → google/gemma-4-12b-qat (tick / MCP / prefetch)
#
# Removes legacy LM_STUDIO_VISION_MODEL from presence-ui.local.env.
# Image caption uses PRESENCE_LLM_MODEL / CLAUDE_MODEL / 12b-qat default (wifi_cam_mcp.vision).
#
# Usage:
#   .\scripts\enable-vision-12b-ma-home.ps1
#   .\scripts\restart-presence-ui.ps1
#   # Restart Claude Code / MCP wifi-cam if MCP see tool is used

param(
    [string]$SurfaceModel = "google/gemma-4-12b-qat",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$LocalEnvFile = Join-Path $env:USERPROFILE ".config\embodied-claude\presence-ui.local.env"
$LegacyVisionKey = "LM_STUDIO_VISION_MODEL"

if ($WhatIf) {
    Write-Host "Would remove $LegacyVisionKey from $LocalEnvFile (if present)"
    Write-Host "Would set wifi-cam env CLAUDE_MODEL=$SurfaceModel via set-lmstudio-model -VisionModel (deprecated key cleanup)"
    exit 0
}

$content = if (Test-Path $LocalEnvFile) { Get-Content $LocalEnvFile -Encoding UTF8 } else { @() }
$newContent = @()
$removed = $false
foreach ($line in $content) {
    if ($line -match "^\s*$([regex]::Escape($LegacyVisionKey))=") {
        $removed = $true
        continue
    }
    $newContent += $line
}
if ($removed -or -not (Test-Path $LocalEnvFile)) {
    if (-not $removed) {
        $newContent = @($newContent) + @(
            "",
            "# vision describe uses surface 12b-qat (wifi_cam_mcp.vision — no LM_STUDIO_VISION_MODEL)"
        )
    } else {
        $newContent = @($newContent) + @(
            "",
            "# vision describe → 12b-qat via wifi_cam_mcp.vision (LM_STUDIO_VISION_MODEL removed $(Get-Date -Format yyyy-MM-dd))"
        )
    }
    $dir = Split-Path $LocalEnvFile -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $newContent | Set-Content -Path $LocalEnvFile -Encoding UTF8
    Write-Host "Updated $LocalEnvFile (removed $LegacyVisionKey if was set)"
} else {
    Write-Host "OK: $LegacyVisionKey not in $LocalEnvFile"
}

# Drop legacy vision key from .mcp.json wifi-cam env (12b default in vision.py)
$McpJson = Join-Path $Repo ".mcp.json"
if (Test-Path $McpJson) {
    $cfg = Get-Content $McpJson -Raw | ConvertFrom-Json
    $wifi = $cfg.mcpServers.'wifi-cam'
    if ($wifi -and $wifi.env) {
        if ($wifi.env.PSObject.Properties.Name -contains $LegacyVisionKey) {
            $wifi.env.PSObject.Properties.Remove($LegacyVisionKey)
        }
        if (-not $wifi.env.CLAUDE_MODEL) {
            $wifi.env | Add-Member -NotePropertyName "CLAUDE_MODEL" -NotePropertyValue $SurfaceModel -Force
        }
        $cfg | ConvertTo-Json -Depth 10 | Set-Content -Path $McpJson -Encoding UTF8
        Write-Host "Updated .mcp.json wifi-cam: CLAUDE_MODEL=$SurfaceModel, removed $LegacyVisionKey"
    }
}

Write-Host ""
Write-Host "Next:"
Write-Host "  1. LM Studio: google/gemma-4-12b-qat loaded (surface + vision describe share this model)"
Write-Host "  2. .\scripts\restart-presence-ui.ps1"
Write-Host "  3. autonomous tick / observe_room → Developer Log model=google/gemma-4-12b-qat"
