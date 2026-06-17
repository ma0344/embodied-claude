# Start Input Leap server on ma-home (portable zip layout).
# Usage: .\scripts\ma-home-input-leap-server.ps1

$ErrorActionPreference = "Stop"
$InstallDir = if ($env:INPUT_LEAP_DIR) { $env:INPUT_LEAP_DIR } else { "C:\Programs\InputLeap" }
$Config = Join-Path $InstallDir "default.sgc"
$Fingerprint = Join-Path $env:LOCALAPPDATA "InputLeap\SSL\Fingerprints\Local.txt"

if (-not (Test-Path (Join-Path $InstallDir "input-leaps.exe"))) {
  Write-Error "input-leaps.exe not found under $InstallDir"
}

Write-Host "=== Input Leap server (ma-home) ==="
Write-Host "  config: $Config"
if (Test-Path $Fingerprint) {
  Write-Host "  server fingerprint (copy to koyori TrustedServers.txt):"
  Get-Content $Fingerprint | ForEach-Object { Write-Host "    $_" }
} else {
  Write-Host "  fingerprint: (will be created on first start)"
}
Write-Host ""
Write-Host "  koyori trust (SSH):"
Write-Host "    koyori-input-leap-trust-server - < paste Local.txt lines"
Write-Host ""

Write-Host ""
Write-Host "  Stopping any existing input-leaps processes ..."
Get-Process -Name input-leaps -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

Set-Location $InstallDir
Write-Host "  starting: input-leaps.exe --disable-client-cert-checking --disable-crypto"
& .\input-leaps.exe -c $Config --disable-client-cert-checking --disable-crypto
