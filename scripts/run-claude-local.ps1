# Run from repo root in PowerShell (ma-home Windows).
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\run-claude-local.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

$env:ANTHROPIC_BASE_URL = if ($env:ANTHROPIC_BASE_URL) { $env:ANTHROPIC_BASE_URL } else { "http://127.0.0.1:1234" }
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"

$tokenFile = Join-Path $env:USERPROFILE ".config\embodied-claude\lmstudio.token"
if (Test-Path $tokenFile) {
    $env:ANTHROPIC_AUTH_TOKEN = (Get-Content $tokenFile -Raw).Trim()
} elseif (-not $env:LM_STUDIO_TOKEN) {
    Write-Warning "No token at $tokenFile — set LM_STUDIO_TOKEN or create the file."
    $env:ANTHROPIC_AUTH_TOKEN = "lmstudio"
} else {
    $env:ANTHROPIC_AUTH_TOKEN = $env:LM_STUDIO_TOKEN
}
$env:ANTHROPIC_API_KEY = $env:ANTHROPIC_AUTH_TOKEN

$model = if ($env:CLAUDE_MODEL) { $env:CLAUDE_MODEL } else { "google/gemma-4-12b" }

Write-Host "ANTHROPIC_BASE_URL=$($env:ANTHROPIC_BASE_URL)"
Write-Host "model=$model"
Write-Host "repo=$Repo"

Set-Location $Repo
& claude --model $model @args
