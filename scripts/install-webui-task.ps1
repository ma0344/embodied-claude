# Register or remove a logon Scheduled Task that keeps claude-code-webui running.
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
    $Shell = Get-Command powershell -ErrorAction SilentlyContinue
}
if (-not $Shell) {
    Write-Error "PowerShell not found"
}

$Argument = @(
    "-NoProfile"
    "-ExecutionPolicy", "Bypass"
    "-WindowStyle", "Hidden"
    "-File", "`"$Daemon`""
) -join " "

$Action = New-ScheduledTaskAction -Execute $Shell.Source -Argument $Argument -WorkingDirectory $Repo
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
Write-Host "Stop:"
Write-Host "  Stop-ScheduledTask -TaskName $TaskName"
