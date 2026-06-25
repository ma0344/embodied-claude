# Configure WinGet Input Leap 3.0.2 (ma-home server → koyori client).
#
# - Installs via winget if missing
# - Copies repo default.sgc, disables SSL (koyori: KOYORI_INPUT_LEAP_CRYPTO=0)
# - Removes legacy EmbodiedClaude-InputLeapServer CLI task (conflicts with input-leapd)
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\configure-input-leap-winget.ps1
#   .\scripts\configure-input-leap-winget.ps1 -LaunchGui   # tray app after configure

param(
    [switch]$LaunchGui,
    [string]$InstallDir = "C:\Program Files\InputLeap",
    [string]$TaskName = "EmbodiedClaude-InputLeapServer"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SourceSgc = Join-Path $Repo "scripts\input-leap\default.sgc"
$ConfigDir = Join-Path $env:USERPROFILE ".config\embodied-claude\input-leap"
$TargetSgc = Join-Path $ConfigDir "default.sgc"

function Test-InputLeapInstalled {
    return (Test-Path (Join-Path $InstallDir "input-leapd.exe"))
}

if (-not (Test-InputLeapInstalled)) {
    Write-Host "Installing input-leap 3.0.2 via winget..."
    winget install -e --id input-leap.input-leap --accept-package-agreements --accept-source-agreements
    if (-not (Test-InputLeapInstalled)) {
        Write-Error "input-leapd.exe not found under $InstallDir after winget install"
    }
}

Get-Process input-leaps -ErrorAction SilentlyContinue | Stop-Process -Force
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

if (-not (Test-Path $SourceSgc)) {
    Write-Error "Missing $SourceSgc"
}

New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
Copy-Item -Path $SourceSgc -Destination $TargetSgc -Force
Write-Host "Copied default.sgc -> $TargetSgc"

$regBase = "HKCU:\Software\InputLeap\InputLeap"
if (-not (Test-Path $regBase)) {
    New-Item -Path $regBase -Force | Out-Null
}

$sgcPath = $TargetSgc -replace '\\', '/'
Set-ItemProperty -Path $regBase -Name screenName -Value "MA-HOME"
Set-ItemProperty -Path $regBase -Name port -Value 24800 -Type DWord
Set-ItemProperty -Path $regBase -Name cryptoEnabled -Value "false"
Set-ItemProperty -Path $regBase -Name requireClientCertificate -Value "false"
Set-ItemProperty -Path $regBase -Name useExternalConfig -Value "true"
Set-ItemProperty -Path $regBase -Name useInternalConfig -Value "false"
Set-ItemProperty -Path $regBase -Name configFile -Value $sgcPath
Set-ItemProperty -Path $regBase -Name autoStart -Value "true"
Set-ItemProperty -Path $regBase -Name groupServerChecked -Value "true"
Set-ItemProperty -Path $regBase -Name groupClientChecked -Value "false"
Write-Host "Registry: external config, crypto off, port 24800, screen MA-HOME"

$fw = Get-NetFirewallRule -DisplayName "Input Leap" -ErrorAction SilentlyContinue
if (-not $fw) {
    New-NetFirewallRule -DisplayName "Input Leap" -Direction Inbound -Protocol TCP -LocalPort 24800 -Action Allow | Out-Null
    Write-Host "Firewall: added TCP 24800"
}

$svc = Get-Service -Name InputLeap -ErrorAction SilentlyContinue
if ($svc) {
    try {
        if ($svc.Status -eq "Running") {
            Restart-Service InputLeap -ErrorAction Stop
        } else {
            Start-Service InputLeap -ErrorAction Stop
        }
        Write-Host "Service InputLeap: $((Get-Service InputLeap).Status)"
    } catch {
        Write-Warning "Could not restart InputLeap (admin required). Run elevated:"
        Write-Warning "  Restart-Service InputLeap"
    }
} else {
    Write-Warning "InputLeap Windows service not found — start input-leap.exe GUI manually"
}

Start-Sleep -Seconds 2
$listen = Get-NetTCPConnection -LocalPort 24800 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listen) {
    Write-Host "Listening on :24800 (pid=$($listen.OwningProcess))" -ForegroundColor Green
} else {
    Write-Host "WARN: :24800 not listening yet — open Input Leap GUI, Server, Apply" -ForegroundColor Yellow
}

if ($LaunchGui) {
    $gui = Join-Path $InstallDir "input-leap.exe"
    if (Test-Path $gui) {
        Start-Process $gui
        Write-Host "Launched input-leap.exe (tray)"
    }
}

Write-Host ""
Write-Host "koyori: KOYORI_INPUT_LEAP_CRYPTO=0, screen name koyori"
Write-Host "GUI: Server mode, MA-HOME right edge -> koyori"
Write-Host "Legacy CLI task removed — use Windows service + GUI, not install-input-leap-task.ps1"
