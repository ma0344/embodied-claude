# Run Claude Code CLI on ma-home with LM Studio (local Gemma QAT).
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\run-claude-local.ps1
#   .\scripts\run-claude-local.ps1 --continue

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

. (Join-Path $PSScriptRoot "load-lmstudio-env.ps1")

Write-Host "==> claude (LM Studio)"
Write-Host "    repo:  $Repo"
Write-Host "    LM:    $($env:ANTHROPIC_BASE_URL)"
Write-Host "    model: $Model"

Set-Location $Repo
& (Join-Path $PSScriptRoot "claude-lmstudio.ps1") @args
