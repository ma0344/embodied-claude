# Windows toast for ma-home outbound (A4g PC path).
#
# Body click opens the notifying app (ntfy-desktop limitation). This toast adds a
# button with activationType=protocol so Windows opens the URL in the default browser.
#
# Usage:
#   .\scripts\show-koyori-win-toast.ps1 -Message "まー、おる？"
#   .\scripts\show-koyori-win-toast.ps1 -TestOnly

param(
    [string]$Title = "Koyori",
    [string]$Message = "",
    [string]$ClickUrl = "http://127.0.0.1:8090/",
    [string]$ButtonLabel = "Open room",
    [switch]$TestOnly
)

# WinRT toast APIs load in Windows PowerShell 5.1 only (pwsh 7 fails on ToastNotificationManager).
if ($PSVersionTable.PSEdition -eq 'Core') {
    $windowsPs = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path $windowsPs)) {
        Write-Error "Windows PowerShell 5.1 not found: $windowsPs"
    }
    $forward = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
    foreach ($key in $PSBoundParameters.Keys) {
        $val = $PSBoundParameters[$key]
        if ($val -is [switch]) {
            if ($val) { $forward += "-$key" }
        } else {
            $forward += @("-$key", [string]$val)
        }
    }
    & $windowsPs @forward
    exit $LASTEXITCODE
}

$ErrorActionPreference = "Stop"

if ($TestOnly) {
    $Message = "Win toast test — $(Get-Date -Format 'HH:mm:ss')"
}

if (-not $Message.Trim()) {
    Write-Error "Message is required (or use -TestOnly)."
}

function Escape-Xml {
    param([string]$Text)
    if (-not $Text) { return "" }
    return ($Text -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' -replace '"', '&quot;')
}

$safeTitle = Escape-Xml $Title
$safeMessage = Escape-Xml $Message
$safeUrl = Escape-Xml $ClickUrl.Trim()
$safeButton = Escape-Xml $ButtonLabel

$xml = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>$safeTitle</text>
      <text>$safeMessage</text>
    </binding>
  </visual>
  <actions>
    <action content="$safeButton" activationType="protocol" arguments="$safeUrl" />
  </actions>
</toast>
"@

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)

# Registered AUMID — notifications show as Windows PowerShell (no extra install).
$appId = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($doc)

if ($TestOnly) {
    Write-Host "OK: toast shown. Tap '$ButtonLabel' -> $ClickUrl"
}
