# RP Phase 1 — LM Studio carries SOUL.core; presence-ui skips duplicate append.
#
# Prerequisite: paste presets/koyori-SOUL.core.md into LM Studio chat model System Prompt
# (google/gemma-4-12b-qat). See docs/lmstudio-model-change.md § SOUL.core
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\enable-rp-phase1-ma-home.ps1
#   .\scripts\restart-presence-ui.ps1

param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$CorePath = Join-Path $Repo "presets\koyori-SOUL.core.md"
$LocalEnvFile = Join-Path $env:USERPROFILE ".config\embodied-claude\presence-ui.local.env"
$Key = "PRESENCE_SOUL_CORE_IN_APPEND"
$Value = "0"

if (-not (Test-Path $CorePath)) {
    Write-Error "Missing $CorePath"
}

$Dir = Split-Path $LocalEnvFile -Parent
if (-not (Test-Path $Dir)) {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
}

$OutLines = New-Object System.Collections.Generic.List[string]
if (Test-Path $LocalEnvFile) {
    foreach ($line in Get-Content $LocalEnvFile -Encoding UTF8) {
        if ($line -match "^\s*$([regex]::Escape($Key))=") { continue }
        [void]$OutLines.Add($line)
    }
}
[void]$OutLines.Add("$Key=$Value")

if ($WhatIf) {
    Write-Host "Would write $LocalEnvFile :"
    foreach ($line in $OutLines) { Write-Host "  $line" }
    exit 0
}

$OutLines | Set-Content -Path $LocalEnvFile -Encoding UTF8
Write-Host "Updated $LocalEnvFile"
Write-Host "  $Key=$Value"
Write-Host ""
Write-Host "Confirm LM Studio chat model System Prompt = contents of:"
Write-Host "  $CorePath"
Write-Host ""
Write-Host "Then restart presence-ui:"
Write-Host "  .\scripts\restart-presence-ui.ps1"
