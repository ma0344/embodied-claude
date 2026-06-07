@echo off
REM Launch claude-code-webui with LM Studio env (ma-home).
REM Double-click or: scripts\run-webui-ma-home.cmd

set "SCRIPT=%~dp0run-webui-ma-home.ps1"
where pwsh >nul 2>&1 && (pwsh -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %* & exit /b !ERRORLEVEL!)
where powershell >nul 2>&1 && (powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %* & exit /b !ERRORLEVEL!)
echo No PowerShell found >&2
exit /b 1
