# Start Irodori OpenAI TTS Server (CUDA) on ma-home.
# Repo: C:\Users\ma\src\Irodori-TTS-Server (clone separately)
#
# Foreground (blocks — dev):
#   .\scripts\start-irodori-tts.ps1
#
# Background (logon task / watchdog):
#   .\scripts\start-irodori-tts.ps1 -Background
#
# Model switch + restart (updates Irodori-TTS-Server/.env, stops :8088, starts again):
#   .\scripts\restart-irodori-tts-500m.ps1
#   .\scripts\restart-irodori-tts-600m.ps1
#
# Log (background): %USERPROFILE%\.config\embodied-claude\logs\irodori-tts.log
#
# 参照声 WAV: voices/<voice_id>.wav（例: koyori.wav）。差し替え → docs/backlog-ma-home.md § Irodori 参照声 WAV の差し替え
#
# Do not run Aivis (:10101) and Irodori (:8088) as dual defaults — coexistence is discouraged.
# To disable Aivis Task: .\scripts\install-aivis-tts-task.ps1 -Uninstall
#   or: Disable-ScheduledTask -TaskName EmbodiedClaude-AivisTTS

param(
    [switch]$Background,
    [int]$WaitSeconds = 180
)

$ErrorActionPreference = "Stop"
$ServerRoot = if ($env:IRODORI_TTS_SERVER_ROOT) {
    $env:IRODORI_TTS_SERVER_ROOT
} else {
    "C:\Users\ma\src\Irodori-TTS-Server"
}

if (-not (Test-Path $ServerRoot)) {
    Write-Error "Irodori-TTS-Server not found at $ServerRoot. Clone: git clone https://github.com/Aratako/Irodori-TTS-Server.git"
}

function Test-IrodoriListening {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:8088/health" -TimeoutSec 3
        return $true
    } catch {
        return $false
    }
}

function Write-IrodoriLog([string]$Message) {
    $dir = Join-Path $env:USERPROFILE ".config\embodied-claude\logs"
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $log = Join-Path $dir "irodori-tts.log"
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $log -Value $line -Encoding utf8
    Write-Host $line
}

if (Test-IrodoriListening) {
    $existing = Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    $pidText = if ($existing) { "PID $($existing.OwningProcess)" } else { "unknown PID" }
    Write-IrodoriLog "Irodori TTS already listening on http://127.0.0.1:8088 ($pidText)"
    exit 0
}

if ($Background) {
    Write-IrodoriLog "Starting Irodori TTS in background from $ServerRoot"
    # --extra cu128 is required; plain `uv run` swaps in CPU torch on Windows.
    Start-Process -FilePath "uv" `
        -ArgumentList @("run", "--extra", "cu128", "python", "-m", "irodori_openai_tts", "--host", "127.0.0.1", "--port", "8088") `
        -WorkingDirectory $ServerRoot `
        -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-IrodoriListening) {
            Write-IrodoriLog "Irodori TTS ready on http://127.0.0.1:8088"
            exit 0
        }
        Start-Sleep -Seconds 3
    }
    Write-IrodoriLog "ERROR: Irodori TTS did not become ready within ${WaitSeconds}s"
    exit 1
}

Push-Location $ServerRoot
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "First run: uv sync --extra cu128 (may take several minutes)..."
        uv sync --extra cu128
    }
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example — edit voices/ and IRODORI_DEFAULT_VOICE as needed."
    }
    Write-Host "Starting Irodori TTS on http://127.0.0.1:8088 (preload loads model on startup)..."
    # --extra cu128 is required; plain `uv run` swaps in CPU torch on Windows.
    uv run --extra cu128 python -m irodori_openai_tts --host 127.0.0.1 --port 8088
}
finally {
    Pop-Location
}
