# Run memory-mcp HTTP daemon (POST /remember, GET /recall, GET /health on :18900).
#
# Foreground test:
#   .\scripts\run-memory-daemon.ps1
#
# Install as logon task:
#   .\scripts\install-memory-daemon-task.ps1

param(
    [string]$Port = $(if ($env:MEMORY_HTTP_PORT) { $env:MEMORY_HTTP_PORT } else { "18900" }),
    [int]$RestartSeconds = $(if ($env:MEMORY_DAEMON_RESTART_SECONDS) { [int]$env:MEMORY_DAEMON_RESTART_SECONDS } else { 15 })
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$MemoryDir = Join-Path $Repo "memory-mcp"
$LogDir = Join-Path $env:USERPROFILE ".config\embodied-claude\logs"
$LogFile = Join-Path $LogDir "memory-daemon.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Add-PathIfExists([string]$Dir) {
    if ($Dir -and (Test-Path $Dir) -and ($env:Path -notlike "*$Dir*")) {
        $env:Path = "$Dir;$env:Path"
    }
}

Add-PathIfExists (Join-Path $env:USERPROFILE ".local\bin")

function Write-Log([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Host $line
}

$env:MEMORY_HTTP_PORT = $Port
$env:MEMORY_EMBEDDING_DEVICE = $(if ($env:MEMORY_EMBEDDING_DEVICE) { $env:MEMORY_EMBEDDING_DEVICE } else { "cpu" })
$env:UV_PYTHON = $(if ($env:UV_PYTHON) { $env:UV_PYTHON } else { "3.12" })

Write-Log "memory daemon start repo=$Repo port=$Port device=$($env:MEMORY_EMBEDDING_DEVICE)"

while ($true) {
    try {
        Write-Log "starting memory-mcp-http-daemon"
        Push-Location $MemoryDir
        try {
            uv run --no-sync memory-mcp-http-daemon 2>&1 | ForEach-Object { Write-Log $_ }
            $exitCode = $LASTEXITCODE
            if ($null -eq $exitCode) { $exitCode = 0 }
            Write-Log "memory daemon exited code=$exitCode"
        } finally {
            Pop-Location
        }
    } catch {
        Write-Log "memory daemon error: $($_.Exception.Message)"
    }

    Write-Log "restart in ${RestartSeconds}s"
    Start-Sleep -Seconds $RestartSeconds
}
