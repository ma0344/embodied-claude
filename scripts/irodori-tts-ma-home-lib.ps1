# Shared helpers for Irodori TTS on ma-home (:8088).
# Dot-source from restart-irodori-tts-*.ps1 — do not run directly.

$Script:IrodoriTtsPort = $(if ($env:IRODORI_PORT) { [int]$env:IRODORI_PORT } else { 8088 })

$Script:IrodoriModelProfiles = @{
    "500m" = @{
        Label        = "500M-v3"
        HfCheckpoint = "Aratako/Irodori-TTS-500M-v3"
        WaitSeconds  = 180
        UpgradeLib   = $false
    }
    "600m" = @{
        Label        = "600M-v3-VoiceDesign"
        HfCheckpoint = "Aratako/Irodori-TTS-600M-v3-VoiceDesign"
        WaitSeconds  = 300
        UpgradeLib   = $true
    }
}

function Get-IrodoriTtsServerRoot {
    if ($env:IRODORI_TTS_SERVER_ROOT) {
        return $env:IRODORI_TTS_SERVER_ROOT
    }
    return "C:\Users\ma\src\Irodori-TTS-Server"
}

function Resolve-IrodoriCheckpointPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HfCheckpoint
    )

    $cacheRoot = Join-Path $env:USERPROFILE ".cache\huggingface\hub"
    $folderName = "models--$($HfCheckpoint -replace '/', '--')"
    $snapshotsDir = Join-Path $cacheRoot $folderName "snapshots"
    if (-not (Test-Path $snapshotsDir)) {
        throw "HF cache not found for $HfCheckpoint at $snapshotsDir. Download the model first."
    }

    $candidate = Get-ChildItem -Path $snapshotsDir -Directory -ErrorAction SilentlyContinue |
        ForEach-Object {
            $path = Join-Path $_.FullName "model.safetensors"
            if (Test-Path $path) {
                [PSCustomObject]@{
                    Path         = $path
                    LastWriteUtc = (Get-Item $path).LastWriteTimeUtc
                }
            }
        } |
        Sort-Object LastWriteUtc -Descending |
        Select-Object -First 1

    if (-not $candidate) {
        throw "model.safetensors not found under $snapshotsDir"
    }

    return $candidate.Path
}

function Set-IrodoriDotEnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EnvPath,
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if (-not (Test-Path $EnvPath)) {
        throw "Missing $EnvPath"
    }

    $pattern = "^\s*$([regex]::Escape($Key))\s*="
    $newLine = "$Key=$Value"
    $found = $false
    $out = foreach ($line in (Get-Content -Path $EnvPath -Encoding utf8)) {
        if ($line -match $pattern) {
            $found = $true
            $newLine
        } else {
            $line
        }
    }
    if (-not $found) {
        $out += $newLine
    }
    Set-Content -Path $EnvPath -Value $out -Encoding utf8
}

function Update-IrodoriTtsEnvForProfile {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Profile
    )

    $serverRoot = Get-IrodoriTtsServerRoot
    $envPath = Join-Path $serverRoot ".env"
    $checkpoint = Resolve-IrodoriCheckpointPath -HfCheckpoint $Profile.HfCheckpoint

    Set-IrodoriDotEnvValue -EnvPath $envPath -Key "IRODORI_HF_CHECKPOINT" -Value $Profile.HfCheckpoint
    Set-IrodoriDotEnvValue -EnvPath $envPath -Key "IRODORI_CHECKPOINT" -Value $checkpoint

    return [PSCustomObject]@{
        EnvPath    = $envPath
        Checkpoint = $checkpoint
        HfCheckpoint = $Profile.HfCheckpoint
    }
}

