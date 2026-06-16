# Start AivisSpeech Engine (VOICEVOX-compatible HTTP API on :10101).
$ErrorActionPreference = "Stop"
$EngineRoot = if ($env:AIVIS_ENGINE_ROOT) {
    $env:AIVIS_ENGINE_ROOT
} else {
    "C:\Users\ma\src\AivisSpeech-Engine\Windows-x64"
}

$run = Join-Path $EngineRoot "run.exe"
if (-not (Test-Path $run)) {
    Write-Error "run.exe not found at $run. Extract AivisSpeech-Engine Windows release first."
}

$existing = Get-NetTCPConnection -LocalPort 10101 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    $pid = $existing[0].OwningProcess
    Write-Host "AivisSpeech Engine already listening on http://127.0.0.1:10101 (PID $pid). Skipping start."
    curl -s http://127.0.0.1:10101/version | Write-Host
    return
}

Write-Host "Starting AivisSpeech Engine on http://127.0.0.1:10101 (--use_gpu for RTX/DirectML)..."
Push-Location $EngineRoot
try {
    & $run --use_gpu
}
finally {
    Pop-Location
}
