# Run in PowerShell on ma-home (Windows). LM Studio + Claude Code + MCP.
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\setup-ma-home.ps1

$ErrorActionPreference = "Stop"
$Repo = if ($args[0]) { $args[0] } else { Split-Path $PSScriptRoot -Parent }
if (-not (Test-Path "$Repo\memory-mcp\pyproject.toml")) {
    $Repo = (Get-Location).Path
}
Write-Host "==> embodied-claude setup (ma-home Windows)"
Write-Host "    repo: $Repo"

# uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# ffmpeg (optional, for camera/TTS)
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "WARN: ffmpeg not found. Install: winget install Gyan.FFmpeg"
}

Set-Location $Repo
# install-mcps is bash; run equivalent on Windows
$dirs = @(
    @{ Path = "desire-system"; Extra = "" },
    @{ Path = "memory-mcp"; Extra = "" },
    @{ Path = "system-temperature-mcp"; Extra = "" },
    @{ Path = "tts-mcp"; Extra = "--extra all" },
    @{ Path = "usb-webcam-mcp"; Extra = "" },
    @{ Path = "wifi-cam-mcp"; Extra = "--extra transcribe" },
    @{ Path = "x-mcp"; Extra = "" },
    @{ Path = "sociality-mcp"; Extra = "" }
)
foreach ($d in $dirs) {
    $p = Join-Path $Repo $d.Path
    if (Test-Path "$p\pyproject.toml") {
        Write-Host "==> $($d.Path)"
        Push-Location $p
        $extra = $d.Extra
        if ($extra) { uv sync $extra.Split(" ") } else { uv sync }
        Pop-Location
    }
}

# LM Studio token
$tokenDir = Join-Path $env:USERPROFILE ".config\embodied-claude"
$tokenFile = Join-Path $tokenDir "lmstudio.token"
if (-not (Test-Path $tokenDir)) { New-Item -ItemType Directory -Path $tokenDir -Force | Out-Null }
if (-not (Test-Path $tokenFile)) {
    Write-Host ""
    Write-Host "Create LM Studio API token file:"
    Write-Host "  notepad $tokenFile"
    Write-Host "  (paste token from LM Studio -> Developer -> API tokens, save, close)"
}

# Node + Claude Code
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Host "Install Node.js LTS: winget install OpenJS.NodeJS.LTS"
        Write-Host "Then reopen PowerShell and run this script again."
        exit 1
    }
    Write-Host "Installing Claude Code CLI..."
    npm install -g @anthropic-ai/claude-code
}

# .mcp.json
$mcp = Join-Path $Repo ".mcp.json"
if (-not (Test-Path $mcp)) {
    Copy-Item (Join-Path $Repo ".mcp.json.example") $mcp -ErrorAction SilentlyContinue
    Write-Host "Edit $mcp (use Windows paths in command/args if needed)."
}

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. LM Studio: load google/gemma-4-12b-qat, start Local Server"
Write-Host "  2. .\scripts\run-claude-local.ps1"
Write-Host "  Model change later: docs/lmstudio-model-change.md"
