# Initialize desire + automation files for ma-home (Windows).
# Run from repo root:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\setup-automation.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

Write-Host "==> embodied-claude automation setup"
Write-Host "    repo: $Repo"

# desires.json (v2 homeostasis — desire-system)
$claudeDir = Join-Path $env:USERPROFILE ".claude"
New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null
$desiresJson = Join-Path $claudeDir "desires.json"
if (-not (Test-Path $desiresJson)) {
    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    @"
{
  "updated_at": "$now",
  "desires": {
    "observe_room": 0.0,
    "look_outside": 0.0,
    "browse_curiosity": 0.0,
    "miss_companion": 0.0,
    "identity_coherence": 0.0,
    "cognitive_load": 0.0,
    "literary_wander": 0.0
  },
  "discomforts": {
    "observe_room": 0.0,
    "look_outside": 0.0,
    "browse_curiosity": 0.0,
    "miss_companion": 0.0,
    "identity_coherence": 0.0,
    "cognitive_load": 0.0,
    "literary_wander": 0.0
  },
  "dominant": "observe_room"
}
"@ | Set-Content -Path $desiresJson -Encoding utf8
    Write-Host "Created v2 $desiresJson"
}

$desireSystem = Join-Path $Repo "desire-system"
if (Test-Path $desireSystem) {
    Write-Host "Run initial desire-updater:"
    Write-Host "  cd desire-system; uv run desire-updater"
}

# Legacy desires.conf is deprecated — do not copy desires.sample.conf

# settings.local.json from example (merge hooks manually if you already have one)
$settingsWindows = Join-Path $Repo ".claude\settings.windows.json.example"
$settingsLocal = Join-Path $Repo ".claude\settings.local.json"
if (-not (Test-Path $settingsLocal) -and (Test-Path $settingsWindows)) {
    Copy-Item $settingsWindows $settingsLocal
    Write-Host "Created .claude\settings.local.json from settings.windows.json.example"
} elseif (Test-Path $settingsLocal) {
    Write-Host "Keep existing .claude\settings.local.json"
    Write-Host "  If UserPromptSubmit hook errors: use run_auto_context.cmd in the hook command"
}

Write-Host ""
Write-Host "Next:"
Write-Host "  1. Add desire-system (+ optional usb-webcam) to .mcp.json — see .mcp.json.windows.example"
Write-Host "  2. Copy SOUL.md.example -> SOUL.md and edit"
Write-Host "  3. Restart Claude Code"
Write-Host "  4. User messages: /talk  or ask agent to follow talk.md flow"
Write-Host "  5. Periodic autonomous tick:"
Write-Host "       .\scripts\install-autonomous-tick-task.ps1"
Write-Host "     (desire-updater + POST /api/v1/autonomous-tick every 15m)"
Write-Host "  6. Logon TTS (kiosk voice):"
Write-Host "       .\scripts\install-irodori-tts-task.ps1"
