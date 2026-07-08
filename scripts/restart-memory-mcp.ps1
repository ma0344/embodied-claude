# Restart memory-mcp HTTP daemon (:18900) after code / config changes.

#

# Stops the daemon supervisor + listener first (so uv sync can replace the .exe),

# runs uv sync in memory-mcp, then starts the logon task (EmbodiedClaude-MemoryHTTP)

# and probes /health + /recall.

#

# Admin rights are not required for user-owned logon tasks on localhost.

#

# Usage:

#   .\scripts\restart-memory-mcp.ps1

#   .\scripts\restart-memory-mcp.ps1 -SkipSync

#   .\scripts\restart-memory-mcp.ps1 -Foreground

#   .\scripts\restart-memory-mcp.ps1 -NoRecallProbe



param(

    [int]$Port = $(if ($env:MEMORY_HTTP_PORT) { [int]$env:MEMORY_HTTP_PORT } else { 18900 }),

    [string]$TaskName = "EmbodiedClaude-MemoryHTTP",

    [switch]$SkipSync,

    [switch]$Foreground,

    [switch]$NoRecallProbe

)



$ErrorActionPreference = "Stop"

$Repo = Split-Path $PSScriptRoot -Parent

$MemoryDir = Join-Path $Repo "memory-mcp"

. (Join-Path $PSScriptRoot "embodied-health-lib.ps1")



Write-Host "==> restart-memory-mcp (port $Port)"



if (-not (Test-Path $MemoryDir)) {

    Write-Error "Missing $MemoryDir"

}



Write-Host "    stop daemon (supervisor + :$Port listener)"

$stopped = Stop-MemoryHttpDaemon -Port $Port -Repo $Repo -TaskName $TaskName

if (-not $stopped) {

    Write-Error "Port $Port still in use after stop/reclaim. Try: Get-NetTCPConnection -LocalPort $Port | Format-List"

}



if (-not $SkipSync) {

    Push-Location $MemoryDir

    try {

        Write-Host "    uv sync"

        uv sync

    } finally {

        Pop-Location

    }

}



if ($Foreground) {

    Write-Host "    foreground: run-memory-daemon.ps1"

    & (Join-Path $PSScriptRoot "run-memory-daemon.ps1") -Port $Port

    exit $LASTEXITCODE

}



$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if (-not $task) {

    Write-Error @"

Scheduled task '$TaskName' not found.

  Install: .\scripts\install-memory-daemon-task.ps1

  Or dev:  .\scripts\restart-memory-mcp.ps1 -Foreground

"@

}



Write-Host "    Start-ScheduledTask $TaskName"

Start-ScheduledTask -TaskName $TaskName

Start-Sleep -Seconds 2



$health = Test-MemoryHttpHealth -Port $Port -TimeoutSec 5.0

if (-not $health.Ok) {

    Write-Error "health check failed: $($health.Reason)"

}

Write-Host "    health OK ($($health.Ms) ms)"



if (-not $NoRecallProbe) {

    $recall = Test-MemoryHttpRecall -Port $Port -TimeoutSec 20.0

    if ($recall.Ok) {

        Write-Host "    recall OK ($($recall.Ms) ms)"

    } else {

        Write-Warning "recall probe failed: $($recall.Reason)"

        exit 2

    }

}



Write-Host "OK  http://127.0.0.1:$Port/health"

exit 0

