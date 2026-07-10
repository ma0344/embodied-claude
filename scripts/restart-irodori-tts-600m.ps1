# Switch Irodori-TTS-Server/.env to 600M-v3-VoiceDesign and restart (:8088).
#
# Upgrades irodori-tts from git (VoiceDesign needs use_speaker_condition support).
# Caption in irodori-profile.toml is honored on this checkpoint.
#
# Usage:
#   .\scripts\restart-irodori-tts-600m.ps1
#   .\scripts\restart-irodori-tts-600m.ps1 -Foreground
#   .\scripts\restart-irodori-tts-600m.ps1 -SkipSync
#
# Log: %USERPROFILE%\.config\embodied-claude\logs\irodori-tts.log

param(
    [switch]$Foreground,
    [switch]$SkipSync,
    [int]$WaitSeconds = 0
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "irodori-tts-ma-home-lib.ps1")

exit (Restart-IrodoriTtsMaHome -Variant "600m" -SkipSync:$SkipSync -Foreground:$Foreground -WaitSeconds $WaitSeconds)
