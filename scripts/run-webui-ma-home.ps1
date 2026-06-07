# Start claude-code-webui on ma-home (koyori / Tailscale kiosk).
#
# LM Studio routing lives in .claude/settings.local.json (copy from settings.local.json.example).
# This script only sets bind address + port for the web UI process.
#
# Prerequisites:
#   - LM Studio: model loaded, server on port 1234
#   - .claude/settings.local.json with env block (ANTHROPIC_*)
#   - npm install -g claude-code-webui
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\run-webui-ma-home.ps1

param(
    [string]$Port = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
    [string]$HostBind = $(if ($env:WEBUI_HOST) { $env:WEBUI_HOST } else { "0.0.0.0" })
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$SettingsLocal = Join-Path $Repo ".claude\settings.local.json"

if (-not (Test-Path $SettingsLocal)) {
    Write-Error @"
Missing $SettingsLocal

  Copy-Item .claude\settings.local.json.example .claude\settings.local.json
  Edit ANTHROPIC_AUTH_TOKEN (or paste lmstudio.token contents).
"@
}

Write-Host "==> claude-code-webui"
Write-Host "    repo:     $Repo"
Write-Host "    settings: $SettingsLocal"
Write-Host "    bind:     ${HostBind}:$Port"

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
Write-Host "Open:   $ProjectUrl"
Write-Host "Koyori: http://<tailscale-ip>:${Port}/projects/..."
Write-Host ""

& $Webui.Source --host $HostBind --port $Port --claude-path $Claude.Source @args
