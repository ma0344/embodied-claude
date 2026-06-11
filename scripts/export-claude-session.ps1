# Export Claude Code session JSONL to editable Markdown.
#
# List sessions:
#   .\scripts\export-claude-session.ps1 -List
#
# Export latest session (default):
#   .\scripts\export-claude-session.ps1
#
# Export by session id or prefix:
#   .\scripts\export-claude-session.ps1 -SessionId 6afd3195
#   .\scripts\export-claude-session.ps1 -SessionId 6afd3195-1f52-4474-b3be-714d48e958aa
#
# Custom output:
#   .\scripts\export-claude-session.ps1 -Output C:\temp\my-session.md

param(
    [switch]$List,
    [string]$SessionId = "",
    [switch]$Latest,
    [string]$Output = "",
    [string]$Project = ""
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$Py = Join-Path $PSScriptRoot "export_claude_session.py"

if (-not (Test-Path $Py)) {
    Write-Error "Missing $Py"
}

$Args = @($Py)
if ($Project) {
    $Args += @("--project", $Project)
} else {
    $Args += @("--project", $Repo)
}
if ($List) { $Args += "--list" }
if ($SessionId) { $Args += @("--session-id", $SessionId) }
if ($Latest) { $Args += "--latest" }
if ($Output) { $Args += @("-o", $Output) }

python @Args
