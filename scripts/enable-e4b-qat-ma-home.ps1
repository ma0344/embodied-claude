# ma-home — align classifier + vision describe on google/gemma-4-e4b-qat
#
# Usage:
#   .\scripts\enable-e4b-qat-ma-home.ps1
#   .\scripts\restart-presence-ui.ps1

param(
    [string]$E4bQatModel = "google/gemma-4-e4b-qat",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

if ($WhatIf) {
    & (Join-Path $Repo "scripts\enable-classifier-e4b-qat-ma-home.ps1") -ClassifierModel $E4bQatModel -WhatIf
    & (Join-Path $Repo "scripts\enable-vis-e4b-ma-home.ps1") -VisionModel $E4bQatModel -WhatIf
    exit 0
}

& (Join-Path $Repo "scripts\enable-classifier-e4b-qat-ma-home.ps1") -ClassifierModel $E4bQatModel
& (Join-Path $Repo "scripts\enable-vis-e4b-ma-home.ps1") -VisionModel $E4bQatModel

Write-Host ""
Write-Host "e4b-qat aligned: PRESENCE_CLASSIFIER_MODEL + LM_STUDIO_VISION_MODEL + settings/.mcp.json vision"
