# Shared helpers for ma-home claude-code-webui (stop / port check).

function Get-WebuiPortListeners {
    param([string]$Port = "8080")
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-WebuiMaHome {
    param(
        [string]$Port = $(if ($env:WEBUI_PORT) { $env:WEBUI_PORT } else { "8080" }),
        [string]$TaskName = "EmbodiedClaude-WebUI",
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

    $DaemonMarker = "run-webui-ma-home-daemon.ps1"
    Get-CimInstance Win32_Process -Filter "Name='pwsh.exe' OR Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$DaemonMarker*" } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            $Stopped += "daemon PID $($_.ProcessId)"
        }

    foreach ($Conn in (Get-WebuiPortListeners -Port $Port)) {
        $OwnerPid = $Conn.OwningProcess
        if (-not $OwnerPid) { continue }
        $Proc = Get-Process -Id $OwnerPid -ErrorAction SilentlyContinue
        Stop-Process -Id $OwnerPid -Force -ErrorAction SilentlyContinue
        $Label = if ($Proc) { "$($Proc.ProcessName) PID $OwnerPid" } else { "PID $OwnerPid" }
        $Stopped += "port $Port listener ($Label)"
    }

    $Deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $Deadline) {
        if ((Get-WebuiPortListeners -Port $Port).Count -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 300
    }

    $StillListening = Get-WebuiPortListeners -Port $Port
    if ($StillListening.Count -gt 0) {
        throw "Port $Port is still in use after stop (PID $($StillListening[0].OwningProcess))."
    }

    ,$Stopped
}

function Get-WebuiProjectUrl {
    param(
        [string]$Repo,
        [string]$Port = "8080"
    )
    "http://localhost:${Port}/projects/$($Repo -replace '\\','/')"
}

function Wait-WebuiPortReady {
    param(
        [string]$Port = "8080",
        [int]$TimeoutSeconds = 30
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        $Listeners = Get-WebuiPortListeners -Port $Port
        if ($Listeners.Count -gt 0) {
            return $Listeners[0]
        }
        Start-Sleep -Milliseconds 500
    }
    $null
}
