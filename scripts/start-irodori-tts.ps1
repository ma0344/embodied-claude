# Start Irodori OpenAI TTS Server (CUDA) on ma-home.
# Repo: C:\Users\ma\src\Irodori-TTS-Server (clone separately)
$ErrorActionPreference = "Stop"
$ServerRoot = if ($env:IRODORI_TTS_SERVER_ROOT) { $env:IRODORI_TTS_SERVER_ROOT } else { "C:\Users\ma\src\Irodori-TTS-Server" }

if (-not (Test-Path $ServerRoot)) {
    Write-Error "Irodori-TTS-Server not found at $ServerRoot. Clone: git clone https://github.com/Aratako/Irodori-TTS-Server.git"
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
