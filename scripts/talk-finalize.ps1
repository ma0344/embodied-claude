# Heartbeat finalize-turn via gateway (record + pulse + interpretation_shift).
param(
    [Parameter(Mandatory)][string]$UserText,
    [string]$ReplyText = "",
    [string]$PersonId = "ma",
    [string]$SessionId = "",
    [string]$PlanJsonPath = "",
    [string]$CtxJsonPath = "",
    [string]$BaseUrl = $(if ($env:PRESENCE_BASE_URL) { $env:PRESENCE_BASE_URL } else { "http://127.0.0.1:8090" })
)

$ErrorActionPreference = "Stop"
$body = @{
    person_id  = $PersonId
    user_text  = $UserText
    reply_text = $ReplyText
}
if ($SessionId) { $body.session_id = $SessionId }
if ($PlanJsonPath -and (Test-Path $PlanJsonPath)) {
    $body.plan = Get-Content $PlanJsonPath -Raw | ConvertFrom-Json
}
if ($CtxJsonPath -and (Test-Path $CtxJsonPath)) {
    $body.ctx = Get-Content $CtxJsonPath -Raw | ConvertFrom-Json
}

$uri = ($BaseUrl.TrimEnd("/")) + "/api/v1/heartbeat/finalize-turn"
$response = Invoke-RestMethod -Uri $uri -Method Post -Body ($body | ConvertTo-Json -Depth 30 -Compress) -ContentType "application/json; charset=utf-8"
$response | ConvertTo-Json -Depth 10
