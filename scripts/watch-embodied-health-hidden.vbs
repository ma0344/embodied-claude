' Run watch-embodied-health.ps1 with no console window (Scheduled Task).
Option Explicit
Dim sh, repo, ps1, cmd
repo = "C:\Users\ma\src\embodied-claude"
ps1 = repo & "\scripts\watch-embodied-health.ps1"
cmd = "pwsh.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """ -StdioHangMinutes 5"
Set sh = CreateObject("Wscript.Shell")
sh.Run cmd, 0, False
