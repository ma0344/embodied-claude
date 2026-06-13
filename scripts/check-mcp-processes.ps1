# Embodied Claude MCP health: processes, Claude sessions, HTTP sidecars.
# Usage: .\scripts\check-mcp-processes.ps1

$ErrorActionPreference = "SilentlyContinue"

$EmbodiedMcps = @(
    @{ Key = "memory";        Pattern = "memory-mcp";             HttpPort = 18900; HttpPath = "/recall?q=health&n=1" }
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

function Test-HttpSidecar([int]$port, [string]$path, [int]$timeoutSec = 4) {
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
$detail = $allProcs |
    Where-Object { $_.Name -eq "uv.exe" -and $_.CommandLine -match $mcpUvPattern } |
    ForEach-Object {
        [PSCustomObject]@{
            PID       = $_.ProcessId
            ClaudePID = Find-ClaudeRoot $_.ProcessId
            Cmd       = Get-ShortCmd $_.CommandLine
        }
    }
if ($detail) { $detail | Format-Table -AutoSize } else { Write-Host "  (none)" }

Write-Host ""
Write-Host "Interpretation:" -ForegroundColor DarkGray
Write-Host "  - NOT RUNNING: Claude has not spawned that MCP yet (lazy) or session ended."
Write-Host "  - ProcRows >> 1 per MCP: normal on Windows (uv process tree); count uv.exe rows."
Write-Host "  - memory :18900 HUNG: restart chat session or kill stale memory-mcp tree."
Write-Host "  - Hooks: memory HTTP down -> auto_context uses memory.db; social ingest uses social.db in hook."
