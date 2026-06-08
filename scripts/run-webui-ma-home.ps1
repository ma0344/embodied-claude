# Start claude-code-webui on ma-home (koyori / Tailscale kiosk).
#
# Uses claude-lmstudio.cmd (npm-shim shape → claude-lmstudio.js) so webui can spawn node
# and every turn gets --model google/gemma-4-12b-qat.
#
# Prerequisites:
#   - LM Studio: google/gemma-4-12b-qat loaded, server on port 1234
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
$ClaudeWrapper = Join-Path $PSScriptRoot "claude-lmstudio.cmd"

if (-not (Test-Path $SettingsLocal)) {
    Write-Error @"
Missing $SettingsLocal

  Copy-Item .claude\settings.local.json.example .claude\settings.local.json
  Edit ANTHROPIC_AUTH_TOKEN (or paste lmstudio.token contents).
"@
}

. (Join-Path $PSScriptRoot "load-lmstudio-env.ps1")

Write-Host "==> claude-code-webui"
Write-Host "    repo:     $Repo"
Write-Host "    settings: $SettingsLocal"
Write-Host "    model:    $Model"
Write-Host "    claude:   $ClaudeWrapper"
Write-Host "    bind:     ${HostBind}:$Port"

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
Write-Host "Tip: old webui chats may have been started on gemma-4-12b; wrapper forces QAT on each turn."
Write-Host "      Run .\scripts\check-lmstudio-model.ps1 if LM Studio loads the wrong weights."
Write-Host ""

& $Webui.Source --host $HostBind --port $Port --claude-path $ClaudeWrapper @args
