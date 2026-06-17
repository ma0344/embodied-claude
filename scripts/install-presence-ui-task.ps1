# Register or remove a logon Scheduled Task that keeps presence-ui running.
#
# Install (run once, elevated not required for per-user task):
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\install-presence-ui-task.ps1
#
# Remove:
#   .\scripts\install-presence-ui-task.ps1 -Uninstall
#
# Logs:
#   %USERPROFILE%\.config\embodied-claude\logs\presence-ui.log

param(
    [switch]$Uninstall,
    [string]$TaskName = "EmbodiedClaude-PresenceUI"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Daemon = Join-Path $PSScriptRoot "run-presence-ui-daemon.ps1"

if (-not (Test-Path $Daemon)) {
    Write-Error "Missing $Daemon"
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
$Launcher = Join-Path $PSScriptRoot "run-presence-ui-daemon-hidden.vbs"
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
Write-Host "  launcher: wscript (hidden, no console flash)"
Write-Host "  log:    $env:USERPROFILE\.config\embodied-claude\logs\presence-ui.log"
Write-Host ""

# C0: ma-home default — Native chat on first install (no restart here).
$LocalEnvFile = Join-Path $env:USERPROFILE ".config\embodied-claude\presence-ui.local.env"
if (-not (Test-Path $LocalEnvFile)) {
    $Dir = Split-Path $LocalEnvFile -Parent
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    @(
        "# presence-ui optional flags (loaded by run-presence-ui-worker.ps1)"
        "PRESENCE_NATIVE_CHAT=1"
        "# PRESENCE_CCS_PASSWORD=koyori-poc"
    ) | Set-Content -Path $LocalEnvFile -Encoding UTF8
    Write-Host "Created $LocalEnvFile (PRESENCE_NATIVE_CHAT=1)"
}

Write-Host ""
Write-Host "Start now:"
Write-Host "  .\scripts\run-presence-ui.ps1"
Write-Host ""
Write-Host "Native chat: :8080 webui Task is optional (see install-webui-task.ps1 -Uninstall)"
Write-Host ""
Write-Host "Restart:"
Write-Host "  .\scripts\restart-presence-ui.ps1"
Write-Host ""
Write-Host "Stop:"
Write-Host "  .\scripts\stop-presence-ui.ps1"
