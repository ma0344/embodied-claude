# A/B TTS: AivisSpeech vs Irodori (same phrase). See tts_ab_compare.py
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    python (Join-Path $PSScriptRoot "tts_ab_compare.py")
    $samples = Join-Path $PSScriptRoot "tts-samples"
    Start-Process (Join-Path $samples "aivis-mao-normal-long.wav")
    Start-Sleep -Seconds 4
    $iro = Join-Path $samples "irodori-none-long.wav"
    if (Test-Path $iro) { Start-Process $iro }
}
finally {
    Pop-Location
}
