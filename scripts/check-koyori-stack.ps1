# ma-home こより運用スタックの一括ヘルスチェック。
# 何か怪しいときに実行 → 落ちているものを日本語で列挙。
#
# Usage:
#   .\scripts\check-koyori-stack.ps1
#   .\scripts\check-koyori-stack.ps1 -Quick    # memory recall / LM models 詳細を省略
#
# 再起動直後の自動スモークは post-logon-smoke.ps1（B1b）。本スクリプトは手動診断向け。

param(
    [switch]$Quick
)

$ErrorActionPreference = "Continue"
if ($PSVersionTable.PSVersion.Major -ge 6) {
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8
}
$Repo = Split-Path $PSScriptRoot -Parent
Set-Location $Repo

. (Join-Path $PSScriptRoot "embodied-health-lib.ps1")
. (Join-Path $PSScriptRoot "presence-ui-ma-home-lib.ps1")
Initialize-PresenceUiEnv -Repo $Repo
$nativeChat = Test-PresenceNativeChatEnabled -QueryUiConfig

$okLines = [System.Collections.Generic.List[string]]::new()
$downLines = [System.Collections.Generic.List[string]]::new()
$warnLines = [System.Collections.Generic.List[string]]::new()

function Test-PortListening([int]$Port) {
    return $null -ne (
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    )
}

function Get-ScheduledTaskStatus([string]$Name) {
    $t = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if (-not $t) { return @{ Present = $false; State = "missing"; Detail = "" } }
    $info = Get-ScheduledTaskInfo -TaskName $Name
    return @{
        Present = $true
        State   = [string]$t.State
        Detail  = "last=$($info.LastRunTime) result=$($info.LastTaskResult)"
    }
}

function Add-Ok([string]$Label, [string]$Detail = "") {
    $line = $Label
    if ($Detail) { $line += " — $Detail" }
    $null = $okLines.Add($line)
}

function Add-Down([string]$Label, [string]$Hint = "") {
    $line = $Label
    if ($Hint) { $line += " → $Hint" }
    $null = $downLines.Add($line)
}

function Add-Warn([string]$Label, [string]$Hint = "") {
    $line = $Label
    if ($Hint) { $line += " → $Hint" }
    $null = $warnLines.Add($line)
}

Write-Host "== こよりスタック診断 (ma-home) ==" -ForegroundColor Cyan
if ($nativeChat) {
    Write-Host "mode: Native chat（:8080 webui は任意）" -ForegroundColor DarkGray
}

# ── Memory HTTP ───────────────────────────────────────────────
$memHealth = Test-MemoryHttpHealth -Port 18900
if ($memHealth.Ok) {
    Add-Ok "記憶 HTTP (:18900)" "$($memHealth.Ms)ms"
    if (-not $Quick) {
        $recall = Test-MemoryHttpRecall -Port 18900 -TimeoutSec 15
        if ($recall.Ok) {
            Add-Ok "記憶 recall" "$($recall.Ms)ms"
        } else {
            Add-Down "記憶 recall" "応答なし: $($recall.Reason) — Start-ScheduledTask EmbodiedClaude-MemoryHTTP"
        }
    }
} elseif (Test-PortListening 18900) {
    Add-Down "記憶 HTTP (:18900)" "/health 異常: $($memHealth.Reason) — Start-ScheduledTask EmbodiedClaude-MemoryHTTP"
} else {
    Add-Down "記憶 HTTP (:18900)" "ポート未待受 — Start-ScheduledTask EmbodiedClaude-MemoryHTTP"
}

$memTask = Get-ScheduledTaskStatus "EmbodiedClaude-MemoryHTTP"
if ($memTask.Present) {
    if ($memTask.State -eq "Running" -or (Test-PortListening 18900)) {
        Add-Ok "タスク MemoryHTTP" $memTask.State
    } else {
        Add-Warn "タスク MemoryHTTP" "$($memTask.State) $($memTask.Detail)"
    }
} else {
    Add-Warn "タスク MemoryHTTP" "未登録 — .\scripts\install-memory-daemon-task.ps1"
}

# ── Presence UI ───────────────────────────────────────────────
try {
    $h = Invoke-RestMethod http://127.0.0.1:8090/api/v1/health -TimeoutSec 5
    $detail = "$($h.details.mode) status=$($h.status)"
    if ($null -ne $h.details.surface_tts_ready) {
        if ($h.details.surface_tts_ready) {
            $detail += " surface_tts=ready"
        } else {
            $detail += " surface_tts=DOWN"
            Add-Down "Presence 表面 TTS" "$($h.details.surface_tts_status) — Irodori / :8088 を確認"
        }
    }
    if ($h.status -eq "ok") {
        Add-Ok "Presence UI (:8090)" $detail
    } else {
        Add-Warn "Presence UI (:8090)" $detail
    }

    $chatLabel = if ($nativeChat) { "Native チャット送信 (/api/native/chat)" } else { "チャット送信 (/api/chat)" }
    $chatProbe = Test-PresenceChatSendProbe -NativeChat $nativeChat
    if ($chatProbe.Ok) {
        Add-Ok $chatLabel "$($chatProbe.Ms)ms intercept OK"
    } else {
        Add-Down $chatLabel "$($chatProbe.Reason) — Get-Content $(Get-PresenceUiLogFile) -Tail 40"
    }
} catch {
    if (Test-PortListening 8090) {
        Add-Down "Presence UI (:8090)" "health 取得失敗: $($_.Exception.Message)"
    } else {
        Add-Down "Presence UI (:8090)" "落ちている — .\scripts\restart-presence-ui.ps1"
    }
}

