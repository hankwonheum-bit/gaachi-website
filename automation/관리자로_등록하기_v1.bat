@echo off
rem ===============================================================
rem  gaachi - one-click ADMIN launcher for register_task_v2.ps1
rem
rem  ASCII ONLY. Do not add Korean text to this file:
rem  cmd.exe seeks by byte offset while running a batch file, and
rem  multi-byte characters under chcp 65001 make it resume in the
rem  middle of a later line. Every Korean message comes from the
rem  PowerShell script that this file calls.
rem
rem  What this file does:
rem    1. checks whether it already runs as administrator
rem    2. if not, relaunches itself through UAC with marker arg ELEV
rem    3. once elevated, runs automation\register_task_v2.ps1
rem
rem  If elevation is impossible on this PC, use the no-admin
rem  fallback instead:
rem    powershell -ExecutionPolicy Bypass -File automation\register_startup_v1.ps1
rem ===============================================================
setlocal EnableExtensions

rem --- are we already administrator? ------------------------------
net session >nul 2>&1
if not errorlevel 1 goto elevated

rem --- guard against an endless relaunch loop ----------------------
if /I "%~1"=="ELEV" goto elevfail

echo.
echo  gaachi - daily auto publish : register scheduled task
echo  ----------------------------------------------------
echo  Requesting administrator rights...
echo  A Windows UAC dialog will appear. Please choose YES.
echo.
powershell -NoProfile -Command "try { Start-Process -FilePath '%~f0' -ArgumentList 'ELEV' -Verb RunAs -ErrorAction Stop } catch { exit 1 }"
if errorlevel 1 goto uaccancel
echo  An elevated window has been opened. Please continue there.
echo  This window can be closed.
echo.
pause
endlocal & exit /b 0

:uaccancel
echo.
echo  [CANCELLED] The UAC prompt was declined, or elevation is
echo              blocked on this PC.
echo.
echo  Use the no-admin fallback instead. Copy this one line into
echo  PowerShell and run it:
echo.
echo    powershell -ExecutionPolicy Bypass -File "%~dp0register_startup_v1.ps1"
echo.
pause
endlocal & exit /b 1

:elevfail
echo.
echo  [ERROR] Still not running as administrator after elevation.
echo          This account probably has no administrator rights,
echo          or company policy blocks UAC elevation.
echo.
echo  Use the no-admin fallback instead. Copy this one line into
echo  PowerShell and run it:
echo.
echo    powershell -ExecutionPolicy Bypass -File "%~dp0register_startup_v1.ps1"
echo.
pause
endlocal & exit /b 1

:elevated
echo.
echo  Running as administrator.
echo  Registering the scheduled task...
echo.
if not exist "%~dp0register_task_v2.ps1" goto nops1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_task_v2.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo  [WARN] PowerShell exit code: %RC%
if not "%RC%"=="0" echo         If registration failed, try the no-admin fallback:
if not "%RC%"=="0" echo           powershell -ExecutionPolicy Bypass -File "%~dp0register_startup_v1.ps1"
echo.
pause
endlocal & exit /b %RC%

:nops1
echo.
echo  [ERROR] File not found:
echo          %~dp0register_task_v2.ps1
echo.
pause
endlocal & exit /b 2
