@echo off
rem Token Vault setup for Windows. Safe to run again at any time.
rem Installs uv (which installs Python 3.12 for you), the game's packages, and a .env file.
rem   setup.bat          core game
rem   setup.bat --all    also Langfuse, NeMo Guardrails, and CrewAI
cd /d "%~dp0"

set "UV_EXTRAS="
for %%A in (%*) do if /I "%%~A"=="--all" set "UV_EXTRAS=--all-extras"

echo.
echo  ===== Token Vault setup =====

where uv >nul 2>nul
if not errorlevel 1 goto have_uv
if exist "%USERPROFILE%\.local\bin\uv.exe" goto add_uv_path
echo  [1/3] Installing uv, the Python toolchain manager...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
:add_uv_path
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
:have_uv
where uv >nul 2>nul
if errorlevel 1 (
  echo  Could not find or install uv. Install it by hand from https://docs.astral.sh/uv/ and run this again.
  exit /b 1
)

echo  [2/3] Installing Python and packages. The first run takes a minute or two...
uv sync %UV_EXTRAS%
if errorlevel 1 (
  echo  Package install failed. Check your internet connection and run setup.bat again.
  exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul
echo  [3/3] Ready. Run play.bat to play.
exit /b 0
