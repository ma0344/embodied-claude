# Heartbeat compose+plan via gateway (BIO-6 — no sociality MCP).
param(
    [Parameter(Mandatory)][string]$UserText,
    [string]$PersonId = "ma",
    [string]$Channel = "chat",
    [string]$SessionId = "",
    [string]$BaseUrl = $(if ($env:PRESENCE_BASE_URL) { $env:PRESENCE_BASE_URL } else { "http://127.0.0.1:8090" })
)

$ErrorActionPreference = "Stop"
$body = @{
    person_id   = $PersonId
    channel     = $Channel
    user_text   = $UserText
    include_private = $true
}
if ($SessionId) { $body.session_id = $SessionId }

$uri = ($BaseUrl.TrimEnd("/")) + "/api/v1/heartbeat/compose-plan"
$response = Invoke-RestMethod -Uri $uri -Method Post -Body ($body | ConvertTo-Json -Compress) -ContentType "application/json; charset=utf-8"
$response | ConvertTo-Json -Depth 20
