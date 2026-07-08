# PFC-1 — classifier model → google/gemma-4-e4b-qat (ma-home)
#
# Prerequisite: LM Studio に e4b-qat をロード（OL-GATE / Stage1/2 / GAPI-2b 等）
#
# Usage:
#   .\scripts\enable-classifier-e4b-qat-ma-home.ps1
#   .\scripts\restart-presence-ui.ps1

param(
    [string]$ClassifierModel = "google/gemma-4-e4b-qat",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$LocalEnvFile = Join-Path $env:USERPROFILE ".config\embodied-claude\presence-ui.local.env"
$Key = "PRESENCE_CLASSIFIER_MODEL"

$Dir = Split-Path $LocalEnvFile -Parent
if (-not (Test-Path $Dir)) {
    if ($WhatIf) {
        Write-Host "Would create $Dir"
    } else {
        New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    }
}

if ($WhatIf) {
    Write-Host "Would set $Key=$ClassifierModel in $LocalEnvFile"
    exit 0
}

$content = if (Test-Path $LocalEnvFile) { Get-Content $LocalEnvFile -Encoding UTF8 } else { @() }
$replaced = $false
$newContent = foreach ($line in $content) {
    if ($line -match "^\s*$([regex]::Escape($Key))=") {
        $replaced = $true
        "$Key=$ClassifierModel"
    } else {
        $line
    }
}
if (-not $replaced) {
    $newContent = @($newContent) + @("", "# PFC-1 classifier (OL-GATE / Stage1/2 / GAPI)", "$Key=$ClassifierModel")
}
$newContent | Set-Content -Path $LocalEnvFile -Encoding UTF8

Write-Host ""
Write-Host "Updated $LocalEnvFile : $Key=$ClassifierModel"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. LM Studio: keep $ClassifierModel loaded (Concurrent=1, separate from 12b-qat surface)"
Write-Host "  2. .\scripts\restart-presence-ui.ps1"
Write-Host "  3. gateway-llm.log で classifier リクエストの model が $ClassifierModel であること"
