# Switch the LM Studio model ID used by Claude Code / webui / wifi-cam vision on ma-home.
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\set-lmstudio-model.ps1 -Model google/gemma-4-12b-qat
#   .\scripts\set-lmstudio-model.ps1 -Model google/gemma-4-12b-qat -WhatIf
#
# See docs/lmstudio-model-change.md for the full checklist.

param(
    [Parameter(Mandatory = $true)]
    [string]$Model,
    [switch]$WhatIf,
    [switch]$SkipMcp,
    [switch]$UpdateUserEnv
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$SettingsLocal = Join-Path $Repo ".claude\settings.local.json"
$McpJson = Join-Path $Repo ".mcp.json"

. (Join-Path $PSScriptRoot "lmstudio-env.ps1")

if (-not (Test-Path $SettingsLocal)) {
    Write-Error @"
Missing $SettingsLocal

  Copy-Item .claude\settings.local.json.example .claude\settings.local.json
  Edit ANTHROPIC_AUTH_TOKEN, then re-run this script.
"@
}

Write-Host "==> set-lmstudio-model"
Write-Host "    target: $Model"
if ($WhatIf) { Write-Host "    mode:   WhatIf (no files written)" }
Write-Host ""

$SettingsResult = Set-LmStudioModelInSettingsFile -SettingsLocal $SettingsLocal -Model $Model -WhatIf:$WhatIf
Write-Host "  settings.local.json"
if ($SettingsResult.Changed.Count -eq 0) {
    Write-Host "    OK: already $Model"
} else {
    foreach ($Line in $SettingsResult.Changed) {
        if ($WhatIf) { Write-Host "    would set $Line" } else { Write-Host "    set $Line" }
    }
}

if (-not $SkipMcp) {
    Write-Host ""
    Write-Host "  .mcp.json (wifi-cam vision)"
    $McpResult = Update-LmStudioMcpJson -McpJson $McpJson -Model $Model -WhatIf:$WhatIf
    if ($McpResult.Skipped) {
        Write-Host "    skip: $($McpResult.Skipped)"
    } elseif ($McpResult.Changed.Count -eq 0) {
        Write-Host "    OK: already $Model"
    } else {
        foreach ($Line in $McpResult.Changed) {
            if ($WhatIf) { Write-Host "    would set $Line" } else { Write-Host "    set $Line" }
        }
    }
}

if ($UpdateUserEnv) {
    Write-Host ""
    Write-Host "  Windows User env"
    foreach ($Name in $script:LmStudioModelEnvVars) {
        $Current = [Environment]::GetEnvironmentVariable($Name, "User")
        if ($Current -ne $Model) {
            if ($WhatIf) {
                Write-Host "    would set User\$Name = $Model (was $Current)"
            } else {
                [Environment]::SetEnvironmentVariable($Name, $Model, "User")
                Write-Host "    set User\$Name = $Model"
            }
        }
    }
}

Write-Host ""
if ($WhatIf) {
    Write-Host "Re-run without -WhatIf to apply."
    exit 0
}

Write-Host "Next:"
Write-Host "  1. LM Studio: load $Model and start Local Server (port 1234)"
Write-Host "  2. .\scripts\check-lmstudio-model.ps1"
Write-Host "  3. Restart claude-code-webui if running: .\scripts\run-webui-ma-home.ps1"
Write-Host "  4. Send a test message; LM Studio log should show `"model`": `"$Model`""
Write-Host ""
Write-Host "Docs: docs/lmstudio-model-change.md"
