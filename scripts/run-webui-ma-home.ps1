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

. (Join-Path $PSScriptRoot "lmstudio-env.ps1")

$Settings = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
$Model = Get-LmStudioModelFromSettings -SettingsLocal $SettingsLocal

# Top-level "model" must win over stale env.*MODEL keys (CLAUDE_MODEL overrides "model").
Set-LmStudioProcessEnv -Model $Model -SettingsEnv $Settings.env -ForceModel

$Mismatches = Test-LmStudioSettingsMismatch -SettingsLocal $SettingsLocal
if ($Mismatches.Count -gt 0) {
    Write-Warning "settings.local.json env MODEL keys differ from `"model`": run .\scripts\sync-lmstudio-settings.ps1"
}

$UserSettings = Join-Path $env:USERPROFILE ".claude\settings.json"
if (Test-Path $UserSettings) {
    try {
        $UserJson = Get-Content $UserSettings -Raw | ConvertFrom-Json
        if ($UserJson.model -and $UserJson.model -ne $Model) {
            Write-Warning "~/.claude/settings.json model=$($UserJson.model) — project local uses $Model for new sessions."
        }
    } catch {
        # ignore parse errors
    }
}

$ClaudeExe = Resolve-ClaudeExe -Override $ClaudePath

$PortListeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($PortListeners.Count -gt 0) {
    $OwnerPid = $PortListeners[0].OwningProcess
    $Proc = Get-Process -Id $OwnerPid -ErrorAction SilentlyContinue
    $ProcLabel = if ($Proc) { "$($Proc.ProcessName) (PID $OwnerPid)" } else { "PID $OwnerPid" }
    $ProjectUrl = "http://localhost:${Port}/projects/$($Repo -replace '\\','/')"
    $Task = Get-ScheduledTask -TaskName "EmbodiedClaude-WebUI" -ErrorAction SilentlyContinue

    Write-Host "==> claude-code-webui"
    Write-Host ""
    Write-Host "Port $Port is already in use by $ProcLabel."
    if ($Task -and $Task.State -eq "Running") {
        Write-Host "Scheduled task EmbodiedClaude-WebUI is running — webui is already up."
    } else {
        Write-Host "Another webui (or process) is already listening."
    }
    Write-Host ""
    Write-Host "Open:   $ProjectUrl"
    Write-Host ""
    Write-Host "To restart:"
    Write-Host "  .\scripts\restart-webui-ma-home.ps1"
    exit 0
}

Write-Host "==> claude-code-webui"
Write-Host "    repo:     $Repo"
Write-Host "    settings: $SettingsLocal"
Write-Host "    model:    $Model"
Write-Host "    claude:   $ClaudeExe"
Write-Host "    bind:     ${HostBind}:$Port"

$Webui = Get-Command claude-code-webui-ma-home -ErrorAction SilentlyContinue
if (-not $Webui) {
    $Webui = Get-Command claude-code-webui -ErrorAction SilentlyContinue
}
if (-not $Webui) {
    Write-Error @"
claude-code-webui not found.

  Fork (recommended — appendSystemPrompt for presence-ui):
    .\scripts\setup-claude-code-webui-fork.ps1

  Upstream fallback:
    npm install -g claude-code-webui
"@
}
if ($Webui.Source -match "claude-code-webui-ma-home") {
    Write-Host "    webui:    ma-home fork (appendSystemPrompt)"
} else {
    Write-Warning "Using upstream claude-code-webui — sociality may enrich user message text. Run .\scripts\setup-claude-code-webui-fork.ps1"
}

Set-Location $Repo

$ProjectUrl = "http://localhost:${Port}/projects/$($Repo -replace '\\','/')"
Write-Host ""
Write-Host "Open:   $ProjectUrl"
Write-Host "Koyori: http://<tailscale-ip>:${Port}/projects/..."
Write-Host ""
Write-Host "Tip: NEW chat only (History resumes google/gemma-4-12b). If mismatch warning above: .\scripts\sync-lmstudio-settings.ps1"
Write-Host ""

& $Webui.Source --host $HostBind --port $Port --claude-path $ClaudeExe @args
