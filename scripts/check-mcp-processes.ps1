# Embodied Claude MCP health: processes, Claude sessions, HTTP sidecars.
# Usage: .\scripts\check-mcp-processes.ps1

$ErrorActionPreference = "SilentlyContinue"

$EmbodiedMcps = @(
    @{ Key = "memory";        Pattern = "memory-mcp";             HttpPort = 18900; HttpPath = "/health" }
    @{ Key = "sociality";     Pattern = "sociality-mcp";          HttpPort = 18901; HttpPath = "/ingest?text=healthcheck&person_id=ma" }
    @{ Key = "wifi-cam";      Pattern = "wifi-cam-mcp";           HttpPort = $null; HttpPath = $null }
    @{ Key = "tts";           Pattern = "tts-mcp";                HttpPort = $null; HttpPath = $null }
    @{ Key = "system-temperature"; Pattern = "system-temperature-mcp"; HttpPort = $null; HttpPath = $null }
)

function Get-ShortCmd([string]$cmd, [int]$max = 88) {
    if (-not $cmd) { return "" }
    if ($cmd.Length -le $max) { return $cmd }
    return $cmd.Substring(0, $max) + "..."
}

function Find-ClaudeRoot([int]$ProcessId) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId"
    for ($i = 0; $i -lt 8 -and $proc; $i++) {
        if ($proc.Name -eq "claude.exe") { return $proc.ProcessId }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)"
    }
    return $null
}

function Test-HttpSidecar([int]$port, [string]$path, [int]$timeoutSec = 2) {
    $uri = "http://127.0.0.1:$port$path"
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $resp = Invoke-WebRequest -Uri $uri -TimeoutSec $timeoutSec -UseBasicParsing
        $sw.Stop()
        return "ok HTTP $($resp.StatusCode) ($($sw.ElapsedMilliseconds)ms)"
    } catch {
        $msg = $_.Exception.Message
        if ($msg -match "timeout|canceled|タイムアウト") { return "HUNG/TIMEOUT" }
        if ($msg -match "404") { return "ok (reachable, 404)" }
        return "FAIL"
    }
}

Write-Host "== Claude Code sessions ==" -ForegroundColor Cyan
$sessions = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "claude.exe" })
if (-not $sessions) {
    Write-Host "  (no claude.exe — MCP children will be absent or orphaned)" -ForegroundColor Yellow
} else {
    if ($sessions.Count -gt 1) {
        Write-Host "  WARNING: $($sessions.Count) concurrent claude.exe — full MCP set spawned per session." -ForegroundColor Yellow
    }
    $sessions | ForEach-Object {
        [PSCustomObject]@{
            PID = $_.ProcessId
            Cmd = Get-ShortCmd $_.CommandLine 110
        }
    } | Format-Table -AutoSize
}

Write-Host "== Embodied MCP servers (from .mcp.json) ==" -ForegroundColor Cyan

$allProcs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine })
$summary = foreach ($mcp in $EmbodiedMcps) {
    $matchedProcs = @($allProcs | Where-Object { $_.CommandLine -match $mcp.Pattern })
    $uvRoots = @($matchedProcs | Where-Object { $_.Name -eq "uv.exe" })
    $claudeIds = @($uvRoots | ForEach-Object { Find-ClaudeRoot $_.ProcessId } | Where-Object { $_ } | Sort-Object -Unique)

    $httpStatus = "n/a"
    if ($mcp.HttpPort) {
        $listening = netstat -ano | Select-String "127.0.0.1:$($mcp.HttpPort)\s+.*LISTENING"
        if (-not $listening) {
            $httpStatus = "port $($mcp.HttpPort) not listening"
        } else {
            $httpStatus = Test-HttpSidecar $mcp.HttpPort $mcp.HttpPath
        }
    }

    $procStatus = if ($uvRoots.Count -eq 0) {
        "NOT RUNNING"
    } elseif ($uvRoots.Count -eq 1) {
        "running (1 session)"
    } else {
        "running ($($uvRoots.Count) uv spawns — multiple sessions?)"
    }

    [PSCustomObject]@{
        MCP        = $mcp.Key
        Status     = $procStatus
        ClaudePIDs = ($claudeIds -join ", ")
        Http       = $httpStatus
        ProcRows   = $matchedProcs.Count
    }
}

