@echo off
setlocal
rem Manual Windows launcher. No invocation without an explicit action starts IO.
set "ROOT=%~dp0.."
set "PY=%ROOT%\tts\.venv\Scripts\python.exe"
if defined CERVHOTS_PYTHON set "PY=%CERVHOTS_PYTHON%"
if not defined CERVHOTS_SCRATCH (
  echo CERVHOTS_SCRATCH required: absolute existing operator Hermes scratch directory.
  exit /b 2
)
if not exist "%PY%" (
  echo Product Python unavailable. Configure CERVHOTS_PYTHON explicitly.
  exit /b 2
)
"%PY%" -B -c "import os,sys; p=os.environ['CERVHOTS_SCRATCH']; sys.exit(0 if os.path.isabs(p) and os.path.isdir(p) else 2)"
if errorlevel 1 (
  echo CERVHOTS_SCRATCH invalid: absolute existing directory required.
  exit /b 2
)
set "TMPDIR=%CERVHOTS_SCRATCH%"
set "TEMP=%TMPDIR%"
set "TMP=%TMPDIR%"
cd /d "%ROOT%"
if /I "%~1"=="preflight" goto preflight
if /I "%~1"=="stop" goto stop
if /I "%~1"=="silent" goto prepare
if /I "%~1"=="voice" goto prepare
if /I "%~1"=="wav" goto prepare
echo Usage: playtest.cmd silent^|voice^|wav PLAYER_FILE NEW_OUTPUT STOP_FILE [CONFIG_FILE]
echo        playtest.cmd stop OUTPUT STOP_FILE
echo        playtest.cmd preflight
echo Paths must be absolute. Never put a player name or API token on the command line.
exit /b 2
:preflight
"%PY%" -B -m cerveau.playtest
exit /b %ERRORLEVEL%
:prepare
if "%~4"=="" exit /b 2
set "AUDIO="
if /I "%~1"=="wav" set "AUDIO=--wav"
if /I "%~1"=="voice" (
  choice /C ON /N /M "Activer MANUELLEMENT la diffusion Mumble ? O/N "
  if errorlevel 2 exit /b 0
  if not errorlevel 1 exit /b 0
  set "AUDIO=--mumble"
)
if "%~5"=="" (
  "%PY%" -B -m cerveau.playtest --live --player-file "%~2" --output-dir "%~3" --stop-file "%~4" %AUDIO%
) else (
  "%PY%" -B -m cerveau.playtest --live --player-file "%~2" --output-dir "%~3" --stop-file "%~4" --coach-env-file "%~5" %AUDIO%
)
exit /b %ERRORLEVEL%
:stop
if "%~3"=="" exit /b 2
"%PY%" -B -m cerveau.passive_session --request-stop --output-dir "%~2" --stop-file "%~3"
exit /b %ERRORLEVEL%
