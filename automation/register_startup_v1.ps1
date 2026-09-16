<#
  가치앤같이 감정평가법인 — 사례 자동 게시 "시작프로그램" 등록 스크립트 v1
  ------------------------------------------------------------------
  관리자 권한이 필요 없는 대안(Plan B)이다.

  이 PC 에서는 작업 스케줄러 등록(Register-ScheduledTask)이 관리자 권한을
  요구해서, 일반 권한으로 실행하면 "Access is denied"(0x80070005) 로 실패한다.
  그래서 이 스크립트는 작업 스케줄러를 쓰지 않고, 사용자 계정의
  "시작프로그램" 폴더에 바로 가기를 하나 만들어 로그온할 때마다 실행되게 한다.
  시작프로그램 폴더는 사용자 본인 폴더이므로 관리자 권한이 전혀 필요 없다.

      시작프로그램\가치앤같이_사례자동게시.lnk
          -> wscript.exe "...\automation\run_hidden_v2.vbs" //B //Nologo
          -> run_daily_v2.bat -> publish_case_v1.py

  실행:  powershell -ExecutionPolicy Bypass -File .\automation\register_startup_v1.ps1
  해제:  powershell -ExecutionPolicy Bypass -File .\automation\register_startup_v1.ps1 -Remove
  같은 이름의 바로 가기가 있으면 덮어쓴다(몇 번 실행해도 안전).

  [바로 가기 대상(TargetPath)으로 .vbs 가 아니라 wscript.exe 를 쓰는 이유]
  .vbs 파일을 TargetPath 로 직접 지정하면 실행이 .vbs 파일 연결
  (HKCR\VBSFile\shell\open\command)에 의존하게 된다. 백신이나 회사 보안
  정책이 .vbs 연결을 메모장으로 바꿔 두거나 아예 막아 두는 경우가 드물지
  않고, 그러면 로그온할 때마다 메모장이 뜨거나 아무 일도 일어나지 않는다.
  또 바로 가기의 WindowStyle(창 모드)은 실행 파일을 대상으로 할 때만
  제대로 적용된다. wscript.exe 를 대상으로 두고 .vbs 를 인수로 넘기면 파일
  연결과 무관하게 동작하고, register_task_v2.ps1 이 작업 스케줄러에 넣는
  실행 방식과도 정확히 같아진다.
