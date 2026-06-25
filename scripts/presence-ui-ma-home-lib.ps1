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

function Test-PresenceChatSendProbe {
    <#
    .SYNOPSIS
    POST chat (native SSE or legacy NDJSON) and fail on HTTP 5xx before stream starts.
    Catches intercept bugs that /health and compose-plan miss (e.g. missing imports).
    #>
    param(
        [string]$Port = $(if ($env:PRESENCE_UI_PORT) { $env:PRESENCE_UI_PORT } else { "8090" }),
        [bool]$NativeChat = $true,
        [double]$TimeoutSec = 15.0
    )

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $base = "http://127.0.0.1:$Port"

    try {
        $chatUri = if ($NativeChat) { "$base/api/native/chat" } else { "$base/api/chat" }
        $headers = @{}

        if ($NativeChat) {
            $password = Get-PresenceNativeLoginPassword
            $loginJson = (@{ password = $password } | ConvertTo-Json -Compress)
            $loginResp = Invoke-RestMethod -Method Post -Uri "$base/api/native/login" `
                -ContentType "application/json; charset=utf-8" `
                -Body $loginJson -TimeoutSec 5
            $token = [string]$loginResp.token
            if ([string]::IsNullOrWhiteSpace($token)) {
                $sw.Stop()
                return @{ Ok = $false; Reason = "native login: token missing"; Ms = $sw.ElapsedMilliseconds }
            }
            $headers["Authorization"] = "Bearer $token"
            $bodyObj = @{ prompt = "__healthcheck__" }
        } else {
            $bodyObj = @{ message = "__healthcheck__" }
        }

        $bodyJson = ($bodyObj | ConvertTo-Json -Compress)
        $client = [System.Net.Http.HttpClient]::new()
        $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)

        $request = [System.Net.Http.HttpRequestMessage]::new(
            [System.Net.Http.HttpMethod]::Post,
            $chatUri
        )
        $request.Content = [System.Net.Http.StringContent]::new(
            $bodyJson,
            [System.Text.Encoding]::UTF8,
            "application/json"
        )
        foreach ($key in $headers.Keys) {
            $null = $request.Headers.TryAddWithoutValidation($key, $headers[$key])
        }

        $response = $client.SendAsync(
            $request,
            [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
        ).GetAwaiter().GetResult()

        $status = [int]$response.StatusCode
        if ($status -ge 500) {
            $detail = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            $snippet = ($detail -replace '\s+', ' ').Trim()
            if ($snippet.Length -gt 140) { $snippet = $snippet.Substring(0, 140) + "..." }
            $sw.Stop()
            $client.Dispose()
            return @{
                Ok     = $false
                Reason = "HTTP $status $snippet"
                Ms     = $sw.ElapsedMilliseconds
            }
        }
        if ($status -lt 200 -or $status -ge 300) {
            $sw.Stop()
            $client.Dispose()
            return @{ Ok = $false; Reason = "HTTP $status"; Ms = $sw.ElapsedMilliseconds }
        }

        $stream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
        $buffer = New-Object byte[] 256
        $read = $stream.Read($buffer, 0, $buffer.Length)
        $stream.Dispose()
        $client.Dispose()
        $sw.Stop()

        if ($read -le 0) {
            return @{ Ok = $false; Reason = "empty response body"; Ms = $sw.ElapsedMilliseconds }
        }

        return @{ Ok = $true; Ms = $sw.ElapsedMilliseconds; Status = $status }
    } catch {
        $sw.Stop()
        return @{ Ok = $false; Reason = $_.Exception.Message; Ms = $sw.ElapsedMilliseconds }
    }
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
    if (-not $env:EMBODIED_CLAUDE_ROOT) { $env:EMBODIED_CLAUDE_ROOT = $Repo }
    if (-not $env:PRESENCE_OUTBOUND_WIN_TOAST) { $env:PRESENCE_OUTBOUND_WIN_TOAST = "1" }
    $WinToast = Join-Path $Repo "scripts\show-koyori-win-toast.ps1"
    if ((Test-Path $WinToast) -and -not $env:PRESENCE_OUTBOUND_WIN_TOAST_SCRIPT) {
        $env:PRESENCE_OUTBOUND_WIN_TOAST_SCRIPT = $WinToast
    }
    if (-not $env:CAPTURE_DIR) {
        $env:CAPTURE_DIR = Join-Path $env:TEMP "wifi-cam-mcp"
    }
}
