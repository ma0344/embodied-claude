# Print which model names Claude Code / MCP will send to LM Studio.
# Run on ma-home before starting claude:
#   .\scripts\check-lmstudio-model.ps1

$Repo = Split-Path $PSScriptRoot -Parent
$SettingsLocal = Join-Path $Repo ".claude\settings.local.json"

Write-Host "==> LM Studio model check (ma-home)"
Write-Host ""

$Vars = @(
    "CLAUDE_MODEL",
    "LMSTUDIO_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "LM_STUDIO_VISION_MODEL"
)

foreach ($name in $Vars) {
    $val = [Environment]::GetEnvironmentVariable($name, "Process")
    if (-not $val) { $val = [Environment]::GetEnvironmentVariable($name, "User") }
    if (-not $val) { $val = [Environment]::GetEnvironmentVariable($name, "Machine") }
    if ($val) {
        Write-Host "  env $name = $val"
    }
}

if (Test-Path $SettingsLocal) {
    Write-Host ""
    Write-Host "  settings.local.json:"
    $json = Get-Content $SettingsLocal -Raw | ConvertFrom-Json
    if ($json.model) { Write-Host "    model = $($json.model)" }
    if ($json.env) {
        foreach ($prop in $json.env.PSObject.Properties) {
            if ($prop.Name -match "MODEL|CLAUDE_MODEL") {
                Write-Host "    env.$($prop.Name) = $($prop.Value)"
            }
        }
    }
} else {
    Write-Host ""
    Write-Host "  WARN: missing $SettingsLocal"
}

Write-Host ""
Write-Host "Expected: google/gemma-4-12b-qat everywhere."
Write-Host "If you see google/gemma-4-12b (no -qat), fix settings.local.json or User env vars."
Write-Host "WebUI: restart with .\scripts\run-webui-ma-home.ps1 (claude-lmstudio.js wrapper)."
Write-Host "Resumed CLI sessions: .\scripts\run-claude-local.ps1 --continue  (wrapper adds --model)"
