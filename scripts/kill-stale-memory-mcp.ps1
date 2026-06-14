# Kill orphan memory-mcp processes (no claude.exe ancestor).
# Safe to run when :18900 is hung or check shows orphan memory-mcp rows.
# Usage: .\scripts\kill-stale-memory-mcp.ps1

$ErrorActionPreference = "SilentlyContinue"

function Find-ClaudeRoot([int]$ProcessId) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId"
    for ($i = 0; $i -lt 8 -and $proc; $i++) {
        if ($proc.Name -eq "claude.exe") { return $proc.ProcessId }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)"
    }
    return $null
}

$targets = @(Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "memory-mcp" -and
    $_.Name -in @("memory-mcp.exe", "uv.exe") -and
    -not (Find-ClaudeRoot $_.ProcessId)
})

if (-not $targets) {
    Write-Host "No orphan memory-mcp / uv processes found."
    exit 0
}

foreach ($proc in $targets) {
    Write-Host "Stopping PID $($proc.ProcessId) ($($proc.Name))"
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Milliseconds 500
Write-Host ""
Write-Host "Re-check:"
& (Join-Path $PSScriptRoot "check-mcp-processes.ps1")
