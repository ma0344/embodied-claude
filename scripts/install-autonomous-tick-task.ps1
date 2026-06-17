# Register or remove a periodic Scheduled Task for autonomous-tick (A4f).
#
# Install (default: every 15 minutes + at logon):
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\install-autonomous-tick-task.ps1
#
# Remove:
#   .\scripts\install-autonomous-tick-task.ps1 -Uninstall
#
# Log: %USERPROFILE%\.config\embodied-claude\logs\autonomous-tick.log

param(
    [switch]$Uninstall,
    [string]$TaskName = "EmbodiedClaude-AutonomousTick",
    [int]$IntervalMinutes = $(if ($env:AUTONOMOUS_TICK_INTERVAL_MINUTES) { [int]$env:AUTONOMOUS_TICK_INTERVAL_MINUTES } else { 15 })
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Runner = Join-Path $PSScriptRoot "run-autonomous-tick.ps1"

if (-not (Test-Path $Runner)) {
    Write-Error "Missing $Runner"
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

$Shell = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $Shell) {
    Write-Error "pwsh.exe required (install PowerShell 7)"
}

. (Join-Path $PSScriptRoot "embodied-hidden-launcher.ps1")
$Launcher = Join-Path $PSScriptRoot "run-autonomous-tick-hidden.vbs"
New-EmbodiedHiddenVbsLauncher -Repo $Repo -Ps1Path $Runner -LauncherPath $Launcher | Out-Null
$Action = New-EmbodiedHiddenTaskAction -Repo $Repo -LauncherPath $Launcher

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
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

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
Write-Host "  log:      $env:USERPROFILE\.config\embodied-claude\logs\autonomous-tick.log"
Write-Host ""
Write-Host "Requires: presence-ui on :8090, PRESENCE_GATEWAY_DIRECT_ACTIONS=1"
Write-Host ""
Write-Host "Run once now:"
Write-Host "  .\scripts\run-autonomous-tick.ps1"
Write-Host ""
Write-Host "Start task:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
