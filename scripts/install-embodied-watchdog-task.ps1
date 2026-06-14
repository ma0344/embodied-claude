# Register or remove a periodic Scheduled Task for watch-embodied-health.ps1.
#
# Install:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\install-embodied-watchdog-task.ps1
#
# Remove:
#   .\scripts\install-embodied-watchdog-task.ps1 -Uninstall
#
# Log: %USERPROFILE%\.config\embodied-claude\logs\watchdog.log

param(
    [switch]$Uninstall,
    [string]$TaskName = "EmbodiedClaude-Watchdog",
    [int]$IntervalMinutes = $(if ($env:EMBODIED_WATCHDOG_INTERVAL_MIN) { [int]$env:EMBODIED_WATCHDOG_INTERVAL_MIN } else { 2 }),
    [int]$StdioHangMinutes = $(if ($env:EMBODIED_WATCHDOG_STDIO_HANG_MIN) { [int]$env:EMBODIED_WATCHDOG_STDIO_HANG_MIN } else { 5 })
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Watchdog = Join-Path $PSScriptRoot "watch-embodied-health.ps1"
$HiddenLauncher = Join-Path $PSScriptRoot "watch-embodied-health-hidden.vbs"

if (-not (Test-Path $Watchdog)) {
    Write-Error "Missing $Watchdog"
}

# Keep VBS launcher in sync with repo path (VBS has no env vars).
$vbsContent = @"
' Run watch-embodied-health.ps1 with no console window (Scheduled Task).
Option Explicit
Dim sh, repo, ps1, cmd
repo = "$Repo"
ps1 = repo & "\scripts\watch-embodied-health.ps1"
cmd = "pwsh.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """ -StdioHangMinutes $StdioHangMinutes"
Set sh = CreateObject("Wscript.Shell")
sh.Run cmd, 0, False
"@
Set-Content -Path $HiddenLauncher -Value $vbsContent -Encoding ASCII

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

$Shell = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $Shell) {
    Write-Error "pwsh.exe required for watchdog (install PowerShell 7)"
}

# wscript //B = no flash (pwsh -WindowStyle Hidden still flashes from Task Scheduler)
$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "//B `"$HiddenLauncher`"" -WorkingDirectory $Repo

$StartAt = (Get-Date).AddMinutes(1)
$RepeatTrigger = New-ScheduledTaskTrigger -Once -At $StartAt `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3)

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($RepeatTrigger, $LogonTrigger) `
    -Settings $Settings `
    -Principal $Principal `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "  interval: every ${IntervalMinutes}m (+ once at logon)"
Write-Host "  launcher: wscript (hidden, no console flash)"
Write-Host "  stdio kill: after ${StdioHangMinutes}m idle (CPU ~0)"
Write-Host "  repo:     $Repo"
Write-Host "  log:      $env:USERPROFILE\.config\embodied-claude\logs\watchdog.log"
Write-Host ""
Write-Host "Run once now:"
Write-Host "  .\scripts\watch-embodied-health.ps1"
Write-Host ""
Write-Host "Dry-run:"
Write-Host "  .\scripts\watch-embodied-health.ps1 -DryRun"
Write-Host ""
Write-Host "Start task:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
