# Start AivisSpeech Engine (VOICEVOX-compatible HTTP API on :10101).
#
# Foreground (blocks — dev):
#   .\scripts\start-aivis-tts.ps1
#
# Background (logon task / watchdog):
#   .\scripts\start-aivis-tts.ps1 -Background
#
# Log (background): %USERPROFILE%\.config\embodied-claude\logs\aivis-tts.log

param(
    [switch]$Background,
    [int]$WaitSeconds = 90
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$EngineRoot = if ($env:AIVIS_ENGINE_ROOT) {
    $env:AIVIS_ENGINE_ROOT
} else {
    "C:\Users\ma\src\AivisSpeech-Engine\Windows-x64"
}

$run = Join-Path $EngineRoot "run.exe"
if (-not (Test-Path $run)) {
    Write-Error "run.exe not found at $run. Extract AivisSpeech-Engine Windows release first."
}

function Test-AivisListening {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:10101/version" -TimeoutSec 3
        return $true
    } catch {
        return $false
    }
}

function Write-AivisLog([string]$Message) {
    $dir = Join-Path $env:USERPROFILE ".config\embodied-claude\logs"
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $log = Join-Path $dir "aivis-tts.log"
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $log -Value $line -Encoding utf8
    Write-Host $line
}

if (Test-AivisListening) {
    $existing = Get-NetTCPConnection -LocalPort 10101 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    $pidText = if ($existing) { "PID $($existing.OwningProcess)" } else { "unknown PID" }
    Write-AivisLog "AivisSpeech already listening on http://127.0.0.1:10101 ($pidText)"
    exit 0
}

if ($Background) {
    Write-AivisLog "Starting AivisSpeech in background (--use_gpu) from $EngineRoot"
    Start-Process -FilePath $run -ArgumentList "--use_gpu" -WorkingDirectory $EngineRoot -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-AivisListening) {
            Write-AivisLog "AivisSpeech ready on http://127.0.0.1:10101"
            exit 0
        }
        Start-Sleep -Seconds 2
    }
    Write-AivisLog "ERROR: AivisSpeech did not become ready within ${WaitSeconds}s"
    exit 1
}

Write-Host "Starting AivisSpeech Engine on http://127.0.0.1:10101 (--use_gpu for RTX/DirectML)..."
Push-Location $EngineRoot
try {
    & $run --use_gpu
}
finally {
    Pop-Location
}
