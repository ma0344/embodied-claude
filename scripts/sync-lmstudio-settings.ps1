# Align settings.local.json env MODEL keys with the top-level "model" field.
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\sync-lmstudio-settings.ps1
#   .\scripts\sync-lmstudio-settings.ps1 -WhatIf

param([switch]$WhatIf)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$SettingsLocal = Join-Path $Repo ".claude\settings.local.json"

. (Join-Path $PSScriptRoot "lmstudio-env.ps1")

if (-not (Test-Path $SettingsLocal)) {
    Write-Error @"
Missing $SettingsLocal

  Copy-Item .claude\settings.local.json.example .claude\settings.local.json
"@
}

$Result = Sync-LmStudioSettingsFile -SettingsLocal $SettingsLocal -WhatIf:$WhatIf

Write-Host "==> sync-lmstudio-settings"
Write-Host "    file:  $SettingsLocal"
Write-Host "    model: $($Result.Model)"

if ($Result.Changed.Count -eq 0) {
    Write-Host "    OK: env MODEL keys already match."
    exit 0
}

Write-Host ""
foreach ($Line in $Result.Changed) {
    if ($WhatIf) {
        Write-Host "  would update env.$Line"
    } else {
        Write-Host "  updated env.$Line"
    }
}

if ($WhatIf) {
    Write-Host ""
    Write-Host "Re-run without -WhatIf to apply."
} else {
    Write-Host ""
    Write-Host "Restart claude-code-webui if it is running."
    Write-Host "To change the model ID: .\scripts\set-lmstudio-model.ps1 -Model <id>"
    Write-Host "Docs: docs/lmstudio-model-change.md"
}
