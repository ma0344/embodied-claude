# Claude CLI wrapper: always pass --model (fixes webui resume using old gemma-4-12b).
# Used as: claude-code-webui --claude-path .../claude-lmstudio.cmd
#
# Usage:
#   .\scripts\claude-lmstudio.ps1
#   .\scripts\claude-lmstudio.ps1 --continue

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

. (Join-Path $PSScriptRoot "load-lmstudio-env.ps1")

$Claude = Get-Command claude -ErrorAction Stop
Set-Location $Repo

& $Claude.Source --model $Model @args
exit $LASTEXITCODE
