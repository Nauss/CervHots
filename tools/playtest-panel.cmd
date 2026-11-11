@echo off
setlocal
rem Double-click opens ONLY the manual panel. No game/API/audio autostart.
set "ROOT=%~dp0.."
set "PY=%ROOT%\tts\.venv\Scripts\python.exe"
if defined CERVHOTS_PYTHON set "PY=%CERVHOTS_PYTHON%"
cd /d "%ROOT%"
if not exist "%PY%" (
  echo Python produit absent. Integrer dans main avec tts\.venv installe.
  exit /b 2
)
"%PY%" -B -m cerveau.playtest_ui
exit /b %ERRORLEVEL%
