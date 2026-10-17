@echo off
rem Run the SGF Toolkit web app.
rem
rem Double-clicking this serves the WebApp directory over HTTP and opens it in
rem your browser. The app cannot be opened as a file: browsers refuse to load
rem JavaScript modules from file:// URLs, so a server is needed.
rem
rem   run_web_app.cmd                  serve on the first free port from 8000
rem   run_web_app.cmd 8080             try that port first
rem   run_web_app.cmd --no-browser     serve without opening a browser
rem   run_web_app.cmd --help           list the options
rem
rem Close the window, or press Ctrl+C, to stop the server.
title SGF Toolkit (web)
setlocal

cd /d "%~dp0"

set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
set "PY_CMD="
set "PY_ARGS="

if exist "%VENV_PY%" goto :have_venv
where python >nul 2>nul
if not errorlevel 1 goto :have_python
where py >nul 2>nul
if not errorlevel 1 goto :have_py
goto :no_python

:have_venv
set "PY_CMD=%VENV_PY%"
goto :serve

:have_python
set "PY_CMD=python"
goto :serve

:have_py
set "PY_CMD=py"
set "PY_ARGS=-3"
goto :serve

:no_python
echo This launcher could not find Python.
echo.
echo Looked for:
echo   %VENV_PY%
echo   python on the PATH
echo   the py launcher
echo.
echo Install Python 3 from https://www.python.org/downloads/ and try again.
echo (The app itself needs nothing but a browser; only this launcher needs
echo Python to serve the files. Any static web server would do instead.)
goto :failed

:serve
"%PY_CMD%" %PY_ARGS% "%~dp0serve.py" %*
set "EXITCODE=%ERRORLEVEL%"
if "%EXITCODE%"=="0" goto :end

echo.
echo The server stopped with code %EXITCODE%.
pause

:failed
set "EXITCODE=1"

:end
rem --help exits at once, so keep the window up long enough to read it.
if /i "%~1"=="--help" pause
if /i "%~1"=="-h" pause
endlocal & exit /b %EXITCODE%
