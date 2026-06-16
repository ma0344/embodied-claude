# Run desire-updater (optional) then POST /api/v1/autonomous-tick (A4f).
#
# Foreground:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\run-autonomous-tick.ps1
#
# Scheduled Task:
#   .\scripts\install-autonomous-tick-task.ps1
#
# Log:
#   %USERPROFILE%\.config\embodied-claude\logs\autonomous-tick.log

param(
    [string]$BaseUrl = $(if ($env:PRESENCE_BASE_URL) { $env:PRESENCE_BASE_URL } else { "http://127.0.0.1:8090" }),
    [string]$PersonId = $(if ($env:PRESENCE_PERSON_ID) { $env:PRESENCE_PERSON_ID } else { "ma" }),
    [string]$Trigger = $(if ($env:PRESENCE_AUTONOMOUS_TRIGGER) { $env:PRESENCE_AUTONOMOUS_TRIGGER } else { "scheduled_tick" }),
    [switch]$SkipDesireUpdater,
    [int]$TimeoutSec = 180
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $env:USERPROFILE ".config\embodied-claude\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "autonomous-tick.log"

function Write-TickLog {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

if (-not $SkipDesireUpdater) {
    $DesireDir = Join-Path $Repo "desire-system"
    if (Test-Path $DesireDir) {
        try {
            Push-Location $DesireDir
            $updaterOut = & uv run desire-updater 2>&1
            foreach ($row in @($updaterOut)) {
                Write-TickLog "[desire-updater] $row"
            }
        } catch {
            Write-TickLog "[desire-updater] FAIL: $($_.Exception.Message)"
        } finally {
            Pop-Location
        }
    } else {
        Write-TickLog "[desire-updater] skip (desire-system not found)"
    }
}

$body = @{
    person_id = $PersonId
    trigger   = $Trigger
} | ConvertTo-Json -Compress

try {
    $resp = Invoke-RestMethod `
        -Method POST `
        -Uri "$BaseUrl/api/v1/autonomous-tick" `
        -ContentType "application/json; charset=utf-8" `
        -Body $body `
        -TimeoutSec $TimeoutSec

    $summary = [string]$resp.summary
    if ($summary.Length -gt 160) {
        $summary = $summary.Substring(0, 160) + "..."
    }
    Write-TickLog "[tick] ok=$($resp.ok) move=$($resp.primary_move) action=$($resp.action) summary=$summary"
    if (-not $resp.ok) {
        exit 1
    }
} catch {
    Write-TickLog "[tick] FAIL: $($_.Exception.Message)"
    exit 1
}
