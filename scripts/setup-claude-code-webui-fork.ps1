# Build and link claude-code-webui-ma-home fork (appendSystemPrompt support).
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\setup-claude-code-webui-fork.ps1
#
# After success:
#   claude-code-webui-ma-home --version
#   .\scripts\restart-webui-ma-home.ps1

param(
    [switch]$SkipLink
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$ForkRoot = Join-Path $Repo "claude-code-webui-fork"
$ForkBackend = Join-Path $ForkRoot "backend"
$ForkFrontend = Join-Path $ForkRoot "frontend"

$MaHomeOrigin = "https://github.com/ma0344/claude-code-webui-ma-home.git"

function Initialize-ForkRemotes {
    param([string]$ForkDir, [string]$PushOrigin)

    Push-Location $ForkDir
    try {
        if (-not (Test-Path ".git")) {
            return
        }

        $remotes = @(git remote)
        $hasUpstream = $remotes -contains "upstream"
        $hasOrigin = $remotes -contains "origin"
        if (-not $hasUpstream -and $hasOrigin) {
            $originUrl = & git remote get-url origin
            if ($originUrl -like "*sugyan/claude-code-webui*") {
                & git remote rename origin upstream | Out-Null
            }
        }

        $remotes = @(git remote)
        if ($remotes -notcontains "origin") {
            & git remote add origin $PushOrigin | Out-Null
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $ForkBackend)) {
    Write-Host "    clone:    $ForkRoot (upstream, full history)"
    git clone https://github.com/sugyan/claude-code-webui.git $ForkRoot
    Initialize-ForkRemotes -ForkDir $ForkRoot -PushOrigin $MaHomeOrigin
    Write-Host "    remotes:  upstream=sugyan, origin=ma0344/claude-code-webui-ma-home"
    Write-Host "    NOTE: create empty GitHub repo before first push (see claude-code-webui-fork/FORK.md)"
}

Initialize-ForkRemotes -ForkDir $ForkRoot -PushOrigin $MaHomeOrigin

$Node = Get-Command node -ErrorAction SilentlyContinue
if (-not $Node) {
    Write-Error "Node.js is required (>= 20). Install from https://nodejs.org/"
}

Write-Host "==> setup-claude-code-webui-fork"

if (Test-Path $ForkFrontend) {
    Push-Location $ForkFrontend
    try {
        Write-Host "    frontend: $ForkFrontend"
        if (-not (Test-Path "node_modules")) {
            Write-Host "    npm install (frontend)"
            npm install
        }
        Write-Host "    npm run build (frontend)"
        npm run build
    } finally {
        Pop-Location
    }
}

Push-Location $ForkBackend
try {
    Write-Host "    backend:  $ForkBackend"

    if (-not (Test-Path "node_modules")) {
        Write-Host "    npm install (backend)"
        npm install
    }

    Write-Host "    npm test"
    npm test

    Write-Host "    npm run build (backend)"
    npm run build

    if (-not $SkipLink) {
        Write-Host "    npm link (global claude-code-webui-ma-home)"
        npm link
    }
} finally {
    Pop-Location
}

$Linked = Get-Command claude-code-webui-ma-home -ErrorAction SilentlyContinue
if ($Linked) {
    Write-Host ""
    Write-Host "OK: $($Linked.Source)"
    Write-Host ""
    Write-Host "Restart webui:"
    Write-Host "  .\scripts\restart-webui-ma-home.ps1"
} elseif ($SkipLink) {
    Write-Host ""
    Write-Host "Built. Run locally:"
    Write-Host "  node claude-code-webui-fork\backend\dist\cli\node.js --host 0.0.0.0 --port 8080"
} else {
    Write-Warning "npm link completed but claude-code-webui-ma-home not on PATH."
    Write-Host "Ensure %APPDATA%\npm is on PATH, then open a new terminal."
}
