# Shared health helpers for check-mcp-processes, kill-stale, watchdog.

function Find-ClaudeRoot([int]$ProcessId) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 8 -and $proc; $i++) {
        if ($proc.Name -eq "claude.exe") { return $proc.ProcessId }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
    }
    return $null
}

function Get-EmbodiedLogDir {
    Join-Path $env:USERPROFILE ".config\embodied-claude\logs"
}

function Get-WatchdogLogFile {
    Join-Path (Get-EmbodiedLogDir) "watchdog.log"
}

function Write-WatchdogLog {
    param(
        [string]$Message,
        [string]$LogFile = $(Get-WatchdogLogFile)
    )
    $dir = Split-Path $LogFile -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    if ($env:EMBODIED_WATCHDOG_VERBOSE -eq "1") {
        Write-Host $line
    }
}

function Get-MemoryHttpListenerPid {
    param(
        [int]$Port = 18900,
        [string]$BindHost = "127.0.0.1"
    )
    $needle = "${BindHost}:$Port"
    $lines = netstat -ano | Select-String "LISTENING" | Select-String ([regex]::Escape($needle))
    foreach ($match in $lines) {
        $parts = ($match -split "\s+") | Where-Object { $_ }
        if ($parts.Count -ge 1 -and $parts[-1] -match '^\d+$') {
            return [int]$parts[-1]
        }
    }
    return $null
}

function Test-MemoryHttpHealth {
    param(
        [int]$Port = 18900,
        [double]$TimeoutSec = 3.0
    )
    $uri = "http://127.0.0.1:$Port/health"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $resp = Invoke-WebRequest -Uri $uri -TimeoutSec $TimeoutSec -UseBasicParsing
        $sw.Stop()
        if ($resp.StatusCode -ne 200) {
            return @{ Ok = $false; Reason = "HTTP $($resp.StatusCode)"; Ms = $sw.ElapsedMilliseconds }
        }
        $normalized = ($resp.Content -replace "\s", "")
        if ($normalized -notmatch '"ok":true') {
            return @{ Ok = $false; Reason = "ok not true"; Ms = $sw.ElapsedMilliseconds }
        }
        return @{ Ok = $true; Ms = $sw.ElapsedMilliseconds }
    } catch {
        $sw.Stop()
        return @{ Ok = $false; Reason = $_.Exception.Message; Ms = $sw.ElapsedMilliseconds }
    }
}

function Test-AivisHttpHealth {
    param(
        [int]$Port = 10101,
        [double]$TimeoutSec = 3.0
    )
    $uri = "http://127.0.0.1:$Port/version"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $null = Invoke-RestMethod -Uri $uri -TimeoutSec $TimeoutSec
        $sw.Stop()
        return @{ Ok = $true; Ms = $sw.ElapsedMilliseconds }
    } catch {
        $sw.Stop()
        return @{ Ok = $false; Reason = $_.Exception.Message; Ms = $sw.ElapsedMilliseconds }
    }
}

function Test-MemoryHttpRecall {
    param(
        [int]$Port = 18900,
        [double]$TimeoutSec = 20.0,
        [string]$Query = "watchdog"
    )
    $q = [uri]::EscapeDataString($Query)
    $uri = "http://127.0.0.1:$Port/recall?q=$q&n=1"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $null = Invoke-WebRequest -Uri $uri -TimeoutSec $TimeoutSec -UseBasicParsing
        $sw.Stop()
        return @{ Ok = $true; Ms = $sw.ElapsedMilliseconds }
    } catch {
        $sw.Stop()
        return @{ Ok = $false; Reason = $_.Exception.Message; Ms = $sw.ElapsedMilliseconds }
    }
}

function Invoke-ReclaimMemoryHttpPort {
    param(
        [int]$Port = 18900,
        [string]$Repo
    )
    $memoryDir = Join-Path $Repo "memory-mcp"
    if (-not (Test-Path $memoryDir)) {
        return $false
    }
    Push-Location $memoryDir
    try {
        $code = "from memory_mcp.http_sidecar import reclaim_stale_listener; import sys; sys.exit(0 if reclaim_stale_listener($Port) else 1)"
        & uv run --no-sync python -c $code 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        Pop-Location
    }
}

