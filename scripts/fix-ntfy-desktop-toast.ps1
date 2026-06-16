# Fix ntfy-desktop Windows toast notifications (portable ZIP install).
#
# Portable ZIP often ships only app.asar — toasted-notifier's ntfytoast.exe must live in
# resources/app.asar.unpacked/... or toasts fail silently (no permission prompt).
#
# Usage:
#   .\scripts\fix-ntfy-desktop-toast.ps1
#   .\scripts\fix-ntfy-desktop-toast.ps1 -NtfyDesktopDir "C:\Programs\ntfy-desktop-2.2.0-win32-amd64"

param(
    [string]$NtfyDesktopDir = "C:\Programs\ntfy-desktop-2.2.0-win32-amd64",
    [string]$AppId = "com.ntfydesktop.id"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$Exe = Join-Path $NtfyDesktopDir "ntfy-desktop.exe"
$Resources = Join-Path $NtfyDesktopDir "resources"
$Asar = Join-Path $Resources "app.asar"
$UnpackedRoot = Join-Path $Resources "app.asar.unpacked"
$DestToasted = Join-Path $UnpackedRoot "node_modules\toasted-notifier"
$ToastExe = Join-Path $DestToasted "vendor\ntfyToast\ntfytoast.exe"

if (-not (Test-Path $Exe)) {
    Write-Error "ntfy-desktop.exe not found: $Exe"
}
if (-not (Test-Path $Asar)) {
    Write-Error "app.asar not found: $Asar"
}

function Ensure-AsarExtracted {
    param([string]$TempExtract)
    if (Test-Path (Join-Path $TempExtract "node_modules\toasted-notifier\vendor\ntfyToast\ntfytoast.exe")) {
        return
    }
    New-Item -ItemType Directory -Force -Path $TempExtract | Out-Null
    Write-Host "Extracting app.asar (one-time)..."
    Push-Location (Join-Path $Repo "presence-ui")
    try {
        npx --yes @electron/asar extract $Asar $TempExtract | Out-Null
    } finally {
        Pop-Location
    }
}

$TempExtract = Join-Path $env:TEMP "ntfy-asar-extract-fix"
Ensure-AsarExtracted -TempExtract $TempExtract

$SrcToasted = Join-Path $TempExtract "node_modules\toasted-notifier"
if (-not (Test-Path (Join-Path $SrcToasted "vendor\ntfyToast\ntfytoast.exe"))) {
    Write-Error "toasted-notifier vendor missing in extracted asar"
}

Write-Host "Installing app.asar.unpacked vendor..."
if (Test-Path $DestToasted) {
    Remove-Item $DestToasted -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Split-Path $DestToasted) | Out-Null
Copy-Item -Path $SrcToasted -Destination $DestToasted -Recurse -Force
Write-Host "  -> $DestToasted"

Write-Host "Registering Start Menu shortcut + AppID ($AppId)..."
$installOut = & $ToastExe -install "ntfy-desktop\ntfy-desktop.lnk" $Exe $AppId 2>&1
if ($installOut) { Write-Host $installOut }

Write-Host ""
Write-Host "Vendor install done. Verify inside the app (CLI-only test is unreliable):"
Write-Host "  1. Start ntfy-desktop from Start Menu shortcut"
Write-Host "  2. Help -> Send Test Notification  (authoritative check)"
Write-Host ""
Write-Host "PC outbound toasts: use scripts\show-koyori-win-toast.ps1 (Open room button)."
Write-Host "ntfy-desktop body click cannot open 8090 — Windows opens the notifier app."
Write-Host "  1. Start ntfy-desktop from Start Menu shortcut"
Write-Host "  2. Help -> Send Test Notification  (authoritative check)"
Write-Host ""
Write-Host "Open notification settings:"
Start-Process "ms-settings:notifications"
