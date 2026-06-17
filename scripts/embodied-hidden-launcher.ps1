# Shared VBS launcher for Scheduled Tasks — no console flash (B4).
# Dot-source from install-*-task.ps1 scripts.

function New-EmbodiedHiddenVbsLauncher {
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$Ps1Path,
        [Parameter(Mandatory)][string]$LauncherPath,
        [string]$ExtraArguments = ""
    )

    if (-not (Test-Path $Ps1Path)) {
        throw "Missing runner script: $Ps1Path"
    }

    $escapedRepo = $Repo.Replace("\", "\\")
    $escapedPs1 = $Ps1Path.Replace("\", "\\")
    $extra = ""
    if ($ExtraArguments.Trim()) {
        $extra = " " + $ExtraArguments.Trim()
    }

    $vbsContent = @"
' Embodied Claude — run PowerShell script with no console window.
Option Explicit
Dim sh, cmd
cmd = "pwsh.exe -NoProfile -ExecutionPolicy Bypass -File ""$escapedPs1""$extra"
Set sh = CreateObject("Wscript.Shell")
sh.Run cmd, 0, False
"@

    Set-Content -Path $LauncherPath -Value $vbsContent -Encoding ASCII
    return $LauncherPath
}

function New-EmbodiedHiddenTaskAction {
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$LauncherPath
    )

    if (-not (Test-Path $LauncherPath)) {
        throw "Missing VBS launcher: $LauncherPath"
    }

    return New-ScheduledTaskAction `
        -Execute "wscript.exe" `
        -Argument "//B `"$LauncherPath`"" `
        -WorkingDirectory $Repo
}
