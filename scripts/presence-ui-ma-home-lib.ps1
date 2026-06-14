# Shared helpers for ma-home presence-ui (port / stop / wait).

function Get-PresenceUiPortListeners {
    param([string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }))
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-PresenceUiLogFile {
    Join-Path $env:USERPROFILE ".config\embodied-claude\logs\presence-ui.log"
}

function Get-PresenceUiUrl {
    param([string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }))
    "http://localhost:${Port}/"
}

function Wait-PresenceUiPortReady {
    param(
        [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
        [int]$TimeoutSeconds = 30
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        $Listeners = Get-PresenceUiPortListeners -Port $Port
        if ($Listeners.Count -gt 0) {
            return $Listeners[0]
        }
        Start-Sleep -Milliseconds 500
    }
    $null
}

function Stop-PresenceUiMaHome {
    param(
        [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
        [string]$TaskName = "EmbodiedClaude-PresenceUI",
        [int]$WaitSeconds = 15
    )

    $Stopped = @()

    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        $Info = Get-ScheduledTaskInfo -TaskName $TaskName
        if ($Task.State -eq "Running" -or $Info.LastTaskResult -eq 267009) {
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            $Stopped += "scheduled task $TaskName"
        }
    }

    foreach ($Marker in @("run-presence-ui-daemon.ps1", "run-presence-ui-worker.ps1")) {
        Get-CimInstance Win32_Process -Filter "Name='pwsh.exe' OR Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*$Marker*" } |
            ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                $Stopped += "$Marker PID $($_.ProcessId)"
            }
    }

    foreach ($Conn in (Get-PresenceUiPortListeners -Port $Port)) {
        $OwnerPid = $Conn.OwningProcess
        if (-not $OwnerPid) { continue }
        $Proc = Get-Process -Id $OwnerPid -ErrorAction SilentlyContinue
        Stop-Process -Id $OwnerPid -Force -ErrorAction SilentlyContinue
        $Label = if ($Proc) { "$($Proc.ProcessName) PID $OwnerPid" } else { "PID $OwnerPid" }
        $Stopped += "port $Port listener ($Label)"
    }

    $Deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $Deadline) {
        if ((Get-PresenceUiPortListeners -Port $Port).Count -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 300
    }

    $StillListening = Get-PresenceUiPortListeners -Port $Port
    if ($StillListening.Count -gt 0) {
        throw "Port $Port is still in use after stop (PID $($StillListening[0].OwningProcess))."
    }

    ,$Stopped
}

function Import-PresenceUiLocalEnv {
    $LocalEnvFile = Join-Path $env:USERPROFILE ".config\embodied-claude\presence-ui.local.env"
    if (-not (Test-Path $LocalEnvFile)) { return }
    foreach ($line in Get-Content $LocalEnvFile -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        if ($t -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            $key = $Matches[1]
            $val = $Matches[2].Trim().Trim('"').Trim("'")
            if (-not [string]::IsNullOrWhiteSpace($val)) {
                Set-Item -Path "Env:$key" -Value $val
            }
        }
    }
}

function Test-PresenceNativeChatEnabled {
    param(
        [switch]$QueryUiConfig,
        [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" })
    )

    if ($env:PRESENCE_NATIVE_CHAT -match '^(1|true|yes)$') { return $true }
    if (-not $QueryUiConfig) { return $false }

    try {
        $cfg = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/ui-config" -TimeoutSec 5
        return [bool]$cfg.native_chat -or ($cfg.chat_backend -eq "native")
    } catch {
        return $false
    }
}

function Get-PresenceNativeLoginPassword {
    if ($env:PRESENCE_CCS_PASSWORD) { return $env:PRESENCE_CCS_PASSWORD.Trim() }
    return "koyori-poc"
}

function Initialize-PresenceUiEnv {
    param(
        [string]$Repo,
        [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
        [string]$BackendPort = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" })
    )

    Import-PresenceUiLocalEnv

    if (-not $env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT = $Port }
    if (-not $env:CLAUDE_CODE_BACKEND_URL) {
        $env:CLAUDE_CODE_BACKEND_URL = "http://127.0.0.1:$BackendPort"
    }
    if (-not $env:PRESENCE_PROJECT_PATH) { $env:PRESENCE_PROJECT_PATH = $Repo }
    if (-not $env:CAPTURE_DIR) {
        $env:CAPTURE_DIR = Join-Path $env:TEMP "wifi-cam-mcp"
    }
}
