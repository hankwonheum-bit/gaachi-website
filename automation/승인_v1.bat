@echo off
rem ===============================================================
rem  가치앤같이 사례 초안 승인 — 더블클릭 실행용 v1
rem  automation/review/ 의 초안을 확인하고 번호로 승인한다.
rem ===============================================================
chcp 65001 >nul
setlocal EnableExtensions

set "REPO=C:\Users\user\Documents\GitHub\gaachi-website"
cd /d "%REPO%"
if errorlevel 1 (
    echo 저장소 폴더를 찾을 수 없습니다: %REPO%
    pause
    exit /b 8
)

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo 오류: python 을 찾을 수 없습니다. ^(py -3 / python 모두 실패^)
    pause
    exit /b 9
)

echo.
%PY% "automation\approve_v1.py" --list
echo.
echo  - 초안을 먼저 브라우저로 열어 확인하십시오.
echo    예^) automation\review 폴더에서 HTML 파일을 더블클릭
echo  - 체크리스트: automation\검토_체크리스트_v1.md
echo.

set "SEL="
set /p "SEL=승인할 번호를 입력하고 Enter (그냥 Enter 를 누르면 종료): "
if not defined SEL goto :done

echo.
%PY% "automation\approve_v1.py" --approve %SEL%
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
    echo 승인이 완료되지 않았습니다. 위 메시지를 확인하십시오.
    echo 반려하려면 PowerShell 에서 다음을 실행하십시오:
    echo   python automation\approve_v1.py --reject %SEL% --reason "반려 사유"
    goto :done
)

%PY% "automation\approve_v1.py" --status

:done
echo.
pause
endlocal
