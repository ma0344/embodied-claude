# Prepare Irodori ref_wav for Style-Bert-VITS2 dataset creation.
#
# Usage:
#   .\scripts\prepare_koyori_sbv2_input.ps1
#   .\scripts\prepare_koyori_sbv2_input.ps1 -CopyToSbV2
#
# Output:
#   .research/aivis-koyori/koyori_mono.wav
#   (optional) Style-Bert-VITS2/input/koyori.wav

param(
    [switch]$CopyToSbV2,
    [string]$SourceWav = "C:\Users\ma\src\Irodori-TTS-Server\voices\koyori.wav",
    [string]$SbV2Root = "C:\Users\ma\src\Style-Bert-VITS2"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$OutDir = Join-Path $Repo ".research\aivis-koyori"
$OutWav = Join-Path $OutDir "koyori_mono.wav"

if (-not (Test-Path $SourceWav)) {
    Write-Error "ref_wav not found: $SourceWav"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Source: $SourceWav"
Write-Host "Output: $OutWav"

# Mono 44.1kHz — SBV2 slice/transcribe friendly
& ffmpeg -y -hide_banner -loglevel error -i $SourceWav -ac 1 -ar 44100 $OutWav
if ($LASTEXITCODE -ne 0) {
    Write-Error "ffmpeg failed"
}

$info = & ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $OutWav
Write-Host ("Prepared mono wav: {0:N1}s" -f [double]$info)

if ($CopyToSbV2) {
    $inputDir = Join-Path $SbV2Root "input"
    if (-not (Test-Path $SbV2Root)) {
        Write-Warning "SBV2 not installed at $SbV2Root — run install-style-bert-vits2.ps1 first"
    } else {
        New-Item -ItemType Directory -Force -Path $inputDir | Out-Null
        $dest = Join-Path $inputDir "koyori.wav"
        Copy-Item -Force $OutWav $dest
        Write-Host "Copied to SBV2 input: $dest"
    }
}

Write-Host ""
Write-Host "Next: Style-Bert-VITS2 App.bat -> Dataset tab"
Write-Host "  model name: koyori"
Write-Host "  input file: koyori.wav (in input/ if -CopyToSbV2)"
Write-Host "  -> slice -> auto transcribe -> Train tab -> preprocess -> train"
Write-Host "See docs/tracks/aivis-koyori-aivmx.md"
