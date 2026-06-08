@ECHO off
SETLOCAL
SET "NODE_EXE=node"
"%NODE_EXE%" "%~dp0claude-lmstudio.cjs" %*
REM "%_prog%" "%dp0%\claude-lmstudio.cjs"
