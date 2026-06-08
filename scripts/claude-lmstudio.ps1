# Claude CLI wrapper: always pass --model (fixes webui resume using old gemma-4-12b).
# Prefer claude-lmstudio.js (webui-compatible); this script loads LM Studio env first.
#
# Usage:
#   .\scripts\claude-lmstudio.ps1
#   .\scripts\claude-lmstudio.ps1 --continue

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

. (Join-Path $PSScriptRoot "load-lmstudio-env.ps1")

$Node = Get-Command node -ErrorAction Stop
Set-Location $Repo

& $Node.Source (Join-Path $PSScriptRoot "claude-lmstudio.js") @args
exit $LASTEXITCODE
