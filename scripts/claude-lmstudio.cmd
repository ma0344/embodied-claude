@ECHO off
SETLOCAL
SET "NODE_EXE=node"
SET "_prog=%NODE_EXE%"
"%_prog%" "%dp0%\claude-lmstudio.js" %*
