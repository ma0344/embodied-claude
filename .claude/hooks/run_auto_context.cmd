@echo off
REM UserPromptSubmit hook launcher for Windows (Claude Code).
REM Tries py launcher, then python, then python3.
set "SCRIPT=%CLAUDE_PROJECT_DIR%\.claude\hooks\auto_context.py"
if not exist "%SCRIPT%" exit /b 0
where py >nul 2>&1 && (py -3 "%SCRIPT%" & exit /b 0)
where python >nul 2>&1 && (python "%SCRIPT%" & exit /b 0)
where python3 >nul 2>&1 && (python3 "%SCRIPT%" & exit /b 0)
exit /b 0
