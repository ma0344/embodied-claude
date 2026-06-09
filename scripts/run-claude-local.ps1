# Run Claude Code CLI on ma-home with LM Studio (local Gemma).
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\run-claude-local.ps1
#
# LM Studio env can also live in .claude/settings.local.json ("env" block).

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

$Model = if ($env:CLAUDE_MODEL) { $env:CLAUDE_MODEL } elseif ($env:LMSTUDIO_MODEL) { $env:LMSTUDIO_MODEL } else { "google/gemma-4-12b-qat" }

$env:ANTHROPIC_BASE_URL = if ($env:ANTHROPIC_BASE_URL) { $env:ANTHROPIC_BASE_URL } else { "http://127.0.0.1:1234" }
$env:CLAUDE_CODE_ATTRIBUTION_HEADER = "0"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
$env:CLAUDE_CODE_DISABLE_THINKING = "1"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $Model
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $Model
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $Model
$env:CLAUDE_CODE_SUBAGENT_MODEL = $Model
$env:CLAUDE_MODEL = $Model
$env:LMSTUDIO_MODEL = $Model

$TokenFile = Join-Path $env:USERPROFILE ".config\embodied-claude\lmstudio.token"
if ($env:ANTHROPIC_AUTH_TOKEN) {
    $AuthToken = $env:ANTHROPIC_AUTH_TOKEN.Trim()
} elseif (Test-Path $TokenFile) {
    $AuthToken = (Get-Content $TokenFile -Raw).Trim()
} elseif ($env:LM_STUDIO_TOKEN) {
    $AuthToken = $env:LM_STUDIO_TOKEN.Trim()
} else {
    Write-Warning "No token at $TokenFile — using placeholder 'lmstudio'."
    $AuthToken = "lmstudio"
}

$env:ANTHROPIC_AUTH_TOKEN = $AuthToken
$env:ANTHROPIC_API_KEY = $AuthToken

Write-Host "==> claude (LM Studio)"
Write-Host "    repo:  $Repo"
Write-Host "    LM:    $($env:ANTHROPIC_BASE_URL)"
Write-Host "    model: $Model"

Set-Location $Repo
& claude --model $Model @args
