# Configure ntfy-desktop main-process polling for ma-home Koyori outbound.
#
# ntfy-desktop has TWO subscription layers:
#   1. Embedded web UI (ntfy.sh/app) — in-app list; needs the window / browser tab
#   2. Main process (App -> Settings -> Topics) — Windows native toast via ntfytoast.exe
#
# Web UI subscribe alone does NOT enable native toasts when the browser tab is closed.
# This script writes %APPDATA%\ntfy-desktop\prefs.json topics + instanceURL.
#
# Usage:
#   .\scripts\configure-ntfy-desktop-ma-home.ps1
#   .\scripts\configure-ntfy-desktop-ma-home.ps1 -Topic koyori-ma-home_abc123

param(
    [string]$Topic = "",
    [string]$Server = "https://ntfy.sh",
    [string]$PrefsPath = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")

$ConfigDir = Join-Path $env:USERPROFILE ".config\embodied-claude"
$LocalEnvFile = Join-Path $ConfigDir "presence-ui.local.env"
$TopicFile = Join-Path $ConfigDir "ntfy-topic.txt"

function Read-EnvValue {
    param([string]$Path, [string]$Key)
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path -Encoding UTF8) {
        $t = $line.Trim()
        if ($t -match "^${Key}=(.*)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Get-TopicFromNtfyUrl {
    param([string]$Url)
    if (-not $Url) { return $null }
    try {
        $uri = [Uri]$Url
        $name = $uri.AbsolutePath.Trim("/")
        if ($name) { return $name }
    } catch { }
    return $null
}

function Resolve-KoyoriTopic {
    if ($Topic) { return $Topic.Trim() }

    Import-PresenceUiLocalEnv
    $fromEnv = Get-TopicFromNtfyUrl $env:PRESENCE_OUTBOUND_NTFY_URL
    if ($fromEnv) { return $fromEnv }

    $fromFile = Read-EnvValue -Path $LocalEnvFile -Key "PRESENCE_OUTBOUND_NTFY_URL"
    $fromFile = Get-TopicFromNtfyUrl $fromFile
    if ($fromFile) { return $fromFile }

    if (Test-Path $TopicFile) {
        foreach ($line in Get-Content $TopicFile -Encoding UTF8) {
            if ($line -match "^topic=(.+)$") {
                return $Matches[1].Trim()
            }
        }
    }

    throw "Koyori ntfy topic not found. Run setup-ntfy-ma-home.ps1 or pass -Topic."
}

if (-not $PrefsPath) {
    $PrefsPath = Join-Path $env:APPDATA "ntfy-desktop\prefs.json"
}

$topicName = Resolve-KoyoriTopic
$instanceUrl = $Server.TrimEnd("/")

$prefsDir = Split-Path $PrefsPath -Parent
New-Item -ItemType Directory -Force -Path $prefsDir | Out-Null

$prefsObj = $null
if (Test-Path $PrefsPath) {
    $raw = Get-Content $PrefsPath -Raw -Encoding UTF8
    if ($raw.Trim()) {
        $prefsObj = $raw | ConvertFrom-Json
    }
}
if (-not $prefsObj) {
    $prefsObj = [PSCustomObject]@{}
}

$oldTopics = [string]$prefsObj.topics
$oldInstance = [string]$prefsObj.instanceURL

$prefsObj | Add-Member -NotePropertyName topics -NotePropertyValue $topicName -Force
$prefsObj | Add-Member -NotePropertyName instanceURL -NotePropertyValue $instanceUrl -Force
$pollrate = 15
if ($prefsObj.PSObject.Properties.Name -contains "pollrate") {
    try {
        $current = [int]$prefsObj.pollrate
        if ($current -gt 0 -and $current -le 30) { $pollrate = $current }
    } catch { }
}
$prefsObj | Add-Member -NotePropertyName pollrate -NotePropertyValue $pollrate -Force

($prefsObj | ConvertTo-Json -Depth 4) | Set-Content -Path $PrefsPath -Encoding utf8

Write-Host ""
Write-Host "==> ntfy-desktop native toast config"
Write-Host "  prefs:       $PrefsPath"
Write-Host "  instanceURL: $oldInstance -> $instanceUrl"
Write-Host "  topics:      $oldTopics -> $topicName"
Write-Host ""
Write-Host "Restart ntfy-desktop (tray -> Quit, then Start Menu shortcut)."
Write-Host "Test: .\scripts\setup-ntfy-ma-home.ps1 -TestOnly"
Write-Host "  -> Windows toast should appear even with browser ntfy closed."
Write-Host ""
