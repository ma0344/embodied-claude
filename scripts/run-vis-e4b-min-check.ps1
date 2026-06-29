# VIS-e4b 最小チェック — 3 画角 × Qwen vs e4b（v2 条件: 本番 prompt + -Isolate）
#
# 1. USB 外向き（look_outside JPEG）
# 2. Tapo desk preset（まーのデスク）
# 3. Tapo dining preset（リビング/ダイニング）

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Poc = Join-Path $RepoRoot "scripts\run-vis-e4b-poc.ps1"
$UsbJpg = Join-Path $env:USERPROFILE ".claude\captures\usb\usb_20260629_141812.jpg"

if (-not (Test-Path $UsbJpg)) {
    Write-Host "USB JPEG missing — run look_outside smoke first." -ForegroundColor Yellow
    exit 1
}

Write-Host "=== USB outside ===" -ForegroundColor Cyan
& $Poc -Image $UsbJpg -Isolate -OutSuffix "usb-outside-v2-check"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Tapo desk ===" -ForegroundColor Cyan
& $Poc -Preset desk -Isolate -OutSuffix "tapo-desk-v2"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Tapo dining ===" -ForegroundColor Cyan
& $Poc -Preset dining -Isolate -OutSuffix "tapo-dining-v2"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nDone. See benchmarks\vis-e4b-poc-*-v2*.md" -ForegroundColor Green
