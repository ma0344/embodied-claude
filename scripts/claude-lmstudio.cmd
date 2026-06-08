@echo off
REM Wrapper for claude-code-webui --claude-path (forces LM Studio QAT model).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0claude-lmstudio.ps1" %*
exit /b %ERRORLEVEL%
