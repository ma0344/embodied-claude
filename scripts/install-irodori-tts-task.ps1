# Register or remove a logon Scheduled Task that starts Irodori TTS (:8088).
#
# Install:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\install-irodori-tts-task.ps1
#
# Remove:
#   .\scripts\install-irodori-tts-task.ps1 -Uninstall
#
# Log:
#   %USERPROFILE%\.config\embodied-claude\logs\irodori-tts.log
#
# Coexistence with Aivis is discouraged. After switching to Irodori, disable Aivis:
#   .\scripts\install-aivis-tts-task.ps1 -Uninstall
#   # or: Disable-ScheduledTask -TaskName EmbodiedClaude-AivisTTS

param(
    [switch]$Uninstall,
    [string]$TaskName = "EmbodiedClaude-IrodoriTTS"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Starter = Join-Path $PSScriptRoot "start-irodori-tts.ps1"

if (-not (Test-Path $Starter)) {
    Write-Error "Missing $Starter"
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
$Launcher = Join-Path $PSScriptRoot "start-irodori-tts-hidden.vbs"
New-EmbodiedHiddenVbsLauncher -Repo $Repo -Ps1Path $Starter -LauncherPath $Launcher -ExtraArguments "-Background" | Out-Null
$Action = New-EmbodiedHiddenTaskAction -Repo $Repo -LauncherPath $Launcher
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "  starts: at logon ($env:USERNAME), background Irodori on :8088"
Write-Host "  repo:   $Repo"
Write-Host "  log:    $env:USERPROFILE\.config\embodied-claude\logs\irodori-tts.log"
Write-Host ""
Write-Host "Disable Aivis (recommended — do not run both as defaults):"
Write-Host "  .\scripts\install-aivis-tts-task.ps1 -Uninstall"
Write-Host "  # or: Disable-ScheduledTask -TaskName EmbodiedClaude-AivisTTS"
Write-Host ""
Write-Host "Start now:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host "  # or: .\scripts\start-irodori-tts.ps1 -Background"
Write-Host ""
Write-Host "Check:"
Write-Host "  curl -s http://127.0.0.1:8088/health"
Write-Host "  curl -s http://127.0.0.1:8090/api/v1/ui-config | ConvertFrom-Json | Select surface_tts_ready"
