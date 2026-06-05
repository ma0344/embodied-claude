# Initialize desire + automation files for ma-home (Windows).
# Run from repo root:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\setup-automation.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

Write-Host "==> embodied-claude automation setup"
Write-Host "    repo: $Repo"

# desires.conf / desires.json
$desiresConf = Join-Path $Repo "desires.conf"
$desiresSample = Join-Path $Repo "desires.sample.conf"
if (-not (Test-Path $desiresConf) -and (Test-Path $desiresSample)) {
    Copy-Item $desiresSample $desiresConf
    Write-Host "Created desires.conf from desires.sample.conf"
}

$claudeDir = Join-Path $env:USERPROFILE ".claude"
New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null
$desiresJson = Join-Path $claudeDir "desires.json"
if (-not (Test-Path $desiresJson)) {
    @'
{
  "lastTick": 0,
  "desires": {},
  "discomforts": {}
}
'@ | Set-Content -Path $desiresJson -Encoding utf8
    Write-Host "Created $desiresJson"
}

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
Write-Host "  5. Periodic: cd desire-system; uv run desire-updater  (or Task Scheduler)"
