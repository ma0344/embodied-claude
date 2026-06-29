# VIS-e4b POC — Qwen vs e4b on same JPEG (wifi-cam production prompt).
#
# Env: compare_vision_models.py loads .mcp.json wifi-cam env (same as /see).
# Do NOT parse .env here — PowerShell breaks TAPO_PASSWORD special chars.
#
# LM Studio は通常 vision 1 本だけロード。公平な A/B:
#   .\scripts\run-vis-e4b-poc.ps1 -Image <path> -Isolate
#   → 各モデルを unload/reload してから describe（system prompt も本番同型）

param(
    [switch]$Capture,
    [ValidateSet("window", "desk", "dining")]
    [string]$Preset = "",
    [switch]$Latest,
    [string]$Image = "",
    [string]$QwenModel = "",
    [string]$E4bModel = "google/gemma-4-e4b",
    [string]$OutSuffix = "",
    [switch]$Isolate,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$WifiCam = Join-Path $RepoRoot "wifi-cam-mcp"

if ($QwenModel) { $env:VIS_POC_QWEN_MODEL = $QwenModel }
if ($E4bModel) { $env:VIS_POC_E4B_MODEL = $E4bModel }

$argsList = @()
if ($Capture) { $argsList += "--capture" }
elseif ($Preset) { $argsList += @("--preset", $Preset) }
elseif ($Latest) { $argsList += "--latest" }
elseif ($Image) { $argsList += @("--image", $Image) }
else {
    Write-Host @"
VIS-e4b POC — pick one:

  .\scripts\run-vis-e4b-poc.ps1 -Capture     # live Tapo (uses .mcp.json creds)
  .\scripts\run-vis-e4b-poc.ps1 -Latest      # newest %%TEMP%%\wifi-cam-mcp\capture_*.jpg
  .\scripts\run-vis-e4b-poc.ps1 -Image C:\path\to\frame.jpg

Before running:
  1. LM Studio: load vision model (Qwen first, then e4b)
  2. Optional: -QwenModel / -E4bModel = GET http://127.0.0.1:1234/v1/models ids
  3. Report -> benchmarks\vis-e4b-poc-<date>.md

If -Capture fails with Authority failure:
  - Script now reads TAPO_* from .mcp.json (same as MCP /see)
  - Or skip camera: -Latest after a successful /see, or -Image
"@
    exit 0
}

if ($Json) { $argsList += "--json" }
if ($Isolate) { $argsList += "--isolate" }
if ($OutSuffix) { $argsList += @("--out-suffix", $OutSuffix) }

Push-Location $WifiCam
try {
    uv run python scripts/compare_vision_models.py @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
