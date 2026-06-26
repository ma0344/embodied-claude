# C1: enable or disable Native chat PoC on :8090 (claude-code-server, no :8080).
#
# Enable (writes ~/.config/embodied-claude/presence-ui.local.env + restart):
#   .\scripts\c1-native-poc.ps1 -Enable
#
# Disable (remove flag + restart):
#   .\scripts\c1-native-poc.ps1 -Disable
#
# Docs: docs/archive/c1-native-poc.md

param(
    [switch]$Enable,
    [switch]$Disable,
    [switch]$Status,
    [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" })
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")

$LocalEnvFile = Join-Path $env:USERPROFILE ".config\embodied-claude\presence-ui.local.env"

function Get-NativePocEnabled {
    if (-not (Test-Path $LocalEnvFile)) { return $false }
    foreach ($line in Get-Content $LocalEnvFile -Encoding UTF8) {
        $t = $line.Trim()
        if ($t -match '^\s*#' -or -not $t) { continue }
        if ($t -match '^PRESENCE_NATIVE_CHAT\s*=\s*(.+)$') {
            $v = $Matches[1].Trim().Trim('"').Trim("'")
            return $v -match '^(1|true|yes)$'
        }
    }
    return $false
}

function Write-LocalEnv([bool]$NativeOn) {
    $Dir = Split-Path $LocalEnvFile -Parent
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    if ($NativeOn) {
        @(
            "# presence-ui optional flags (loaded by run-presence-ui-worker.ps1)"
            "PRESENCE_NATIVE_CHAT=1"
            "# PRESENCE_CCS_PASSWORD=koyori-poc"
        ) | Set-Content -Path $LocalEnvFile -Encoding UTF8
    } elseif (Test-Path $LocalEnvFile) {
        Remove-Item $LocalEnvFile -Force
    }
}

if (-not $Enable -and -not $Disable -and -not $Status) {
    Write-Host @"
C1 Native PoC toggle

  .\scripts\c1-native-poc.ps1 -Enable    # turn on /poc/native + restart :8090
  .\scripts\c1-native-poc.ps1 -Disable   # back to gateway-only
  .\scripts\c1-native-poc.ps1 -Status

See docs/archive/c1-native-poc.md
"@
    exit 0
}

if ($Status) {
    $on = Get-NativePocEnabled
    Write-Host "Native PoC: $(if ($on) { 'ENABLED' } else { 'disabled' })"
    Write-Host "Config: $(if (Test-Path $LocalEnvFile) { $LocalEnvFile } else { '(none)' })"
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 3
        Write-Host "Health mode: $($h.details.mode)  native_chat=$($h.details.native_chat)"
    } catch {
        Write-Host "Health: :$Port not reachable"
    }
    exit 0
}

if ($Enable -and $Disable) {
    Write-Error "Use -Enable or -Disable, not both"
}

Write-LocalEnv -NativeOn:$Enable
$Label = if ($Enable) { "ENABLE Native PoC" } else { "DISABLE Native PoC" }
Write-Host "==> C1 $Label"

& (Join-Path $PSScriptRoot "sync-presence-deps.ps1")
& (Join-Path $PSScriptRoot "restart-presence-ui.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Start-Sleep -Seconds 2
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 10
    Write-Host ""
    Write-Host "Health: mode=$($h.details.mode) native_chat=$($h.details.native_chat)"
    if ($Enable -and -not $h.details.native_chat) {
        Write-Warning "native_chat still false — check presence-ui.log"
        exit 1
    }
} catch {
    Write-Warning "Could not reach http://127.0.0.1:$Port/api/v1/health"
}

Write-Host ""
if ($Enable) {
    Write-Host "Open:  http://localhost:$Port/poc/native"
    Write-Host "Password (default): koyori-poc"
    Write-Host "Checklist: docs/archive/c1-native-poc.md"
} else {
    Write-Host "Back to gateway-only. Room: http://localhost:$Port/"
}
