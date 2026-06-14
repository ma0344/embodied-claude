# Watchdog: memory HTTP health/recall + stuck stdio memory-mcp recovery.
#
# Usage:
#   .\scripts\watch-embodied-health.ps1
#   .\scripts\watch-embodied-health.ps1 -DryRun
#   .\scripts\watch-embodied-health.ps1 -StdioHangMinutes 5
#
# Log: %USERPROFILE%\.config\embodied-claude\logs\watchdog.log
#
# Install periodic run:
#   .\scripts\install-embodied-watchdog-task.ps1

param(
    [switch]$DryRun,
    [int]$MemoryPort = $(if ($env:MEMORY_HTTP_PORT) { [int]$env:MEMORY_HTTP_PORT } else { 18900 }),
    [double]$HealthTimeoutSec = 3.0,
    [double]$RecallTimeoutSec = 20.0,
    [int]$StdioHangMinutes = $(if ($env:EMBODIED_WATCHDOG_STDIO_HANG_MIN) { [int]$env:EMBODIED_WATCHDOG_STDIO_HANG_MIN } else { 5 }),
    [double]$CpuSampleSec = 4.0,
    [switch]$SkipRecallProbe,
    [string]$MemoryDaemonTask = "EmbodiedClaude-MemoryHTTP",
    [string]$LogFile = ""
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "embodied-health-lib.ps1")

if (-not $LogFile) { $LogFile = Get-WatchdogLogFile }

$remediated = $false

function Invoke-Remediate {
    param(
        [string]$Action,
        [scriptblock]$Block
    )
    Write-WatchdogLog -Message "ACTION: $Action$(if ($DryRun) { ' (dry-run)' } else { '' })" -LogFile $LogFile
    if ($DryRun) {
        return
    }
    & $Block
    $script:remediated = $true
}

Write-WatchdogLog -Message "watchdog tick port=$MemoryPort stdio_hang_min=$StdioHangMinutes" -LogFile $LogFile

# ── 1. Memory HTTP /health ─────────────────────────────────────
$health = Test-MemoryHttpHealth -Port $MemoryPort -TimeoutSec $HealthTimeoutSec
if ($health.Ok) {
    Write-WatchdogLog -Message "health OK ($($health.Ms)ms)" -LogFile $LogFile
} else {
    Write-WatchdogLog -Message "health FAIL: $($health.Reason)" -LogFile $LogFile
    Invoke-Remediate "reclaim unhealthy listener on :$MemoryPort" {
        $reclaimed = Invoke-ReclaimMemoryHttpPort -Port $MemoryPort -Repo $Repo
        if (-not $reclaimed) {
            $pidListener = Get-MemoryHttpListenerPid -Port $MemoryPort
            if ($pidListener) {
                Write-WatchdogLog -Message "taskkill listener PID $pidListener" -LogFile $LogFile
                Stop-ProcessTree -ProcessId $pidListener | Out-Null
            }
        }
        $task = Get-ScheduledTask -TaskName $MemoryDaemonTask -ErrorAction SilentlyContinue
        if ($task) {
            Write-WatchdogLog -Message "Start-ScheduledTask $MemoryDaemonTask" -LogFile $LogFile
            Start-ScheduledTask -TaskName $MemoryDaemonTask
        } else {
            Write-WatchdogLog -Message "WARN: task $MemoryDaemonTask missing; run install-memory-daemon-task.ps1" -LogFile $LogFile
        }
        Start-Sleep -Seconds 2
    }
}

# ── 2. Recall probe (daemon warm path) ─────────────────────────
if (-not $SkipRecallProbe) {
    $health2 = Test-MemoryHttpHealth -Port $MemoryPort -TimeoutSec $HealthTimeoutSec
    if ($health2.Ok) {
        $recall = Test-MemoryHttpRecall -Port $MemoryPort -TimeoutSec $RecallTimeoutSec
        if ($recall.Ok) {
            Write-WatchdogLog -Message "recall OK ($($recall.Ms)ms)" -LogFile $LogFile
        } else {
            Write-WatchdogLog -Message "recall FAIL: $($recall.Reason)" -LogFile $LogFile
            Invoke-Remediate "restart memory daemon after recall failure" {
                $pidListener = Get-MemoryHttpListenerPid -Port $MemoryPort
                if ($pidListener) {
                    Write-WatchdogLog -Message "taskkill listener PID $pidListener (recall fail)" -LogFile $LogFile
                    Stop-ProcessTree -ProcessId $pidListener | Out-Null
                }
                Start-Sleep -Seconds 1
                $task = Get-ScheduledTask -TaskName $MemoryDaemonTask -ErrorAction SilentlyContinue
                if ($task) {
                    Start-ScheduledTask -TaskName $MemoryDaemonTask
                }
                Start-Sleep -Seconds 2
            }
        }
    }
}

# ── 3. Orphan memory-mcp (no claude ancestor) ──────────────────
function Find-ClaudeRootLocal([int]$ProcessId) { Find-ClaudeRoot $ProcessId }

$orphans = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match "memory-mcp" -and
        $_.Name -in @("memory-mcp.exe", "uv.exe") -and
        -not (Find-ClaudeRootLocal $_.ProcessId)
    })
foreach ($proc in $orphans) {
    # http-daemon orphans are expected when healthy; skip if health OK and cmd is daemon
    if ($proc.CommandLine -match "http-daemon") {
        $h = Test-MemoryHttpHealth -Port $MemoryPort -TimeoutSec $HealthTimeoutSec
        if ($h.Ok) {
            Write-WatchdogLog -Message "orphan daemon PID $($proc.ProcessId) healthy — keep" -LogFile $LogFile
            continue
        }
    }
    Write-WatchdogLog -Message "orphan memory PID $($proc.ProcessId) unhealthy or non-daemon" -LogFile $LogFile
    Invoke-Remediate "kill orphan memory PID $($proc.ProcessId)" {
        Stop-ProcessTree -ProcessId $proc.ProcessId | Out-Null
    }
}

# ── 4. Stuck Claude-attached stdio memory-mcp ───────────────────
$stuck = @(Get-StuckClaudeMemoryStdio -MinAgeMinutes $StdioHangMinutes -CpuSampleSec $CpuSampleSec)
foreach ($row in $stuck) {
    if (-not $row -or -not $row.PID) { continue }
    Write-WatchdogLog -Message "stuck stdio memory PID $($row.PID) claude=$($row.ClaudePID) age=$($row.AgeMin)m cpu_delta=$($row.CpuDelta)" -LogFile $LogFile
    Invoke-Remediate "kill stuck stdio memory PID $($row.PID)" {
        Stop-ProcessTree -ProcessId $row.PID | Out-Null
    }
}

# ── 5. Post-check ───────────────────────────────────────────────
$final = Test-MemoryHttpHealth -Port $MemoryPort -TimeoutSec $HealthTimeoutSec
if ($final.Ok) {
    Write-WatchdogLog -Message "post-check health OK" -LogFile $LogFile
    if ($remediated) { exit 1 }
    exit 0
}

Write-WatchdogLog -Message "post-check health STILL FAIL: $($final.Reason)" -LogFile $LogFile
exit 2
