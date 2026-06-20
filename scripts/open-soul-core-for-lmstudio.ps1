# Open koyori-SOUL.core.md for copy-paste into LM Studio System Prompt.
param(
    [switch]$CopyToClipboard
)

$ErrorActionPreference = "Stop"
$CorePath = Join-Path (Split-Path $PSScriptRoot -Parent) "presets\koyori-SOUL.core.md"
if (-not (Test-Path $CorePath)) {
    Write-Error "Missing $CorePath"
}

$Body = Get-Content $CorePath -Raw -Encoding UTF8
Write-Host "SOUL.core path: $CorePath"
Write-Host ""
Write-Host "LM Studio: load google/gemma-4-12b-qat -> System Prompt -> paste full file -> reload model."
Write-Host "Then: .\scripts\enable-rp-phase1-ma-home.ps1"
Write-Host ""

if ($CopyToClipboard) {
    Set-Clipboard -Value $Body
    Write-Host "Copied to clipboard."
}

Start-Process notepad.exe -ArgumentList $CorePath
