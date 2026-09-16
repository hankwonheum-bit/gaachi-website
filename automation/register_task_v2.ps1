<#
  가치앤같이 감정평가법인 — 사례 자동 게시 작업 등록 스크립트 v2
  ------------------------------------------------------------------
  v1 과 하는 일은 같고, 실행 대상만 v2 로 바꿨다.
      run_hidden_v2.vbs  ->  run_daily_v2.bat  ->  publish_case_v1.py
  v2 배치 파일은 ASCII 만 담고 있다. cmd.exe 가 배치 파일을 바이트 위치로
  되짚어 읽는 특성 때문에, chcp 65001 상태에서 한글이 들어 있으면 다음 줄
  중간부터 실행되는 오류가 생기기 때문이다.

  실행:  powershell -ExecutionPolicy Bypass -File .\automation\register_task_v2.ps1
  해제:  powershell -ExecutionPolicy Bypass -File .\automation\register_task_v2.ps1 -Remove
  동일 이름의 작업이 있으면 지우고 다시 만든다(몇 번 실행해도 안전).
#>
param(
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
chcp 65001 > $null

$TaskName = '가치앤같이_사례자동게시'

# 이 스크립트가 있는 폴더(automation)의 상위 폴더가 저장소 루트다.
# 경로를 하드코딩하지 않으므로 저장소를 옮겨도 그대로 동작한다.
if ($PSScriptRoot) {
    $Repo = Split-Path -Parent $PSScriptRoot
} else {
    $Repo = 'C:\Users\user\Documents\GitHub\gaachi-website'
}
$Vbs = Join-Path $Repo 'automation\run_hidden_v2.vbs'
$Bat = Join-Path $Repo 'automation\run_daily_v2.bat'

Write-Host ''
Write-Host '=== 가치앤같이 사례 자동 게시 — 작업 스케줄러 등록 v2 ===' -ForegroundColor Cyan

if (-not (Test-Path $Repo))                        { throw "저장소 폴더를 찾을 수 없습니다: $Repo" }
if (-not (Test-Path (Join-Path $Repo 'index.html'))) { throw "저장소 루트가 아닙니다(index.html 없음): $Repo" }
if (-not (Test-Path $Bat))                         { throw "실행 파일을 찾을 수 없습니다: $Bat" }

# --- 기존 작업 제거 (멱등) -------------------------------------------------
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "기존 작업을 제거했습니다: $TaskName" -ForegroundColor Yellow
}
if ($Remove) {
    if (-not $existing) { Write-Host "등록된 작업이 없습니다: $TaskName" -ForegroundColor Yellow }
    Write-Host '자동 게시 작업이 해제되었습니다.' -ForegroundColor Green
    return
}

# --- 실행 동작 -------------------------------------------------------------
# 창이 전혀 뜨지 않도록 VBS 런처를 거쳐 run_daily_v2.bat 을 호출한다.
if (Test-Path $Vbs) {
    $action = New-ScheduledTaskAction -Execute 'wscript.exe' `
        -Argument ('"{0}" //B //Nologo' -f $Vbs) -WorkingDirectory $Repo
    $how = 'wscript.exe -> run_hidden_v2.vbs -> run_daily_v2.bat (창 숨김)'
} else {
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' `
        -Argument ('/c "{0}"' -f $Bat) -WorkingDirectory $Repo
    $how = 'cmd.exe -> run_daily_v2.bat'
}

# --- 트리거 ----------------------------------------------------------------
# ① 로그온 3분 후 (네트워크가 올라올 시간 확보)
$trgLogon = New-ScheduledTaskTrigger -AtLogOn
$trgLogon.Delay = 'PT3M'
# ② 매일 09:00 (로컬 시간)
$trgDaily = New-ScheduledTaskTrigger -Daily -At '09:00'

# --- 설정 ------------------------------------------------------------------
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# --- 실행 주체: 현재 사용자, 관리자 권한 없이 --------------------------------
$userId = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $userId `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger @($trgLogon, $trgDaily) `
    -Settings $settings -Principal $principal `
    -Description '가치앤같이 감정평가 사례를 하루 1건 자동으로 홈페이지에 게시합니다. (automation/run_daily_v2.bat -> publish_case_v1.py)' | Out-Null

Write-Host ''
Write-Host '등록 완료!' -ForegroundColor Green
Write-Host ("  작업 이름 : {0}" -f $TaskName)
Write-Host ("  저장소    : {0}" -f $Repo)
Write-Host ("  실행 계정 : {0} (일반 권한)" -f $userId)
Write-Host ("  실행 방식 : {0}" -f $how)
Write-Host  '  트리거 ① : 로그온 3분 후'
Write-Host  '  트리거 ② : 매일 09:00'
Write-Host  '  설정      : 놓친 일정은 PC를 켰을 때 실행, 배터리에서도 실행/중단 안 함'
Write-Host ''
Write-Host '확인 방법 : 작업 스케줄러(taskschd.msc) → 작업 스케줄러 라이브러리 → ' -NoNewline
Write-Host $TaskName -ForegroundColor Cyan
Write-Host '지금 바로 시험 실행하려면 :' -ForegroundColor Cyan
Write-Host ("  Start-ScheduledTask -TaskName '{0}'" -f $TaskName)
Write-Host '실제 게시 없이 점검만 하려면 :' -ForegroundColor Cyan
Write-Host ("  cd '{0}'; py -3 automation\publish_case_v1.py --dry-run" -f $Repo)
Write-Host '설치 상태를 점검하려면 :' -ForegroundColor Cyan
Write-Host  '  automation\점검_v2.bat  (더블클릭)'
Write-Host ''
Write-Host '로그 위치 :' -ForegroundColor Cyan
Write-Host  '  automation\logs\publish-YYYYMMDD.log  (게시 기록)'
Write-Host  '  automation\logs\run_last.log          (마지막 실행 원본 출력)'
Write-Host ''
