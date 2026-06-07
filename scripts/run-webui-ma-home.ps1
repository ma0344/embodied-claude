# Start claude-code-webui on ma-home with LM Studio (local Gemma) instead of Anthropic cloud.
#
# Prerequisites:
#   - LM Studio: model loaded, server on port 1234 (Anthropic-compatible /v1/messages)
#   - npm install -g claude-code-webui
#   - claude CLI on PATH (same env that passed: claude -p "..." --model google/gemma-4-12b)
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\run-webui-ma-home.ps1
#
# Koyori kiosk (Tailscale):
#   http://<ma-home-tailscale-ip>:8080/projects/C:/Users/ma/src/embodied-claude

param(
    [string]$Port = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
    [string]$HostBind = $(if ($env:WEBUI_HOST) { $env:WEBUI_HOST } else { "0.0.0.0" }),
    [string]$Model = $(if ($env:LMSTUDIO_MODEL) { $env:LMSTUDIO_MODEL } else { "google/gemma-4-12b" }),
    [string]$LmBaseUrl = $(if ($env:ANTHROPIC_BASE_URL) { $env:ANTHROPIC_BASE_URL } else { "http://127.0.0.1:1234" })
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

Write-Host "==> claude-code-webui (LM Studio / local model)"
Write-Host "    repo:  $Repo"
Write-Host "    model: $Model"
Write-Host "    LM:    $LmBaseUrl"
Write-Host "    bind:  ${HostBind}:$Port"

# LM Studio API token (when Require Authentication is ON)
$TokenFile = Join-Path $env:USERPROFILE ".config\embodied-claude\lmstudio.token"
if ($env:ANTHROPIC_AUTH_TOKEN) {
    $AuthToken = $env:ANTHROPIC_AUTH_TOKEN.Trim()
} elseif (Test-Path $TokenFile) {
    $AuthToken = (Get-Content $TokenFile -Raw).Trim()
    Write-Host "    auth:  lmstudio.token"
} else {
    $AuthToken = "lmstudio"
    Write-Host "    auth:  placeholder 'lmstudio' (set lmstudio.token if LM Studio requires auth)"
}

$env:ANTHROPIC_BASE_URL = $LmBaseUrl
$env:ANTHROPIC_AUTH_TOKEN = $AuthToken
$env:CLAUDE_CODE_ATTRIBUTION_HEADER = "0"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $Model
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $Model
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $Model

$Claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $Claude) {
    Write-Error "claude CLI not found on PATH"
}

$Webui = Get-Command claude-code-webui -ErrorAction SilentlyContinue
if (-not $Webui) {
    Write-Error "claude-code-webui not found. Run: npm install -g claude-code-webui"
}

Set-Location $Repo

$ProjectUrl = "http://localhost:${Port}/projects/$($Repo -replace '\\','/')"
Write-Host ""
Write-Host "Open: $ProjectUrl"
Write-Host "Koyori: http://<tailscale-ip>:${Port}/projects/..."
Write-Host ""

& $Webui.Source --host $HostBind --port $Port --claude-path $Claude.Source @args
