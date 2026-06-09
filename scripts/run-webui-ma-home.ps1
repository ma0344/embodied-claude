# Start claude-code-webui on ma-home (koyori / Tailscale kiosk).
#
# Uses WinGet claude.exe for --claude-path (Node 24+ spawn EINVAL on .cmd).
# Model/env: this script sets process env; .claude/settings.local.json is read by Claude CLI too.
# CLI with forced --model: .\scripts\run-claude-local.ps1
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
    [string]$HostBind = $(if ($env:WEBUI_HOST) { $env:WEBUI_HOST } else { "0.0.0.0" }),
    [string]$ClaudePath = $(if ($env:CLAUDE_EXE_PATH) { $env:CLAUDE_EXE_PATH } else { "" })
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

function Resolve-ClaudeExe {
    param([string]$Override)

    if ($Override -and (Test-Path $Override)) {
        return (Resolve-Path $Override).Path
    }

    $Candidates = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\claude.exe"),
        (Join-Path $env:USERPROFILE ".local\bin\claude.exe")
    )
    foreach ($Path in $Candidates) {
        if (Test-Path $Path) {
            return (Resolve-Path $Path).Path
        }
    }

    $Where = & where.exe claude 2>$null
    foreach ($Line in $Where) {
        $Line = $Line.Trim()
        if ($Line -match '\.exe$' -and (Test-Path $Line)) {
            return (Resolve-Path $Line).Path
        }
    }

    Write-Error @"
claude.exe not found.

  Install Claude Code (WinGet) or set CLAUDE_EXE_PATH to claude.exe.
  Do not use claude.cmd — claude-code-webui spawn fails with EINVAL on Node 24+.
"@
}

$Settings = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
$Model = if ($Settings.model) { $Settings.model } else { "google/gemma-4-12b-qat" }

if ($Settings.env) {
    foreach ($Prop in $Settings.env.PSObject.Properties) {
        if ($Prop.Value) {
            Set-Item -Path "env:$($Prop.Name)" -Value $Prop.Value
        }
    }
}

if (-not $env:CLAUDE_MODEL) { $env:CLAUDE_MODEL = $Model }
if (-not $env:LMSTUDIO_MODEL) { $env:LMSTUDIO_MODEL = $Model }
if (-not $env:ANTHROPIC_BASE_URL) { $env:ANTHROPIC_BASE_URL = "http://127.0.0.1:1234" }
if (-not $env:CLAUDE_CODE_ATTRIBUTION_HEADER) { $env:CLAUDE_CODE_ATTRIBUTION_HEADER = "0" }
if (-not $env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC) { $env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1" }
if (-not $env:ANTHROPIC_DEFAULT_SONNET_MODEL) { $env:ANTHROPIC_DEFAULT_SONNET_MODEL = $Model }
if (-not $env:ANTHROPIC_DEFAULT_OPUS_MODEL) { $env:ANTHROPIC_DEFAULT_OPUS_MODEL = $Model }
if (-not $env:ANTHROPIC_DEFAULT_HAIKU_MODEL) { $env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $Model }
if (-not $env:CLAUDE_CODE_SUBAGENT_MODEL) { $env:CLAUDE_CODE_SUBAGENT_MODEL = $Model }

if (-not $env:ANTHROPIC_AUTH_TOKEN) {
    $TokenFile = Join-Path $env:USERPROFILE ".config\embodied-claude\lmstudio.token"
    if (Test-Path $TokenFile) {
        $env:ANTHROPIC_AUTH_TOKEN = (Get-Content $TokenFile -Raw).Trim()
    } elseif ($env:LM_STUDIO_TOKEN) {
        $env:ANTHROPIC_AUTH_TOKEN = $env:LM_STUDIO_TOKEN.Trim()
    }
}
if ($env:ANTHROPIC_AUTH_TOKEN -and -not $env:ANTHROPIC_API_KEY) {
    $env:ANTHROPIC_API_KEY = $env:ANTHROPIC_AUTH_TOKEN
}

$ClaudeExe = Resolve-ClaudeExe -Override $ClaudePath

Write-Host "==> claude-code-webui"
Write-Host "    repo:     $Repo"
Write-Host "    settings: $SettingsLocal"
Write-Host "    model:    $Model"
Write-Host "    claude:   $ClaudeExe"
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
Write-Host "Tip: start a NEW chat for QAT (resumed sessions may keep google/gemma-4-12b)."
Write-Host ""

& $Webui.Source --host $HostBind --port $Port --claude-path $ClaudeExe @args
