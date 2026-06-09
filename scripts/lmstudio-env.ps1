# Shared LM Studio env helpers for ma-home scripts (dot-source, do not run directly).
#
#   . (Join-Path $PSScriptRoot "lmstudio-env.ps1")

$script:LmStudioModelEnvVars = @(
    "ANTHROPIC_MODEL",
    "CLAUDE_MODEL",
    "LMSTUDIO_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "LM_STUDIO_VISION_MODEL"
)

function Get-LmStudioModelFromSettings {
    param(
        [string]$SettingsLocal,
        [string]$Default = "google/gemma-4-12b-qat"
    )

    if (-not (Test-Path $SettingsLocal)) {
        return $Default
    }

    $Settings = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
    if ($Settings.model) {
        return [string]$Settings.model
    }
    return $Default
}

function Set-LmStudioProcessEnv {
    param(
        [string]$Model,
        [object]$SettingsEnv,
        [switch]$ForceModel
    )

    if ($SettingsEnv) {
        foreach ($Prop in $SettingsEnv.PSObject.Properties) {
            if ($Prop.Value) {
                Set-Item -Path "env:$($Prop.Name)" -Value $Prop.Value
            }
        }
    }

    if ($ForceModel) {
        foreach ($Name in $script:LmStudioModelEnvVars) {
            Set-Item -Path "env:$Name" -Value $Model
        }
    } else {
        foreach ($Name in $script:LmStudioModelEnvVars) {
            if (-not (Get-Item "env:$Name" -ErrorAction SilentlyContinue)) {
                Set-Item -Path "env:$Name" -Value $Model
            }
        }
    }

    if (-not $env:ANTHROPIC_BASE_URL) { $env:ANTHROPIC_BASE_URL = "http://127.0.0.1:1234" }
    if (-not $env:CLAUDE_CODE_ATTRIBUTION_HEADER) { $env:CLAUDE_CODE_ATTRIBUTION_HEADER = "0" }
    if (-not $env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC) {
        $env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
    }

    if (-not $env:ANTHROPIC_AUTH_TOKEN) {
        $TokenFile = Join-Path $env:USERPROFILE ".config\embodied-claude\lmstudio.token"
        if (Test-Path $TokenFile) {
            $env:ANTHROPIC_AUTH_TOKEN = (Get-Content $TokenFile -Raw).Trim()
        } elseif ($env:LM_STUDIO_TOKEN) {
            $env:ANTHROPIC_AUTH_TOKEN = $env:LM_STUDIO_TOKEN.Trim()
        }
    }
    if ($env:ANTHROPIC_AUTH_TOKEN -and -not $env:ANTHROPIC_API_KEY) {
        $env:ANTHROPIC_API_KEY = $env:ANTHROPIC_AUTH_TOKEN
    }
}

function Sync-LmStudioSettingsFile {
    param(
        [string]$SettingsLocal,
        [switch]$WhatIf
    )

    if (-not (Test-Path $SettingsLocal)) {
        throw "Missing $SettingsLocal"
    }

    $Raw = Get-Content $SettingsLocal -Raw
    $Settings = $Raw | ConvertFrom-Json
    $Model = if ($Settings.model) { [string]$Settings.model } else { "google/gemma-4-12b-qat" }

    if (-not $Settings.PSObject.Properties["model"]) {
        $Settings | Add-Member -NotePropertyName "model" -NotePropertyValue $Model
    } else {
        $Settings.model = $Model
    }

    if (-not $Settings.env) {
        $Settings | Add-Member -NotePropertyName "env" -NotePropertyValue ([pscustomobject]@{})
    }

    $Changed = @()
    foreach ($Name in $script:LmStudioModelEnvVars) {
        $Current = $Settings.env.$Name
        if ($Current -ne $Model) {
            $Changed += "$Name`: $Current -> $Model"
            if (-not $WhatIf) {
                $Settings.env | Add-Member -NotePropertyName $Name -NotePropertyValue $Model -Force
            }
        }
    }

    if (-not $WhatIf -and $Changed.Count -gt 0) {
        ($Settings | ConvertTo-Json -Depth 10) + "`n" | Set-Content -Path $SettingsLocal -Encoding utf8NoBOM
    }

    return [pscustomobject]@{
        Model = $Model
        Changed = $Changed
    }
}

function Test-LmStudioSettingsMismatch {
    param([string]$SettingsLocal)

    if (-not (Test-Path $SettingsLocal)) {
        return @()
    }

    $Settings = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
    $Model = if ($Settings.model) { [string]$Settings.model } else { return @() }
    $Mismatches = @()

    if ($Settings.env) {
        foreach ($Name in $script:LmStudioModelEnvVars) {
            $Val = $Settings.env.$Name
            if ($Val -and $Val -ne $Model) {
                $Mismatches += [pscustomobject]@{
                    Name = $Name
                    Value = $Val
                    Expected = $Model
                }
            }
        }
    }

    return $Mismatches
}
