# Run claude-code-webui in a restart loop with file logging (for Scheduled Task / background).
#
# Foreground test:
#   .\scripts\run-webui-ma-home-daemon.ps1
#
# Install as logon task:
#   .\scripts\install-webui-task.ps1

param(
    [string]$Port = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
    [string]$HostBind = $(if ($env:WEBUI_HOST) { $env:WEBUI_HOST } else { "0.0.0.0" }),
    [int]$RestartSeconds = $(if ($env:WEBUI_RESTART_SECONDS) { [int]$env:WEBUI_RESTART_SECONDS } else { 15 })
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$LogDir = Join-Path $env:USERPROFILE ".config\embodied-claude\logs"
$LogFile = Join-Path $LogDir "webui.log"
$Runner = Join-Path $PSScriptRoot "run-webui-ma-home.ps1"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Add-PathIfExists([string]$Dir) {
    if ($Dir -and (Test-Path $Dir) -and ($env:Path -notlike "*$Dir*")) {
        $env:Path = "$Dir;$env:Path"
    }
}

Add-PathIfExists (Join-Path $env:USERPROFILE ".local\bin")
Add-PathIfExists (Join-Path $env:APPDATA "npm")
Add-PathIfExists "C:\Program Files\nodejs"
Add-PathIfExists "C:\Program Files (x86)\nodejs"

function Write-Log([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Host $line
}

Write-Log "daemon start repo=$Repo port=$Port bind=$HostBind"

while ($true) {
    try {
        Write-Log "starting webui"
        & $Runner -Port $Port -HostBind $HostBind 2>&1 | ForEach-Object {
            Write-Log $_
        }
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) { $exitCode = 0 }
        Write-Log "webui exited code=$exitCode"
    } catch {
        Write-Log "webui error: $($_.Exception.Message)"
    }

    Write-Log "restart in ${RestartSeconds}s"
    Start-Sleep -Seconds $RestartSeconds
}
