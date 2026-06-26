# Switch the LM Studio **chat** model ID (Claude Code / webui). Vision is separate.
#
# Usage:
#   .\scripts\set-lmstudio-model.ps1 -Model google/gemma-4-12b-qat
#   .\scripts\set-lmstudio-model.ps1 -VisionModel qwen/qwen2.5-vl-3b-instruct
#   .\scripts\set-lmstudio-model.ps1 -Model google/gemma-4-12b-qat -VisionModel qwen/qwen2.5-vl-3b-instruct
#
# See docs/ops/lmstudio-model-change.md for the full checklist.

param(
    [string]$Model,
    [string]$VisionModel,
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

if (-not $Model -and -not $VisionModel) {
    Write-Error "Specify -Model (chat) and/or -VisionModel (wifi-cam / gateway vision)."
}

Write-Host "==> set-lmstudio-model"
if ($Model) { Write-Host "    chat:   $Model" }
if ($VisionModel) { Write-Host "    vision: $VisionModel" }
if ($WhatIf) { Write-Host "    mode:   WhatIf (no files written)" }
Write-Host ""

if ($Model) {
    $SettingsResult = Set-LmStudioModelInSettingsFile -SettingsLocal $SettingsLocal -Model $Model -WhatIf:$WhatIf
    Write-Host "  settings.local.json (chat)"
    if ($SettingsResult.Changed.Count -eq 0) {
        Write-Host "    OK: already $Model"
    } else {
        foreach ($Line in $SettingsResult.Changed) {
            if ($WhatIf) { Write-Host "    would set $Line" } else { Write-Host "    set $Line" }
        }
    }

    if (-not $SkipMcp) {
        Write-Host ""
        Write-Host "  .mcp.json (wifi-cam CLAUDE_MODEL)"
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
        Write-Host "  Windows User env (chat only)"
        foreach ($Name in $script:LmStudioChatModelEnvVars) {
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
}

if ($VisionModel) {
    Write-Host ""
    $VisionSettings = Set-LmStudioVisionModelInSettingsFile -SettingsLocal $SettingsLocal -VisionModel $VisionModel -WhatIf:$WhatIf
    Write-Host "  settings.local.json (vision)"
    if ($VisionSettings.Changed.Count -eq 0) {
        Write-Host "    OK: already $VisionModel"
    } else {
        foreach ($Line in $VisionSettings.Changed) {
            if ($WhatIf) { Write-Host "    would set $Line" } else { Write-Host "    set $Line" }
        }
    }

    if (-not $SkipMcp) {
        Write-Host ""
        Write-Host "  .mcp.json (LM_STUDIO_VISION_MODEL)"
        $VisionMcp = Update-LmStudioVisionMcpJson -McpJson $McpJson -VisionModel $VisionModel -WhatIf:$WhatIf
        if ($VisionMcp.Skipped) {
            Write-Host "    skip: $($VisionMcp.Skipped)"
        } elseif ($VisionMcp.Changed.Count -eq 0) {
            Write-Host "    OK: already $VisionModel"
        } else {
            foreach ($Line in $VisionMcp.Changed) {
                if ($WhatIf) { Write-Host "    would set $Line" } else { Write-Host "    set $Line" }
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
if ($Model) {
    Write-Host "  1. LM Studio: load chat model $Model and start Local Server (port 1234)"
}
if ($VisionModel) {
    Write-Host "  2. LM Studio: also load vision $VisionModel (+ mmproj), Concurrent=1"
}
Write-Host "  3. .\scripts\check-lmstudio-model.ps1"
Write-Host "  4. Add vision env to presence-ui.local.env (see docs/ops/lmstudio-model-change.md)"
Write-Host "  5. .\scripts\restart-presence-ui.ps1"
Write-Host ""
Write-Host "Docs: docs/ops/lmstudio-model-change.md"