function Stop-IrodoriTtsMaHome {
    param(
        [int]$Port = $Script:IrodoriTtsPort
    )

    $stopped = @()
    $pids = @(
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    foreach ($listenerPid in $pids) {
        if (-not $listenerPid) { continue }
        try {
            Stop-Process -Id $listenerPid -Force -ErrorAction Stop
            $stopped += "PID $listenerPid"
        } catch {
            throw "Failed to stop Irodori listener PID $listenerPid on port ${Port}: $_"
        }
    }

    if ($stopped.Count -gt 0) {
        Start-Sleep -Seconds 2
    }

    return $stopped
}

function Sync-IrodoriTtsLibrary {
    param(
        [switch]$Upgrade
    )

    $serverRoot = Get-IrodoriTtsServerRoot
    if (-not (Test-Path $serverRoot)) {
        throw "Irodori-TTS-Server not found at $serverRoot"
    }

    Push-Location $serverRoot
    try {
        if ($Upgrade) {
            Write-Host "    uv sync --extra cu128 --upgrade-package irodori-tts"
            uv sync --extra cu128 --upgrade-package irodori-tts
        } else {
            Write-Host "    uv sync --extra cu128"
            uv sync --extra cu128
        }
    } finally {
        Pop-Location
    }
}

function Test-IrodoriTtsHealth {
    param(
        [int]$Port = $Script:IrodoriTtsPort,
        [double]$TimeoutSec = 5.0
    )

    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec $TimeoutSec
        return [PSCustomObject]@{
            Ok           = $true
            HfCheckpoint = [string]$health.model.hf_checkpoint
            Loaded       = [bool]$health.runtime.loaded
            Checkpoint   = [string]$health.runtime.checkpoint
        }
    } catch {
        return [PSCustomObject]@{
            Ok     = $false
            Reason = $_.Exception.Message
        }
    }
}

function Restart-IrodoriTtsMaHome {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("500m", "600m")]
        [string]$Variant,
        [switch]$SkipSync,
        [switch]$Foreground,
        [int]$WaitSeconds = 0
    )

    $profile = $Script:IrodoriModelProfiles[$Variant]
    if ($WaitSeconds -le 0) {
        $WaitSeconds = [int]$profile.WaitSeconds
    }

    Write-Host "==> restart-irodori-tts-$Variant ($($profile.Label))"

    $envUpdate = Update-IrodoriTtsEnvForProfile -Profile $profile
    Write-Host "    .env -> $($envUpdate.HfCheckpoint)"
    Write-Host "    checkpoint -> $($envUpdate.Checkpoint)"

    if (-not $SkipSync) {
        Sync-IrodoriTtsLibrary -Upgrade:([bool]$profile.UpgradeLib)
    } else {
        Write-Host "    skip uv sync"
    }

    $stopped = Stop-IrodoriTtsMaHome
    if ($stopped.Count -eq 0) {
        Write-Host "    was not running"
    } else {
        foreach ($line in $stopped) {
            Write-Host "    stopped $line"
        }
    }

    $starter = Join-Path $PSScriptRoot "start-irodori-tts.ps1"
    if ($Foreground) {
        Write-Host "    foreground: start-irodori-tts.ps1"
        & $starter
        return $LASTEXITCODE
    }

    Write-Host "    background: start-irodori-tts.ps1 -Background -WaitSeconds $WaitSeconds"
    & $starter -Background -WaitSeconds $WaitSeconds
    if ($LASTEXITCODE -ne 0) {
        return $LASTEXITCODE
    }

    $health = Test-IrodoriTtsHealth
    if (-not $health.Ok) {
        throw "health check failed: $($health.Reason)"
    }
    if ($health.HfCheckpoint -ne $profile.HfCheckpoint) {
        throw "health hf_checkpoint mismatch: expected $($profile.HfCheckpoint), got $($health.HfCheckpoint)"
    }
    if (-not $health.Loaded) {
        throw "runtime not loaded after restart"
    }

    Write-Host "OK  http://127.0.0.1:$($Script:IrodoriTtsPort)/health ($($profile.Label))"
    return 0
}