$presTask = Get-ScheduledTaskStatus "EmbodiedClaude-PresenceUI"
if (-not $presTask.Present) {
    Add-Warn "タスク PresenceUI" "未登録 — .\scripts\install-presence-ui-task.ps1"
}

# ── Irodori TTS ───────────────────────────────────────────────
$irodori = Test-IrodoriHttpHealth -Port 8088
if ($irodori.Ok) {
    Add-Ok "Irodori TTS (:8088)" "$($irodori.Ms)ms"
} else {
    Add-Down "Irodori TTS (:8088)" "$($irodori.Reason) — Start-ScheduledTask EmbodiedClaude-IrodoriTTS"
}

# ── Input Leap ────────────────────────────────────────────────
$ilSvc = Get-Service -Name InputLeap -ErrorAction SilentlyContinue
if ($ilSvc) {
    if ($ilSvc.Status -eq "Running") {
        if (Test-PortListening 24800) {
            Add-Ok "Input Leap" "サービス Running, :24800 LISTEN"
        } else {
            Add-Down "Input Leap" "サービスは動いているが :24800 未待受 — Restart-Service InputLeap（管理者）"
        }
    } else {
        Add-Down "Input Leap" "サービス $($ilSvc.Status) — Start-Service InputLeap（管理者）"
    }
} elseif (Test-PortListening 24800) {
    Add-Warn "Input Leap" "サービス未登録だが :24800 は LISTEN（旧 CLI?）"
} else {
    Add-Down "Input Leap" "未起動 — .\scripts\configure-input-leap-winget.ps1 またはスタートメニューから Input Leap"
}

# ── LM Studio ─────────────────────────────────────────────────
$lmPort = 1234
if (Test-PortListening $lmPort) {
    if (-not $Quick) {
        try {
            $models = Invoke-RestMethod "http://127.0.0.1:${lmPort}/v1/models" -TimeoutSec 5
            $ids = @($models.data | ForEach-Object { $_.id }) -join ", "
            Add-Ok "LM Studio (:1234)" "models: $ids"
        } catch {
            Add-Ok "LM Studio (:1234)" "LISTEN（/v1/models 未取得）"
        }
    } else {
        Add-Ok "LM Studio (:1234)" "LISTEN"
    }
} else {
    Add-Warn "LM Studio (:1234)" "未起動 — 会話・vision には LM Studio でモデルロード + Local Server"
}

# ── WebUI (legacy) ────────────────────────────────────────────
if ($nativeChat) {
    if (Test-PortListening 8080) {
        Add-Ok "WebUI (:8080)" "起動中（Native では任意）"
    } else {
        Add-Ok "WebUI (:8080)" "未起動（Native では問題なし）"
    }
} elseif (Test-PortListening 8080) {
    Add-Ok "WebUI (:8080)" "LISTEN"
} else {
    Add-Down "WebUI (:8080)" "落ちている — .\scripts\run-webui-ma-home.ps1 または EmbodiedClaude-WebUI"
}

# ── Watchdog ──────────────────────────────────────────────────
$wd = Get-ScheduledTaskStatus "EmbodiedClaude-Watchdog"
if (-not $wd.Present) {
    Add-Warn "Watchdog" "未登録 — .\scripts\install-embodied-watchdog-task.ps1"
} elseif ($wd.State -eq "Running" -or $wd.State -eq "Ready") {
    Add-Ok "Watchdog" $wd.State
} else {
    Add-Warn "Watchdog" "$($wd.State) $($wd.Detail)"
}

# ── Sociality HTTP (optional) ─────────────────────────────────
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:18901/ingest?text=healthcheck&person_id=ma" `
        -TimeoutSec 2 -UseBasicParsing | Out-Null
    Add-Ok "Sociality HTTP (:18901)" "応答あり（Claude セッション等）"
} catch {
    Add-Ok "Sociality HTTP (:18901)" "未起動（8090 compose は in-process で可）"
}

# ── Autonomous tick (optional) ────────────────────────────────
$tick = Get-ScheduledTaskStatus "EmbodiedClaude-AutonomousTick"
if ($tick.Present) {
    Add-Ok "自律 tick タスク" "$($tick.State) $($tick.Detail)"
} else {
    Add-Ok "自律 tick タスク" "未登録（任意）"
}

# ── 出力 ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- OK --" -ForegroundColor Green
foreach ($line in $okLines) {
    Write-Host "  ✓ $line" -ForegroundColor Green
}

if ($warnLines.Count -gt 0) {
    Write-Host ""
    Write-Host "-- 注意（動くが要確認）--" -ForegroundColor Yellow
    foreach ($line in $warnLines) {
        Write-Host "  ! $line" -ForegroundColor Yellow
    }
}

Write-Host ""
if ($downLines.Count -eq 0) {
    Write-Host "== まとめ: 必須項目はすべて OK ==" -ForegroundColor Green
    if ($warnLines.Count -gt 0) {
        Write-Host "（注意 $($warnLines.Count) 件 — 上記参照）" -ForegroundColor Yellow
    }
    exit 0
}

Write-Host "== まとめ: 落ちている / 異常 ==" -ForegroundColor Red
foreach ($line in $downLines) {
    Write-Host "  ✗ $line" -ForegroundColor Red
}
Write-Host ""
Write-Host "再起動の例:" -ForegroundColor DarkGray
Write-Host "  .\scripts\restart-presence-ui.ps1" -ForegroundColor DarkGray
Write-Host "  Start-ScheduledTask EmbodiedClaude-MemoryHTTP" -ForegroundColor DarkGray
Write-Host "  Start-ScheduledTask EmbodiedClaude-IrodoriTTS" -ForegroundColor DarkGray
Write-Host "  Restart-Service InputLeap   # 管理者" -ForegroundColor DarkGray
exit 1
