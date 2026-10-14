@echo off
rem Run the SGF Toolkit Textual app.
rem
rem   run_sgf_toolkit.cmd                 opens the current directory
rem   run_sgf_toolkit.cmd <directory>     opens that directory
rem   run_sgf_toolkit.cmd --help          lists the app's own options
rem
rem The Python interpreter is chosen in this order:
rem   1. the repository's .venv  (which has Textual installed)
rem   2. whatever "python" is on PATH
rem
rem A directory given here is resolved against the directory you are in when
rem you run this, not against App\, where the script lives.
setlocal
rem Unbuffered, so that --help and any error text appear when the output is
rem being captured or piped rather than going to a console.
set "PYTHONUNBUFFERED=1"

set "ROOT=%~dp0.."
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
    set "PY=%VENV_PY%"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo This launcher could not find a Python interpreter.
        echo.
        echo Looked for:
        echo   %VENV_PY%
        echo   python on the PATH
        echo.
        echo Either create the virtual environment in the repository:
        echo   python -m venv .venv
        echo   .venv\Scripts\python.exe -m pip install textual
        echo ...or install Textual for the Python already on your PATH:
        echo   pip install textual
        goto :end
    )
    set "PY=python"
)

rem The app explains its own options; anything else is a directory, resolved
rem against the caller's working directory.
set "ARG=%~1"
if "%ARG%"=="" goto :run_here
if /i "%ARG%"=="--help" goto :run_args
if /i "%ARG%"=="-h" goto :run_args
if /i "%ARG%"=="/?" goto :run_args
if exist "%ARG%\" (set "TARGET=%CD%\%ARG%") else (set "TARGET=%ARG%")
"%PY%" "%~dp0run_sgf_toolkit.py" "%TARGET%"
goto :end

:run_args
"%PY%" "%~dp0run_sgf_toolkit.py" %*
goto :end

:run_here
"%PY%" "%~dp0run_sgf_toolkit.py" "%CD%"

:end
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" echo The app exited with code %EXITCODE%.
rem Wait for a keypress before the console closes, so a message stays readable
rem when this was started by double-clicking. 'pause' is given its input
rem explicitly because it reports "Press any key" on stderr and would otherwise
rem wait forever when there is no console.
pause < nul > nul
endlocal & exit /b %EXITCODE%
