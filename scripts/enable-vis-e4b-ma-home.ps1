# VIS-e4b ship — vision model → google/gemma-4-e4b (ma-home 2026-06-29)
#
# Prerequisite: LM Studio に e4b vision をロード（classifier と同じ GGUF で可）
#
# Usage:
#   .\scripts\enable-vis-e4b-ma-home.ps1
#   .\scripts\restart-presence-ui.ps1

param(
    [string]$VisionModel = "google/gemma-4-e4b",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$LocalEnvFile = Join-Path $env:USERPROFILE ".config\embodied-claude\presence-ui.local.env"
$Key = "LM_STUDIO_VISION_MODEL"

$Dir = Split-Path $LocalEnvFile -Parent
if (-not (Test-Path $Dir)) {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
}

if ($WhatIf) {
    & (Join-Path $Repo "scripts\set-lmstudio-model.ps1") -VisionModel $VisionModel -WhatIf
    Write-Host "Would set $Key=$VisionModel in $LocalEnvFile"
    exit 0
}

& (Join-Path $Repo "scripts\set-lmstudio-model.ps1") -VisionModel $VisionModel

$content = if (Test-Path $LocalEnvFile) { Get-Content $LocalEnvFile -Encoding UTF8 } else { @() }
$replaced = $false
$newContent = foreach ($line in $content) {
    if ($line -match "^\s*$([regex]::Escape($Key))=") {
        $replaced = $true
        "$Key=$VisionModel"
    } else {
        $line
    }
}
if (-not $replaced) {
    $newContent = @($newContent) + @("", "# vision (wifi-cam / gateway describe)", "$Key=$VisionModel")
}
$newContent | Set-Content -Path $LocalEnvFile -Encoding UTF8

Write-Host ""
Write-Host "Updated $LocalEnvFile : $Key=$VisionModel"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. LM Studio: unload Qwen2.5-VL, keep google/gemma-4-e4b loaded (Concurrent=1)"
Write-Host "  2. .\scripts\check-lmstudio-model.ps1"
Write-Host "  3. .\scripts\restart-presence-ui.ps1"
