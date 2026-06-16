# ntfy.sh setup for ma-home A4g (PC Push when こより enqueues outbound).
#
# ntfy.sh has NO signup for the free tier — the topic name IS the secret.
# Optional later: ntfy Pro to *reserve* a topic + ACL (https://ntfy.sh).
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\setup-ntfy-ma-home.ps1              # generate topic + write env + test
#   .\scripts\setup-ntfy-ma-home.ps1 -Topic koyori-ma-home   # prefix + random suffix
#   .\scripts\setup-ntfy-ma-home.ps1 -TestOnly    # test existing env URL only
#
# After setup:
#   1. Subscribe on phone/PC (ntfy app or https://ntfy.sh)
#   2. .\scripts\restart-presence-ui.ps1
#   3. Smoke: curl POST autonomous-tick miss_companion

param(
    [string]$Topic = "",
    [string]$Server = "https://ntfy.sh",
    [switch]$TestOnly,
    [switch]$SkipEnvWrite,
    [switch]$OpenSubscribePage
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")

$ConfigDir = Join-Path $env:USERPROFILE ".config\embodied-claude"
$LocalEnvFile = Join-Path $ConfigDir "presence-ui.local.env"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

function Get-RandomTopicSuffix {
    param([int]$ByteCount = 12)
    $bytes = [byte[]]::new($ByteCount)
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ([BitConverter]::ToString($bytes) -replace "-", "").ToLowerInvariant()
}

function Normalize-TopicName {
    param([string]$Name)
    $clean = ($Name -replace '[^A-Za-z0-9_-]', '-').Trim('-_')
    if ($clean.Length -gt 64) { $clean = $clean.Substring(0, 64) }
    if (-not $clean) { throw "Topic name empty after normalization" }
    return $clean
}

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

function Set-EnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value,
        [string]$Comment = ""
    )
    $lines = @()
    if (Test-Path $Path) {
        $lines = @(Get-Content $Path -Encoding UTF8)
    }
    $found = $false
    $out = New-Object System.Collections.Generic.List[string]
    $insertedComment = $false
    foreach ($line in $lines) {
        if ($line -match "^#\s*A4g ntfy") { continue }
        if ($line -match "^PRESENCE_OUTBOUND_NTFY_URL=") {
            if (-not $insertedComment -and $Comment) {
                $out.Add("# $Comment")
                $insertedComment = $true
            }
            $out.Add("${Key}=$Value")
            $found = $true
            continue
        }
        $out.Add($line)
    }
    if (-not $found) {
        if ($Comment) {
            $out.Add("")
            $out.Add("# $Comment")
        }
        $out.Add("${Key}=$Value")
    }
    Set-Content -Path $Path -Value $out -Encoding utf8
}

function Send-NtfyTest {
    param(
        [string]$Url,
        [string]$Message,
        [string]$Title = "Koyori",
        [string]$ClickUrl = "http://127.0.0.1:8090/"
    )
    $headers = @{
        Title    = $Title
        Priority = "3"
        Tags     = "koyori,setup"
        Click    = $ClickUrl
    }
    Invoke-RestMethod -Method POST -Uri $Url -Headers $headers -Body ([System.Text.Encoding]::UTF8.GetBytes($Message)) -ContentType "text/plain; charset=utf-8" -TimeoutSec 20
}

Import-PresenceUiLocalEnv
$existingUrl = $env:PRESENCE_OUTBOUND_NTFY_URL
if (-not $existingUrl) {
    $existingUrl = Read-EnvValue -Path $LocalEnvFile -Key "PRESENCE_OUTBOUND_NTFY_URL"
}

if ($TestOnly) {
    if (-not $existingUrl) {
        Write-Error "PRESENCE_OUTBOUND_NTFY_URL not set. Run without -TestOnly first."
    }
    Send-NtfyTest -Url $existingUrl -Message "ntfy テスト — $(Get-Date -Format 'HH:mm:ss')"
    Write-Host "OK: test message sent to $existingUrl"
    Write-Host "Check ntfy-desktop (native toast) or phone. Browser tab alone is not enough on PC."
    exit 0
}

$base = $Server.TrimEnd("/")
if ($Topic) {
    $prefix = Normalize-TopicName $Topic
    if ($prefix.Length -gt 48) { $prefix = $prefix.Substring(0, 48) }
    $topicName = Normalize-TopicName "${prefix}_$(Get-RandomTopicSuffix)"
} else {
    $topicName = Normalize-TopicName "koyori-ma-$(Get-RandomTopicSuffix)"
}

$ntfyUrl = "$base/$topicName"

Write-Host ""
Write-Host "==> ntfy setup (A4g — ma-home PC Push)"
Write-Host ""
Write-Host "ntfy.sh 無料枠: アカウント不要。トピック名が秘密鍵（推測されにくい名前を使う）。"
Write-Host "  topic: $topicName"
Write-Host "  URL:   $ntfyUrl"
Write-Host ""

if (-not $SkipEnvWrite) {
    Set-EnvValue `
        -Path $LocalEnvFile `
        -Key "PRESENCE_OUTBOUND_NTFY_URL" `
        -Value $ntfyUrl `
        -Comment "A4g ntfy — topic is secret; do not commit this file"
    Write-Host "Wrote: $LocalEnvFile"
    Write-Host "  PRESENCE_OUTBOUND_NTFY_URL=$ntfyUrl"
}

Write-Host ""
Write-Host "Sending test notification..."
Send-NtfyTest -Url $ntfyUrl -Message "セットアップ完了。こよりからの着信が届くはずやで。"
Write-Host "OK: test POST succeeded."

Write-Host ""
Write-Host "==> Subscribe (受信側) — どれか1つ"
Write-Host ""
Write-Host "  [A] Web (PC): https://ntfy.sh にアクセス → Subscribe → topic に入力:"
Write-Host "      $topicName"
Write-Host ""
Write-Host "  [B] Android/iOS: Play/App Store で「ntfy」→ Default server = ntfy.sh"
Write-Host "      → + → Subscribe to topic → $topicName"
Write-Host ""
Write-Host ""
Write-Host "PC push: browser notification (Koyori) when 8090 tab open + Win toast when tab closed."
Write-Host "  Both may fire briefly if tab is open in background — set PRESENCE_OUTBOUND_WIN_TOAST=0 to disable Win toast."
Write-Host "  Allow notifications: open http://127.0.0.1:8090/ and click Allow on first visit."
Write-Host "  Subscribe URL (ブラウザで開く): $ntfyUrl"
Write-Host ""

if ($OpenSubscribePage) {
    Start-Process "https://ntfy.sh"
}

Write-Host "Next:"
Write-Host "  1. Open http://127.0.0.1:8090/ and allow browser notifications"
Write-Host "  2. .\scripts\restart-presence-ui.ps1"
Write-Host "  3. .\scripts\setup-ntfy-ma-home.ps1 -TestOnly  (ntfy.sh — phone/Android)"
Write-Host ""
Write-Host "Optional — ntfy Pro で topic 予約 + ACL: https://ntfy.sh (有料)"
Write-Host ""

# Save topic name locally (not secret beyond env, but helps re-subscribe)
$TopicFile = Join-Path $ConfigDir "ntfy-topic.txt"
@(
    "# ma-home ntfy topic (URL also in presence-ui.local.env)"
    "topic=$topicName"
    "url=$ntfyUrl"
    "created=$(Get-Date -Format o)"
) | Set-Content -Path $TopicFile -Encoding utf8
Write-Host "Topic memo: $TopicFile"