function Stop-ProcessTree {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    $result = Start-Process -FilePath "taskkill.exe" -ArgumentList @("/PID", "$ProcessId", "/T", "/F") `
        -Wait -PassThru -WindowStyle Hidden -ErrorAction SilentlyContinue
    return ($result.ExitCode -eq 0)
}

function Stop-MemoryHttpDaemon {
    param(
        [int]$Port = 18900,
        [string]$Repo,
        [string]$TaskName = "EmbodiedClaude-MemoryHTTP"
    )

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "    Stop-ScheduledTask $TaskName"
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    }

    $daemonPatterns = @(
        "run-memory-daemon\.ps1",
        "run-memory-daemon-hidden\.vbs",
        "memory-mcp-http-daemon"
    )
    $targetPids = @{}
    foreach ($proc in Get-CimInstance Win32_Process -ErrorAction SilentlyContinue) {
        $cmd = $proc.CommandLine
        if (-not $cmd) { continue }
        foreach ($pattern in $daemonPatterns) {
            if ($cmd -match $pattern) {
                $targetPids[$proc.ProcessId] = $true
                break
            }
        }
    }
    foreach ($targetPid in @($targetPids.Keys)) {
        Write-Host "    stopping daemon tree PID $targetPid"
        Stop-ProcessTree -ProcessId $targetPid
    }

    $listenerPid = Get-MemoryHttpListenerPid -Port $Port
    if ($listenerPid) {
        Write-Host "    stopping listener PID $listenerPid"
        Stop-ProcessTree -ProcessId $listenerPid
    }

    Start-Sleep -Seconds 2

    for ($attempt = 0; $attempt -lt 6; $attempt++) {
        if (-not (Get-MemoryHttpListenerPid -Port $Port)) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }

    if ($Repo) {
        Write-Host "    reclaim stale port via memory_mcp.http_sidecar"
        $null = Invoke-ReclaimMemoryHttpPort -Port $Port -Repo $Repo
        Start-Sleep -Seconds 1
    }

    return -not (Get-MemoryHttpListenerPid -Port $Port)
}

function Get-StuckClaudeMemoryStdio {
    param(
        [int]$MinAgeMinutes = 8,
        [double]$CpuSampleSec = 4.0,
        [double]$MaxCpuDelta = 0.05
    )
    $now = Get-Date
    $minAge = [TimeSpan]::FromMinutes($MinAgeMinutes)
    $procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -eq "uv.exe" -and
            $_.CommandLine -match "memory-mcp" -and
            $_.CommandLine -notmatch "http-daemon"
        })
    $stuck = @()
    foreach ($proc in $procs) {
        if (-not $proc.ProcessId) { continue }
        $claudePid = Find-ClaudeRoot $proc.ProcessId
        if (-not $claudePid) { continue }
        try {
            $created = [Management.ManagementDateTimeConverter]::ToDateTime($proc.CreationDate)
        } catch {
            continue
        }
        $age = $now - $created
        if ($age -lt $minAge) { continue }

        $osProc = Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue
        if (-not $osProc) { continue }
        $cpu1 = $osProc.CPU
        Start-Sleep -Seconds $CpuSampleSec
        $osProc2 = Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue
        if (-not $osProc2) { continue }
        $cpuDelta = $osProc2.CPU - $cpu1
        if ($cpuDelta -gt $MaxCpuDelta) { continue }

        $stuck += [PSCustomObject]@{
            PID       = $proc.ProcessId
            ClaudePID = $claudePid
            AgeMin    = [math]::Round($age.TotalMinutes, 1)
            CpuDelta  = $cpuDelta
            Cmd       = $proc.CommandLine
        }
    }
    ,@($stuck)
}
