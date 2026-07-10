# Install Style-Bert-VITS2 for Windows (RTX / CUDA).
#
# Official zip route (recommended by community):
#   https://github.com/litagin02/Style-Bert-VITS2/releases
#   Download sbv2.zip -> extract -> run Install-Style-Bert-VITS2.bat inside
#
# This script clones the repo as a fallback and prints manual steps.
#
# Usage:
#   .\scripts\install-style-bert-vits2.ps1
#   .\scripts\install-style-bert-vits2.ps1 -TargetDir C:\Users\ma\src\Style-Bert-VITS2

param(
    [string]$TargetDir = "C:\Users\ma\src\Style-Bert-VITS2"
)

$ErrorActionPreference = "Stop"

if (Test-Path (Join-Path $TargetDir "App.bat")) {
    Write-Host "Already present: $TargetDir"
    Write-Host "Open App.bat to start WebUI."
    exit 0
}

Write-Host "Style-Bert-VITS2 not found at $TargetDir"
Write-Host ""
Write-Host "Recommended (prebuilt Windows bundle):"
Write-Host "  1. Download sbv2.zip from https://github.com/litagin02/Style-Bert-VITS2/releases"
Write-Host "  2. Extract to $TargetDir"
Write-Host "  3. Run Install-Style-Bert-VITS2.bat (once, ~10-30 min)"
Write-Host "  4. Run App.bat"
Write-Host ""
Write-Host "Alternative: git clone (dev setup — you install deps yourself)"
$clone = Read-Host "Clone litagin02/Style-Bert-VITS2 to $TargetDir now? [y/N]"
if ($clone -notmatch '^[yY]') {
    exit 0
}

if (Test-Path $TargetDir) {
    Write-Error "Target exists but App.bat missing: $TargetDir"
}

git clone --depth 1 https://github.com/litagin02/Style-Bert-VITS2.git $TargetDir
Write-Host "Cloned to $TargetDir"
Write-Host "Follow README.md for venv + pip install, then: python app.py"
