# Register or remove a logon Scheduled Task that keeps claude-code-webui running.
#
# OPTIONAL on ma-home when PRESENCE_NATIVE_CHAT=1 (Native chat on :8090).
# To turn off:
#   .\scripts\stop-webui-ma-home.ps1
#   .\scripts\install-webui-task.ps1 -Uninstall
#
# Install (run once, elevated not required for per-user task):
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\install-webui-task.ps1
#
# Remove:
#   .\scripts\install-webui-task.ps1 -Uninstall
#
# Logs:
#   %USERPROFILE%\.config\embodied-claude\logs\webui.log

param(
    [switch]$Uninstall,
    [string]$TaskName = "EmbodiedClaude-WebUI"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Daemon = Join-Path $PSScriptRoot "run-webui-ma-home-daemon.ps1"
$SettingsLocal = Join-Path $Repo ".claude\settings.local.json"

if (-not (Test-Path $Daemon)) {
    Write-Error "Missing $Daemon"
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

if (-not (Test-Path $SettingsLocal)) {
    Write-Error @"
Missing $SettingsLocal

  Copy-Item .claude\settings.local.json.example .claude\settings.local.json
  Edit ANTHROPIC_AUTH_TOKEN, then re-run this script.
"@
}

$Shell = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $Shell) {
    Write-Error "pwsh.exe required (install PowerShell 7)"
}

. (Join-Path $PSScriptRoot "embodied-hidden-launcher.ps1")
$Launcher = Join-Path $PSScriptRoot "run-webui-ma-home-daemon-hidden.vbs"
New-EmbodiedHiddenVbsLauncher -Repo $Repo -Ps1Path $Daemon -LauncherPath $Launcher | Out-Null
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
Write-Host "  repo:   $Repo"
Write-Host "  log:    $env:USERPROFILE\.config\embodied-claude\logs\webui.log"
Write-Host ""
Write-Host "Start now:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host ""
Write-Host "Restart (after config changes):"
Write-Host "  .\scripts\restart-webui-ma-home.ps1"
Write-Host ""
Write-Host "Stop:"
Write-Host "  .\scripts\stop-webui-ma-home.ps1"
