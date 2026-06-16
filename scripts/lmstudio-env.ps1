# Shared LM Studio env helpers for ma-home scripts (dot-source, do not run directly).
#
#   . (Join-Path $PSScriptRoot "lmstudio-env.ps1")

$script:LmStudioChatModelEnvVars = @(
    "ANTHROPIC_MODEL",
    "CLAUDE_MODEL",
    "LMSTUDIO_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL"
)

$script:LmStudioVisionModelEnvVar = "LM_STUDIO_VISION_MODEL"

# Chat + vision (legacy list; prefer ChatModelEnvVars for chat-only updates)
$script:LmStudioModelEnvVars = $script:LmStudioChatModelEnvVars + @($script:LmStudioVisionModelEnvVar)

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
        foreach ($Name in $script:LmStudioChatModelEnvVars) {
            Set-Item -Path "env:$Name" -Value $Model
        }
    } else {
        foreach ($Name in $script:LmStudioChatModelEnvVars) {
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
    if (-not $env:CLAUDE_CODE_DISABLE_THINKING) {
        $env:CLAUDE_CODE_DISABLE_THINKING = "1"
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

function Write-LmStudioJsonFile {
    param(
        [string]$Path,
        [object]$Data
    )

    $Json = ($Data | ConvertTo-Json -Depth 20) + "`n"
    if ($PSVersionTable.PSVersion.Major -ge 6) {
        Set-Content -Path $Path -Value $Json -Encoding utf8NoBOM
    } else {
        $Utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($Path, $Json, $Utf8)
    }
}

function Set-LmStudioModelInSettingsFile {
    param(
        [string]$SettingsLocal,
        [string]$Model,
        [switch]$WhatIf
    )

    if (-not (Test-Path $SettingsLocal)) {
        throw "Missing $SettingsLocal"
    }

    $Settings = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
    $Previous = if ($Settings.model) { [string]$Settings.model } else { "(unset)" }

    if (-not $Settings.env) {
        $Settings | Add-Member -NotePropertyName "env" -NotePropertyValue ([pscustomobject]@{})
    }

    $Changed = @()
    if ($Previous -ne $Model) {
        $Changed += "model: $Previous -> $Model"
    }

    if (-not $WhatIf) {
        $Settings.model = $Model
    }

    foreach ($Name in $script:LmStudioChatModelEnvVars) {
        $Current = $Settings.env.$Name
        if ($Current -ne $Model) {
            $Changed += "$Name`: $Current -> $Model"
            if (-not $WhatIf) {
                $Settings.env | Add-Member -NotePropertyName $Name -NotePropertyValue $Model -Force
            }
        }
    }

    if (-not $WhatIf -and $Changed.Count -gt 0) {
        Write-LmStudioJsonFile -Path $SettingsLocal -Data $Settings
    }

    return [pscustomobject]@{
        Model = $Model
        PreviousModel = $Previous
        Changed = $Changed
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

    $Settings = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
    $Model = if ($Settings.model) { [string]$Settings.model } else { "google/gemma-4-12b-qat" }

    return Set-LmStudioModelInSettingsFile -SettingsLocal $SettingsLocal -Model $Model -WhatIf:$WhatIf
}

function Update-LmStudioMcpJson {
    param(
        [string]$McpJson,
        [string]$Model,
        [switch]$WhatIf
    )

    if (-not (Test-Path $McpJson)) {
        return [pscustomobject]@{ Changed = @(); Skipped = "file missing" }
    }

    $Config = Get-Content $McpJson -Raw | ConvertFrom-Json
    $Changed = @()
    $Targets = @(
        @{ Server = "wifi-cam"; Keys = @("CLAUDE_MODEL") }
    )

    foreach ($Target in $Targets) {
        $Server = $Target.Server
        if (-not $Config.mcpServers.$Server) { continue }
        if (-not $Config.mcpServers.$Server.env) {
            if (-not $WhatIf) {
                $Config.mcpServers.$Server | Add-Member -NotePropertyName "env" -NotePropertyValue ([pscustomobject]@{})
            }
        }
        foreach ($Key in $Target.Keys) {
            $Current = $Config.mcpServers.$Server.env.$Key
            if ($Current -ne $Model) {
                $Changed += "mcpServers.$Server.env.$Key`: $Current -> $Model"
                if (-not $WhatIf) {
                    $Config.mcpServers.$Server.env | Add-Member -NotePropertyName $Key -NotePropertyValue $Model -Force
                }
            }
        }
    }

    if (-not $WhatIf -and $Changed.Count -gt 0) {
        Write-LmStudioJsonFile -Path $McpJson -Data $Config
    }

    return [pscustomobject]@{ Changed = $Changed }
}

function Set-LmStudioVisionModelInSettingsFile {
    param(
        [string]$SettingsLocal,
        [string]$VisionModel,
        [switch]$WhatIf
    )

    if (-not (Test-Path $SettingsLocal)) {
        throw "Missing $SettingsLocal"
    }

    $Settings = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
    if (-not $Settings.env) {
        $Settings | Add-Member -NotePropertyName "env" -NotePropertyValue ([pscustomobject]@{})
    }

    $Key = $script:LmStudioVisionModelEnvVar
    $Current = $Settings.env.$Key
    $Changed = @()
    if ($Current -ne $VisionModel) {
        $Changed += "$Key`: $Current -> $VisionModel"
        if (-not $WhatIf) {
            $Settings.env | Add-Member -NotePropertyName $Key -NotePropertyValue $VisionModel -Force
            Write-LmStudioJsonFile -Path $SettingsLocal -Data $Settings
        }
    }

    return [pscustomobject]@{
        VisionModel = $VisionModel
        Changed = $Changed
    }
}

function Update-LmStudioVisionMcpJson {
    param(
        [string]$McpJson,
        [string]$VisionModel,
        [switch]$WhatIf
    )

    if (-not (Test-Path $McpJson)) {
        return [pscustomobject]@{ Changed = @(); Skipped = "file missing" }
    }

    $Config = Get-Content $McpJson -Raw | ConvertFrom-Json
    $Changed = @()
    $Server = "wifi-cam"
    $Key = $script:LmStudioVisionModelEnvVar

    if (-not $Config.mcpServers.$Server) {
        return [pscustomobject]@{ Changed = @(); Skipped = "wifi-cam missing" }
    }
    if (-not $Config.mcpServers.$Server.env) {
        if (-not $WhatIf) {
            $Config.mcpServers.$Server | Add-Member -NotePropertyName "env" -NotePropertyValue ([pscustomobject]@{})
        }
    }

    $Current = $Config.mcpServers.$Server.env.$Key
    if ($Current -ne $VisionModel) {
        $Changed += "mcpServers.$Server.env.$Key`: $Current -> $VisionModel"
        if (-not $WhatIf) {
            $Config.mcpServers.$Server.env | Add-Member -NotePropertyName $Key -NotePropertyValue $VisionModel -Force
            Write-LmStudioJsonFile -Path $McpJson -Data $Config
        }
    }

    return [pscustomobject]@{ Changed = $Changed }
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
        foreach ($Name in $script:LmStudioChatModelEnvVars) {
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
