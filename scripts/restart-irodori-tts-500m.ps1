# Switch Irodori-TTS-Server/.env to 500M-v3 base and restart (:8088).
#
# Usage:
#   .\scripts\restart-irodori-tts-500m.ps1
#   .\scripts\restart-irodori-tts-500m.ps1 -Foreground
#   .\scripts\restart-irodori-tts-500m.ps1 -SkipSync
#
# Caption in irodori-profile.toml is ignored on this checkpoint.
# Log: %USERPROFILE%\.config\embodied-claude\logs\irodori-tts.log

param(
    [switch]$Foreground,
    [switch]$SkipSync,
    [int]$WaitSeconds = 0
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "irodori-tts-ma-home-lib.ps1")

exit (Restart-IrodoriTtsMaHome -Variant "500m" -SkipSync:$SkipSync -Foreground:$Foreground -WaitSeconds $WaitSeconds)
