# Register or remove a logon Scheduled Task for Input Leap server (ma-home → koyori).
#
# Install:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\install-input-leap-task.ps1
#
# Remove:
#   .\scripts\install-input-leap-task.ps1 -Uninstall
#
# Logs:
#   %USERPROFILE%\.config\embodied-claude\logs\input-leap-server.log
#
# Note: disable Mouse Without Borders on ma-home while using Input Leap (both hook KB/mouse).

param(
    [switch]$Uninstall,
    [string]$TaskName = "EmbodiedClaude-InputLeapServer",
    [string]$InstallDir = $(if ($env:INPUT_LEAP_DIR) { $env:INPUT_LEAP_DIR } else { "C:\Programs\InputLeap" })
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Daemon = Join-Path $PSScriptRoot "run-input-leap-server-daemon.ps1"

if (-not (Test-Path $Daemon)) {
    Write-Error "Missing $Daemon"
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

if (-not (Test-Path (Join-Path $InstallDir "input-leaps.exe"))) {
    Write-Error "input-leaps.exe not found under $InstallDir — set INPUT_LEAP_DIR or install Input Leap first"
}

$Shell = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $Shell) {
    Write-Error "pwsh.exe required (install PowerShell 7)"
}

. (Join-Path $PSScriptRoot "embodied-hidden-launcher.ps1")
$Launcher = Join-Path $PSScriptRoot "run-input-leap-server-daemon-hidden.vbs"
$Extra = "-InstallDir `"$InstallDir`""
New-EmbodiedHiddenVbsLauncher -Repo $Repo -Ps1Path $Daemon -LauncherPath $Launcher -ExtraArguments $Extra | Out-Null
$Action = New-EmbodiedHiddenTaskAction -Repo $Repo -LauncherPath $Launcher
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "  starts: at logon ($env:USERNAME)"
Write-Host "  server: $InstallDir\input-leaps.exe (--disable-crypto)"
Write-Host "  log:    $env:USERPROFILE\.config\embodied-claude\logs\input-leap-server.log"
Write-Host ""
Write-Host "Mouse Without Borders: Win-only; turn OFF on ma-home if both fight for mouse/KB hooks."
Write-Host ""
Write-Host "Start now (foreground test):"
Write-Host "  .\scripts\ma-home-input-leap-server.ps1"
Write-Host ""
Write-Host "Stop daemon:"
Write-Host "  Stop-Process -Name input-leaps -Force -ErrorAction SilentlyContinue"
Write-Host "  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
