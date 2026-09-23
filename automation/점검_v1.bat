@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ===============================================================
rem  가치앤같이 사례 자동 게시 - 사전 점검 v1
rem  이 파일이 있는 폴더(automation)의 상위 폴더가 저장소 루트다.
rem ===============================================================
cd /d "%~dp0.." 2>nul
if errorlevel 1 goto :norepo
if not exist "index.html" goto :norepo

echo ============================================
echo  가치앤같이 사례 자동게시 - 사전 점검
echo ============================================
echo  저장소: %CD%
echo ============================================
echo.

rem ============================================ [1/5] Python
echo [1/5] Python 확인
set "PY="
set "PYVER="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY call :probe_py
if defined PYVER goto :py_done
where python >nul 2>&1
if errorlevel 1 goto :py_done
set "PY=python"
call :probe_py
:py_done
if not defined PYVER set "PY="
if defined PYVER goto :py_ok
echo   [실패] Python 을 찾을 수 없습니다.
echo          https://www.python.org/downloads/windows/ 에서 설치하고,
echo          설치 첫 화면의 Add python.exe to PATH 를 반드시 체크하세요.
goto :step2
:py_ok
echo   [정상] !PYVER!
echo          실행 명령: !PY!
:step2
echo.

rem ============================================ [2/5] Git
echo [2/5] Git 확인
set "GITEXE="
set "GITVER="
set "GITSRC="
if defined PY goto :git_probe
echo   [건너뜀] Python 이 없어 git 자동 탐색을 하지 못했습니다.
echo            먼저 Python 을 설치한 뒤 이 점검을 다시 실행하세요.
goto :step3
:git_probe
set "N=0"
for /f "delims=" %%a in ('!PY! "automation\find_git_v1.py" --check 2^>nul') do (
    set /a N+=1
    if !N!==1 set "GITEXE=%%a"
    if !N!==2 set "GITVER=%%a"
    if !N!==3 set "GITSRC=%%a"
)
if defined GITEXE goto :git_found
echo   [실패] git 을 찾을 수 없습니다.
echo          https://git-scm.com/download/win 에서 설치하세요.
echo          설치 방법 요약: automation\git_설치안내_v1.txt
goto :step3
:git_found
echo   [정상] !GITVER!
echo          경로: !GITEXE!
echo          출처: !GITSRC!
if /i not "!GITSRC!"=="GitHubDesktop" goto :step3
echo   [주의] GitHub Desktop 내장 git 을 사용합니다. 업데이트 시 경로가 바뀔 수 있으니
echo          Git for Windows 설치를 권장합니다: https://git-scm.com/download/win
:step3
echo.

rem ============================================ [3/5] GitHub 자격증명
echo [3/5] GitHub 자격증명 확인
if defined GITEXE goto :cred_run
echo   [건너뜀] git 이 없어 확인하지 못했습니다.
goto :step4
:cred_run
"!GITEXE!" ls-remote origin -h >nul 2>&1
if errorlevel 1 goto :cred_fail
echo   [정상] GitHub 원격 저장소에 접근할 수 있습니다.
goto :step4
:cred_fail
echo   [실패] GitHub 인증이 안 됩니다.
echo          - GitHub Desktop 을 열고 한 번 Push 해서 로그인 상태를 만들어 주세요.
echo          - 그래도 안 되면 아래 명령을 한 번 실행하세요:
echo            "!GITEXE!" config --global credential.helper manager
:step4
echo.

rem ============================================ [4/5] 미푸시 커밋
echo [4/5] 미푸시 커밋 확인
if defined GITEXE goto :ahead_run
echo   [건너뜀] git 이 없어 확인하지 못했습니다.
echo            GitHub Desktop 을 열면 푸시할 커밋이 있는지 바로 보입니다.
goto :step5
:ahead_run
set "AHEAD="
"!GITEXE!" rev-list --count origin/main..HEAD > "%TEMP%\gaachi_check_tmp.txt" 2>nul
if errorlevel 1 goto :ahead_fail
set /p AHEAD=<"%TEMP%\gaachi_check_tmp.txt"
del "%TEMP%\gaachi_check_tmp.txt" >nul 2>&1
if not defined AHEAD goto :ahead_fail
echo   [정상] 로컬에만 있는 커밋: !AHEAD! 건
if not "!AHEAD!"=="0" echo          GitHub Desktop 을 열고 Push 를 눌러 주세요.
goto :step5
:ahead_fail
del "%TEMP%\gaachi_check_tmp.txt" >nul 2>&1
echo   [주의] 미푸시 커밋 수를 확인하지 못했습니다.
echo          origin/main 정보가 아직 없을 수 있습니다. GitHub Desktop 에서 Fetch origin 을 한 번 눌러 주세요.
:step5
echo.

rem ============================================ [5/5] 대기열
echo [5/5] 대기열 상태
set "QCNT=0"
for %%f in (automation\queue\*.html) do set /a QCNT+=1
set "RCNT=0"
for %%f in (automation\review\*.html) do set /a RCNT+=1
echo   게시 대기 queue 폴더: !QCNT! 건
echo   승인 대기 review 폴더: !RCNT! 건
echo.

echo ============================================
echo  점검 완료
echo ============================================
echo.
pause
endlocal
exit /b 0

rem ============================================ 서브루틴
rem  python 버전을 확인해 성공하면 첫 줄을 PYVER 에 담는다.
rem  파이프를 쓰면 지연확장이 깨질 수 있으므로 임시 파일을 쓴다.
:probe_py
set "PYVER="
!PY! --version > "%TEMP%\gaachi_check_tmp.txt" 2>&1
if errorlevel 1 goto :probe_py_end
set /p PYVER=<"%TEMP%\gaachi_check_tmp.txt"
:probe_py_end
del "%TEMP%\gaachi_check_tmp.txt" >nul 2>&1
goto :eof

:norepo
echo [실패] 저장소 폴더를 찾을 수 없습니다.
echo        이 파일은 저장소 안의 automation 폴더에 있어야 합니다.
echo        기대 위치: C:\Users\user\Documents\GitHub\gaachi-website\automation\점검_v1.bat
echo.
pause
exit /b 1
