# Gateway direct-action smoke (A3) — hits :8090 without MCP body tools.
#
# Usage:
#   .\scripts\test-gateway-direct-actions.ps1
#   .\scripts\test-gateway-direct-actions.ps1 -SkipObserveRoom   # look_around ~45s
#   .\scripts\test-gateway-direct-actions.ps1 -SkipMissCompanion # no tts-mcp/.env
#   .\scripts\test-gateway-direct-actions.ps1 -BaseUrl http://127.0.0.1:8090

param(
    [string]$BaseUrl = "http://127.0.0.1:8090",
    [switch]$SkipNaturalTick,
    [switch]$SkipObserveRoom,
    [switch]$SkipMissCompanion,
    [switch]$SkipPrivateReflection
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

function Test-TtsConfigured {
    $TtsEnv = Join-Path $Repo "tts-mcp\.env"
    if (Test-Path $TtsEnv) { return $true }
    $LocalEnv = Join-Path $env:USERPROFILE ".config\embodied-claude\presence-ui.local.env"
    if (-not (Test-Path $LocalEnv)) { return $false }
    return [bool](Select-String -Path $LocalEnv -Pattern '^(ELEVENLABS_API_KEY|VOICEVOX_URL)=' -Quiet)
}

function Invoke-Tick {
    param(
        [string]$Label,
        [hashtable]$Body
    )
    Write-Host ""
    Write-Host "==> $Label" -ForegroundColor Cyan
    $json = $Body | ConvertTo-Json -Compress
    try {
        $resp = Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/v1/autonomous-tick" -ContentType "application/json" -Body $json -TimeoutSec 120
    } catch {
        Write-Host "FAIL: $_" -ForegroundColor Red
        return $false
    }
    Write-Host ($resp | ConvertTo-Json -Depth 6)
    if (-not $resp.ok) {
        $detail = if ($resp.detail) { " detail=$($resp.detail)" } else { "" }
        Write-Host "FAIL: ok=false action=$($resp.action)$detail" -ForegroundColor Red
        if ($resp.summary) {
            Write-Host "      summary=$($resp.summary)" -ForegroundColor DarkRed
        }
        return $false
    }
    Write-Host "PASS: $($resp.action)" -ForegroundColor Green
    return $true
}

Write-Host "Gateway direct-action smoke -> $BaseUrl"

try {
    $null = Invoke-RestMethod -Uri "$BaseUrl/api/v1/health" -TimeoutSec 5
} catch {
    Write-Error "8090 not reachable. Start: .\scripts\restart-presence-ui.ps1"
}

if (-not $SkipMissCompanion -and -not (Test-TtsConfigured)) {
    Write-Warning "Skipping miss_companion: no tts-mcp/.env and no TTS keys in presence-ui.local.env"
    Write-Host "        Create tts-mcp/.env from tts-mcp/.env.example (ELEVENLABS_API_KEY or VOICEVOX_URL)" -ForegroundColor DarkYellow
    $SkipMissCompanion = $true
    if (-not $SkipNaturalTick) {
        Write-Warning "Skipping natural tick too (dominant desire may require TTS say)"
        $SkipNaturalTick = $true
    }
}

$passed = 0
$failed = 0

function Register-Result([bool]$Ok) {
    if ($Ok) { $script:passed++ } else { $script:failed++ }
}

if (-not $SkipNaturalTick) {
    Register-Result (Invoke-Tick "natural tick (dominant desire)" @{ person_id = "ma"; trigger = "smoke" })
} else {
    Write-Host ""
    Write-Host "==> natural tick (skipped)" -ForegroundColor DarkGray
}

if (-not $SkipObserveRoom) {
    Register-Result (Invoke-Tick "smoke observe_room (look_around)" @{
            person_id    = "ma"
            trigger      = "smoke_observe"
            smoke_action = "observe_room"
        })
}

if (-not $SkipMissCompanion) {
    Register-Result (Invoke-Tick "smoke miss_companion (TTS)" @{
            person_id    = "ma"
            trigger      = "smoke_say"
            smoke_action = "miss_companion"
            speech_text  = "まー、おる？ うちやで。"
        })
}

if (-not $SkipPrivateReflection) {
    Register-Result (Invoke-Tick "smoke write_private_reflection" @{
            person_id    = "ma"
            trigger      = "smoke_reflect"
            smoke_action = "write_private_reflection"
        })
}

Write-Host ""
Write-Host "Done: $passed passed, $failed failed"
if ($failed -gt 0) { exit 1 }