$summary | Format-Table -AutoSize

Write-Host "== Detail (uv.exe spawns only) ==" -ForegroundColor Cyan
$mcpUvPattern = "memory-mcp|sociality-mcp|wifi-cam-mcp|tts-mcp|system-temperature-mcp"
$now = Get-Date
$staleMinutes = 30
$detail = $allProcs |
    Where-Object { $_.Name -eq "uv.exe" -and $_.CommandLine -match $mcpUvPattern } |
    ForEach-Object {
        $claudePid = Find-ClaudeRoot $_.ProcessId
        $created = [Management.ManagementDateTimeConverter]::ToDateTime($_.CreationDate)
        $ageMin = [math]::Round(($now - $created).TotalMinutes, 1)
        $staleFlag = ""
        if ($claudePid -and $_.CommandLine -match "memory-mcp" -and $ageMin -ge $staleMinutes) {
            $staleFlag = "STALE?"
        }
        [PSCustomObject]@{
            PID       = $_.ProcessId
            ClaudePID = $claudePid
            AgeMin    = $ageMin
            Flag      = $staleFlag
            Cmd       = Get-ShortCmd $_.CommandLine
        }
    }
if ($detail) {
    $detail | Format-Table -AutoSize
    $staleRows = @($detail | Where-Object { $_.Flag -eq "STALE?" })
    if ($staleRows) {
        Write-Host "  STALE?: Claude-attached memory-mcp running >= ${staleMinutes}m — if chat shows Booping/Called memory forever, kill session or run kill-stale-memory-mcp.ps1" -ForegroundColor Yellow
    }
} else { Write-Host "  (none)" }

Write-Host "== Orphan memory-mcp (no claude.exe ancestor) ==" -ForegroundColor Cyan
$orphanMemory = $allProcs |
    Where-Object {
        $_.CommandLine -match "memory-mcp" -and
        $_.Name -in @("memory-mcp.exe", "uv.exe") -and
        -not (Find-ClaudeRoot $_.ProcessId)
    } |
    ForEach-Object {
        [PSCustomObject]@{
            PID  = $_.ProcessId
            Name = $_.Name
            Cmd  = Get-ShortCmd $_.CommandLine
        }
    }
$daemonHealth = $null
$memRow = $summary | Where-Object { $_.MCP -eq "memory" } | Select-Object -First 1
if ($memRow -and $memRow.Http -match "^ok HTTP") {
    $daemonHealth = $memRow.Http
}
if ($orphanMemory -and $daemonHealth) {
    Write-Host "  HTTP daemon likely running (health $daemonHealth)" -ForegroundColor Green
    $orphanMemory | Format-Table -AutoSize
} elseif ($orphanMemory) {
    $orphanMemory | Format-Table -AutoSize
    Write-Host "  Run: .\scripts\kill-stale-memory-mcp.ps1" -ForegroundColor Yellow
} else {
    Write-Host "  (none)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Interpretation:" -ForegroundColor DarkGray
Write-Host "  - NOT RUNNING: Claude has not spawned that MCP yet (lazy) or session ended."
Write-Host "  - ProcRows >> 1 per MCP: normal on Windows (uv process tree); count uv.exe rows."
Write-Host "  - memory :18900 HUNG/FAIL: orphans block the port; kill-stale or start HTTP daemon."
Write-Host "  - memory MCP missing in chat: if HTTP daemon runs, .mcp.json needs uv run --no-sync (Windows exe lock)."
Write-Host "  - STALE? memory-mcp on Claude session >=30m: possible silent hang; restart Claude or kill-stale."
Write-Host "  - stdio memory-mcp delegates recall/remember to :18900 when healthy (MEMORY_STDIO_DELEGATE_HTTP=1)."
Write-Host "  - Verify MCP registration: claude mcp list  (memory should be Connected)."
Write-Host "  - HTTP daemon: .\scripts\install-memory-daemon-task.ps1 (logon task, :18900 always on)."
Write-Host "  - Watchdog: .\scripts\install-embodied-watchdog-task.ps1 (every 2m; log watchdog.log)."
Write-Host "  - GET /health is instant; /recall loads E5 and can take seconds on cold start."
Write-Host "  - Hooks: memory HTTP down -> auto_context uses memory.db; social ingest uses social.db in hook."