#>
param(
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
chcp 65001 > $null

$LinkName = '가치앤같이_사례자동게시.lnk'

# 이 스크립트가 있는 폴더(automation)의 상위 폴더가 저장소 루트다.
# 경로를 하드코딩하지 않으므로 저장소를 옮겨도 그대로 동작한다.
if ($PSScriptRoot) {
    $Repo = Split-Path -Parent $PSScriptRoot
} else {
    $Repo = 'C:\Users\user\Documents\GitHub\gaachi-website'
}
$Vbs        = Join-Path $Repo 'automation\run_hidden_v2.vbs'
$Bat        = Join-Path $Repo 'automation\run_daily_v2.bat'
$WScriptExe = Join-Path $env:SystemRoot 'System32\wscript.exe'

# 시작프로그램 폴더는 하드코딩하지 않고 Windows 에게 직접 물어본다.
# (OneDrive 리디렉션이나 한글 사용자 폴더에서도 정확히 찾아낸다.)
$Startup  = [Environment]::GetFolderPath('Startup')
$LinkPath = Join-Path $Startup $LinkName

Write-Host ''
Write-Host '=== 가치앤같이 사례 자동 게시 — 시작프로그램 등록 v1 (관리자 권한 불필요) ===' -ForegroundColor Cyan
Write-Host ("  시작프로그램 폴더 : {0}" -f $Startup)
Write-Host ("  바로 가기 파일    : {0}" -f $LinkPath)
Write-Host ''

if ([string]::IsNullOrWhiteSpace($Startup)) {
    throw "시작프로그램 폴더 경로를 가져오지 못했습니다. Windows 사용자 프로필이 손상되었을 수 있습니다."
}

# --- 해제 ------------------------------------------------------------------
if ($Remove) {
    if (Test-Path -LiteralPath $LinkPath) {
        Remove-Item -LiteralPath $LinkPath -Force
        Write-Host '시작프로그램 등록을 해제했습니다.' -ForegroundColor Green
        Write-Host ("  삭제한 파일 : {0}" -f $LinkPath)
    } else {
        Write-Host '등록된 바로 가기가 없습니다. 해제할 것이 없습니다.' -ForegroundColor Yellow
    }
    Write-Host ''
    return
}

# --- 사전 점검 --------------------------------------------------------------
if (-not (Test-Path -LiteralPath $Startup))                       { throw "시작프로그램 폴더를 찾을 수 없습니다: $Startup" }
if (-not (Test-Path -LiteralPath $Repo))                          { throw "저장소 폴더를 찾을 수 없습니다: $Repo" }
if (-not (Test-Path -LiteralPath (Join-Path $Repo 'index.html'))) { throw "저장소 루트가 아닙니다(index.html 없음): $Repo" }
if (-not (Test-Path -LiteralPath $Bat))                           { throw "실행 파일을 찾을 수 없습니다: $Bat" }
if (-not (Test-Path -LiteralPath $Vbs))                           { throw "창 숨김 실행 파일을 찾을 수 없습니다: $Vbs" }
if (-not (Test-Path -LiteralPath $WScriptExe))                    { throw "wscript.exe 를 찾을 수 없습니다: $WScriptExe" }

# --- 멱등: 이미 있으면 덮어쓴다 ---------------------------------------------
$overwrote = Test-Path -LiteralPath $LinkPath
if ($overwrote) {
    Write-Host '같은 이름의 바로 가기가 이미 있습니다. 새 내용으로 덮어씁니다.' -ForegroundColor Yellow
    Write-Host ''
}

# --- 바로 가기 생성 ---------------------------------------------------------
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($LinkPath)
$lnk.TargetPath       = $WScriptExe
$lnk.Arguments        = ('"{0}" //B //Nologo' -f $Vbs)
$lnk.WorkingDirectory = $Repo
$lnk.Description      = '가치앤같이 감정평가 사례 자동 게시'
$lnk.WindowStyle      = 7
$lnk.IconLocation     = ('{0},0' -f $WScriptExe)
$lnk.Save()

# --- 검증: 실제로 만들어졌는지, 값이 제대로 들어갔는지 다시 읽어 확인한다 ------
if (-not (Test-Path -LiteralPath $LinkPath)) {
    throw "바로 가기를 만들지 못했습니다: $LinkPath"
}
$verify = $shell.CreateShortcut($LinkPath)

Write-Host '등록 완료!' -ForegroundColor Green
if ($overwrote) {
    Write-Host '  (기존 바로 가기를 덮어썼습니다.)' -ForegroundColor Yellow
}
Write-Host ("  시작프로그램 폴더 : {0}" -f $Startup)
Write-Host ("  바로 가기 파일    : {0}" -f $LinkPath)
Write-Host ("  실행 대상         : {0}" -f $verify.TargetPath)
Write-Host ("  인수              : {0}" -f $verify.Arguments)
Write-Host ("  작업 폴더         : {0}" -f $verify.WorkingDirectory)
Write-Host ("  설명              : {0}" -f $verify.Description)
Write-Host ("  창 모드           : {0}  (7 = 최소화, 창이 뜨지 않음)" -f $verify.WindowStyle)
Write-Host ''
Write-Host '이제 이 PC 에 로그온할 때마다, 로그온하고 약 10~20초 뒤에' -ForegroundColor Green
Write-Host '사례 자동 게시가 창 없이 조용히 한 번 실행됩니다.' -ForegroundColor Green
Write-Host '(정확한 시간은 PC 사양과 시작프로그램 개수에 따라 조금 달라집니다.)'
Write-Host ''
Write-Host '[꼭 알아 두실 점]' -ForegroundColor Yellow
Write-Host '  시작프로그램은 "로그온할 때"만 실행됩니다. 정해진 시각에 실행되는 것이 아닙니다.'
Write-Host '  그래서 컴퓨터를 끄지 않고 며칠 계속 켜 두는 날에는, 그동안 한 번도 실행되지 않습니다.'
Write-Host '  가능하면 관리자 권한으로 automation\관리자로_등록하기_v1.bat 을 실행해서'
Write-Host '  register_task_v2.ps1 (작업 스케줄러)로 등록하는 편이 낫습니다.'
Write-Host '  작업 스케줄러는 매일 09:00 에도 실행하므로, PC 를 계속 켜 두어도 매일 게시됩니다.'
Write-Host ''
Write-Host '확인 방법 :' -ForegroundColor Cyan
Write-Host '  Win + R  ->  shell:startup  ->  확인  ->  가치앤같이_사례자동게시 바로 가기가 보이면 등록된 것입니다.'
Write-Host '해제 방법 :' -ForegroundColor Cyan
Write-Host '  powershell -ExecutionPolicy Bypass -File .\automation\register_startup_v1.ps1 -Remove'
Write-Host '지금 바로 시험 실행하려면 :' -ForegroundColor Cyan
Write-Host ("  wscript.exe ""{0}"" //B //Nologo" -f $Vbs)
Write-Host '실제 게시 없이 점검만 하려면 :' -ForegroundColor Cyan
Write-Host ("  cd '{0}'; py -3 automation\publish_case_v1.py --dry-run" -f $Repo)
Write-Host '설치 상태를 점검하려면 :' -ForegroundColor Cyan
Write-Host  '  automation\점검_v2.bat  (더블클릭)'
Write-Host ''
Write-Host '로그 위치 :' -ForegroundColor Cyan
Write-Host  '  automation\logs\publish-YYYYMMDD.log  (게시 기록)'
Write-Host  '  automation\logs\run_last.log          (마지막 실행 원본 출력)'
Write-Host ''
