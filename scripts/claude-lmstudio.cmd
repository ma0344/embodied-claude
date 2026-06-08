@ECHO off
SETLOCAL
SET "NODE_EXE=node"
"%NODE_EXE%" "%~dp0claude-lmstudio.cjs" %*
