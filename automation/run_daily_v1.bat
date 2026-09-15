@echo off
rem ===============================================================
rem  가치앤같이 사례 자동 게시 — 일일 실행 래퍼 v1
rem  작업 스케줄러가 호출한다. 창을 띄우지 않고 로그만 남긴다.
rem ===============================================================
chcp 65001 >nul
setlocal EnableExtensions

set "REPO=C:\Users\user\Documents\GitHub\gaachi-website"
cd /d "%REPO%" || exit /b 8

if not exist "automation\logs" mkdir "automation\logs"

set "TODAY="
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd" 2^>nul') do set "TODAY=%%I"
if not defined TODAY set "TODAY=unknown"
set "RUNLOG=automation\logs\run-%TODAY%.log"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    >>"%RUNLOG%" echo [%DATE% %TIME%] 오류: python 을 찾을 수 없습니다 ^(py -3 / python 모두 실패^)
    endlocal & exit /b 9
)

>>"%RUNLOG%" echo.
>>"%RUNLOG%" echo ==== %DATE% %TIME% 실행 시작 (%PY%) ====
%PY% "automation\publish_case_v1.py" %* >>"%RUNLOG%" 2>&1
set "RC=%ERRORLEVEL%"
>>"%RUNLOG%" echo ==== 종료 코드 %RC% ====

endlocal & exit /b %RC%
