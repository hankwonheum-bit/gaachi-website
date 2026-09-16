@echo off
rem ===============================================================
rem  gaachi - daily auto-publish runner v2 (Task Scheduler entry)
rem  ASCII ONLY. Do not add Korean text to this file:
rem  cmd.exe seeks by byte offset while running a batch file, and
rem  multi-byte characters under chcp 65001 make it resume in the
rem  middle of a later line. All Korean messages come from Python.
rem
rem  Log files:
rem    automation\logs\publish-YYYYMMDD.log  <- written by Python
rem    automation\logs\run_last.log          <- raw stdout+stderr of
rem                                             the last run only
rem ===============================================================
chcp 65001 >nul
setlocal EnableExtensions

cd /d "%~dp0.." || exit /b 8
if not exist "index.html" exit /b 8
if not exist "automation\logs" mkdir "automation\logs"

set "RUNLOG=automation\logs\run_last.log"

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (python --version >nul 2>&1 && set "PY=python")
if not defined PY goto nopy

%PY% "automation\publish_case_v1.py" %* >"%RUNLOG%" 2>&1
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%

:nopy
>"%RUNLOG%" echo [ERROR] Python not found. Tried "py -3" and "python".
>>"%RUNLOG%" echo         Install from https://www.python.org/downloads/
endlocal & exit /b 9
