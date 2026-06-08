# Safe git sync for ma-home after repo recovery (PowerShell).
#
# Backs up local secrets, aligns with origin/main, restores secrets.
#
# Usage:
#   cd C:\Users\ma\src\embodied-claude
#   .\scripts\sync-ma-home-git.ps1
#
# Do NOT commit settings.local.json or .mcp.json — they stay local.

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$BackupDir = Join-Path $env:USERPROFILE ".config\embodied-claude\git-sync-backup"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $BackupDir $Stamp

$SecretFiles = @(
    (Join-Path $Repo ".claude\settings.local.json"),
    (Join-Path $Repo ".mcp.json"),
    (Join-Path $Repo "SOUL.md"),
    (Join-Path $Repo "MEMORY.md"),
    (Join-Path $env:USERPROFILE ".config\embodied-claude\lmstudio.token")
)

Write-Host "==> ma-home git sync"
Write-Host "    repo: $Repo"

Set-Location $Repo

New-Item -ItemType Directory -Force -Path $Backup | Out-Null
foreach ($file in $SecretFiles) {
    if (Test-Path $file) {
        $dest = Join-Path $Backup (Split-Path $file -Leaf)
        Copy-Item $file $dest -Force
        Write-Host "    backed up: $file"
    }
}

Write-Host ""
Write-Host "Fetching origin..."
git fetch origin

$local = git rev-parse HEAD
$remote = git rev-parse origin/main 2>$null
if (-not $remote) {
    Write-Error "origin/main not found. Check: git remote -v"
}

if ($local -eq $remote) {
    Write-Host "Already aligned with origin/main ($local)"
} else {
    Write-Host "Resetting to origin/main (local was $local)"
    Write-Host "  remote: $remote"
    git reset --hard origin/main
}

foreach ($file in $SecretFiles) {
    $name = Split-Path $file -Leaf
    $src = Join-Path $Backup $name
    if (Test-Path $src) {
        $dir = Split-Path $file -Parent
        if ($dir -and -not (Test-Path $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        Copy-Item $src $file -Force
        Write-Host "    restored: $file"
    }
}

Write-Host ""
Write-Host "Done. Backup kept at: $Backup"
Write-Host "Verify: git status"
git status -sb
