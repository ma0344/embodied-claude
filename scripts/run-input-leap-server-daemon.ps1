# Keep Input Leap server running (single instance). For Scheduled Task / logon.
#
# Foreground test:
#   .\scripts\run-input-leap-server-daemon.ps1
#
# Install logon task:
#   .\scripts\install-input-leap-task.ps1

param(
    [string]$InstallDir = $(if ($env:INPUT_LEAP_DIR) { $env:INPUT_LEAP_DIR } else { "C:\Programs\InputLeap" }),
    [string]$Config = "",
    [int]$PollSeconds = 30
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

if (-not $Config) {
    $Config = Join-Path $InstallDir "default.sgc"
}

$ServerExe = Join-Path $InstallDir "input-leaps.exe"
$LogDir = Join-Path $env:USERPROFILE ".config\embodied-claude\logs"
$LogFile = Join-Path $LogDir "input-leap-server.log"

if (-not (Test-Path $ServerExe)) {
    throw "input-leaps.exe not found: $ServerExe (set INPUT_LEAP_DIR?)"
}
if (-not (Test-Path $Config)) {
    throw "config not found: $Config"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Host $line
}

function Start-InputLeapServer {
    $args = @(
        "-c", $Config,
        "--disable-client-cert-checking",
        "--disable-crypto",
        "--debug", "INFO"
    )
    Write-Log "starting input-leaps $($args -join ' ')"
    Start-Process `
        -FilePath $ServerExe `
        -ArgumentList $args `
        -WorkingDirectory $InstallDir `
        -WindowStyle Hidden
}

function Sync-InputLeapServer {
    $procs = @(Get-Process -Name input-leaps -ErrorAction SilentlyContinue)
    if ($procs.Count -gt 1) {
        Write-Log "found $($procs.Count) input-leaps — stopping duplicates"
        $procs | Stop-Process -Force
        Start-Sleep -Seconds 2
        $procs = @()
    }
    if ($procs.Count -eq 0) {
        Start-InputLeapServer
        return
    }
    $listening = Get-NetTCPConnection -LocalPort 24800 -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -eq $procs[0].Id }
    if (-not $listening) {
        Write-Log "input-leaps pid=$($procs[0].Id) not listening on 24800 — restarting"
        $procs | Stop-Process -Force
        Start-Sleep -Seconds 1
        Start-InputLeapServer
    }
}

Write-Log "daemon start installDir=$InstallDir config=$Config"

while ($true) {
    try {
        Sync-InputLeapServer
    } catch {
        Write-Log "error: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $PollSeconds
}
