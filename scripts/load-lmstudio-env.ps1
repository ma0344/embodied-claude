# Dot-source to configure LM Studio env for Claude Code (ma-home).
# Sets $Model and exports ANTHROPIC_* / CLAUDE_* vars.
#
#   . .\scripts\load-lmstudio-env.ps1

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = Split-Path $PSScriptRoot -Parent
}

$DefaultModel = "google/gemma-4-12b-qat"
$SettingsLocal = Join-Path $Repo ".claude\settings.local.json"

$Model = $DefaultModel
if ($env:CLAUDE_MODEL) {
    $Model = $env:CLAUDE_MODEL
} elseif ($env:LMSTUDIO_MODEL) {
    $Model = $env:LMSTUDIO_MODEL
}

if (Test-Path $SettingsLocal) {
    try {
        $json = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
        if ($json.model) { $Model = [string]$json.model }
        if ($json.env.CLAUDE_MODEL) { $Model = [string]$json.env.CLAUDE_MODEL }
        if ($json.env.ANTHROPIC_BASE_URL) {
            $env:ANTHROPIC_BASE_URL = [string]$json.env.ANTHROPIC_BASE_URL
        }
        if ($json.env.ANTHROPIC_AUTH_TOKEN -and $json.env.ANTHROPIC_AUTH_TOKEN -notmatch 'PASTE_') {
            $env:ANTHROPIC_AUTH_TOKEN = [string]$json.env.ANTHROPIC_AUTH_TOKEN
        }
    } catch {
        Write-Warning "Could not parse $SettingsLocal : $_"
    }
}

$env:ANTHROPIC_BASE_URL = if ($env:ANTHROPIC_BASE_URL) { $env:ANTHROPIC_BASE_URL } else { "http://127.0.0.1:1234" }
$env:CLAUDE_CODE_ATTRIBUTION_HEADER = "0"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $Model
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $Model
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $Model
$env:CLAUDE_CODE_SUBAGENT_MODEL = $Model
$env:CLAUDE_MODEL = $Model
$env:LMSTUDIO_MODEL = $Model

$TokenFile = Join-Path $env:USERPROFILE ".config\embodied-claude\lmstudio.token"
if (-not $env:ANTHROPIC_AUTH_TOKEN) {
    if (Test-Path $TokenFile) {
        $env:ANTHROPIC_AUTH_TOKEN = (Get-Content $TokenFile -Raw).Trim()
    } elseif ($env:LM_STUDIO_TOKEN) {
        $env:ANTHROPIC_AUTH_TOKEN = $env:LM_STUDIO_TOKEN.Trim()
    } else {
        $env:ANTHROPIC_AUTH_TOKEN = "lmstudio"
    }
}
$env:ANTHROPIC_AUTH_TOKEN = $env:ANTHROPIC_AUTH_TOKEN.Trim()
$env:ANTHROPIC_API_KEY = $env:ANTHROPIC_AUTH_TOKEN
