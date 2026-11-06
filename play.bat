@echo off
rem Double-click to play. Sets everything up on the first run, then opens the game in your browser.
rem Extra arguments go to the vault-heist command, for example:  play.bat doctor
cd /d "%~dp0"
title Token Vault

call "%~dp0setup.bat" %*
if errorlevel 1 (
  echo.
  echo  Setup failed. Scroll up for the error.
  pause
  exit /b 1
)

set "RUNARGS="
for %%Z in (%*) do if /I not "%%~Z"=="--all" call set "RUNARGS=%%RUNARGS%% %%Z"
if "%RUNARGS%"=="" (
  uv run vault-heist serve
) else (
  uv run vault-heist %RUNARGS%
)
if errorlevel 1 pause
