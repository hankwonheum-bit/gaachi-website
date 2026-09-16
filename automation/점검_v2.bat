@echo off
rem ===============================================================
rem  gaachi - pre-flight check launcher v2
rem  This .bat is ASCII-only on purpose.
rem  cmd.exe tracks a BYTE OFFSET into the running batch file and
rem  re-seeks after every command. With chcp 65001 and multi-byte
rem  (Korean) text inside the file that offset drifts, so execution
rem  resumes in the middle of a later line. All Korean output lives
rem  in check_v2.py instead.
rem ===============================================================
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (python --version >nul 2>&1 && set "PY=python")
if not defined PY goto nopy
%PY% "%~dp0check_v2.py"
goto done
:nopy
echo [ERROR] Python not found. Install from https://www.python.org/downloads/
echo         Check "Add python.exe to PATH" during installation.
:done
echo.
pause
