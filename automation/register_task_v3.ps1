<#
  가치앤같이 감정평가법인 — 사례 자동 게시 작업 등록 스크립트 v3
  ------------------------------------------------------------------
  v2 와 등록하는 내용은 똑같다. 달라진 점은 "실패를 다루는 방식"뿐이다.
      run_hidden_v2.vbs  ->  run_daily_v2.bat  ->  publish_case_v1.py

  v2 대비 추가된 것
    1) 맨 처음에 관리자 권한 여부를 확인하고, 관리자가 아니면 실패할
       가능성이 높다는 것과 해결 방법 두 가지를 먼저 알려 준다.
       (그래도 등록은 일단 시도한다. 일반 권한으로 되는 PC 도 있다.)
    2) Register-ScheduledTask 를 try/catch 로 감싼다. 권한 오류
       (Access is denied / 0x80070005)면 .NET 예외를 그대로 쏟지 않고
       한국어 설명과 다음에 할 일을 알려 준다.
    3) cmdlet 이 실패하면 포기하기 전에 schtasks.exe /Create /XML 로
       한 번 더 시도한다.
       솔직히 말하면 성공 확률은 높지 않다. cmdlet 과 schtasks.exe 는
       결국 같은 작업 스케줄러 서비스와 같은 접근 권한을 거치기 때문이다.
       다만 cmdlet 은 WMI/CIM(Root\Microsoft\Windows\TaskScheduler)을,
       schtasks.exe 는 COM(ITaskService)을 쓰므로, WMI 쪽만 막혀 있는
       설정에서는 드물게 schtasks.exe 가 통한다. 비용이 없으니 시도한다.
       기대는 하지 말고, 실패하면 아래 두 가지 방법을 쓰면 된다.
    4) -Remove 는 cmdlet 과 schtasks.exe 양쪽 모두로 동작한다.

  참고: schtasks.exe /Create /SC ONLOGON /TR ... 방식은 일부러 쓰지 않았다.
  /TR 인수 안에 따옴표를 중첩해야 하는데 PowerShell 이 네이티브 실행 파일에
  인수를 넘길 때 따옴표 처리가 버전마다 달라서, 등록은 되었는데 실제로는
  실행되지 않는 "겉보기 성공"이 생길 수 있다. 조용히 망가진 작업이
  등록 실패보다 나쁘므로, 모든 설정을 그대로 담을 수 있는 /XML 만 쓴다.

  실행:  powershell -ExecutionPolicy Bypass -File .\automation\register_task_v3.ps1
  해제:  powershell -ExecutionPolicy Bypass -File .\automation\register_task_v3.ps1 -Remove
  동일 이름의 작업이 있으면 지우고 다시 만든다(몇 번 실행해도 안전).

  v2(register_task_v2.ps1)는 그대로 두었다. 둘 중 아무거나 써도 된다.
#>
param(
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
chcp 65001 > $null

$TaskName = '가치앤같이_사례자동게시'
$Desc     = '가치앤같이 감정평가 사례를 하루 1건 자동으로 홈페이지에 게시합니다. (automation/run_daily_v2.bat -> publish_case_v1.py)'

# --- 관리자 권한 확인 (맨 먼저) ---------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

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
Write-Host '=== 가치앤같이 사례 자동 게시 — 작업 스케줄러 등록 v3 ===' -ForegroundColor Cyan
Write-Host ''
if ($isAdmin) {
    Write-Host '  권한 상태 : 관리자 권한으로 실행 중입니다. 좋습니다.' -ForegroundColor Green
} else {
    Write-Host '  권한 상태 : 일반(비관리자) 권한으로 실행 중입니다.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '  [경고] 이 PC 에서는 작업 스케줄러 등록에 관리자 권한이 필요할 가능성이 높습니다.' -ForegroundColor Yellow
    Write-Host '         이대로 진행하면 Access is denied (0x80070005) 로 실패할 수 있습니다.' -ForegroundColor Yellow
    Write-Host '         실패하면 다음 두 가지 중 하나로 해결하시면 됩니다.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '           방법 A (권장) : automation\관리자로_등록하기_v1.bat 더블클릭'
    Write-Host '                           UAC 창이 뜨면 [예] 를 누르세요.'
    Write-Host '                           관리자 권한으로 작업 스케줄러 등록을 다시 시도합니다.'
    Write-Host '                           로그온 3분 후 + 매일 09:00 실행.'
    Write-Host ''
    Write-Host '           방법 B         : 관리자 권한을 쓸 수 없을 때 (회사 정책 등)'
    Write-Host '                           powershell -ExecutionPolicy Bypass -File .\automation\register_startup_v1.ps1'
    Write-Host '                           시작프로그램에 등록되어 로그온할 때마다 실행됩니다.'
    Write-Host '                           관리자 권한이 전혀 필요 없습니다.'
    Write-Host ''
    Write-Host '  일반 권한으로도 등록이 되는 PC 가 있으므로, 일단 이대로 시도해 봅니다.' -ForegroundColor Yellow
}
Write-Host ''

# ---------------------------------------------------------------------------
#  보조 함수
# ---------------------------------------------------------------------------
function Invoke-Schtasks {
    # schtasks.exe 를 호출하고 (종료코드, 출력) 을 돌려준다.
    # 네이티브 명령이 stderr 에 쓰는 것 때문에 스크립트가 중단되지 않도록
    # 이 안에서만 ErrorActionPreference 를 잠시 낮춘다.
    param([string[]]$SchArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & schtasks.exe @SchArgs 2>&1
        $code = $LASTEXITCODE
    } catch {
        $out  = $_.Exception.Message
        $code = -1
    } finally {
        $ErrorActionPreference = $prev
    }
    return [PSCustomObject]@{ Code = $code; Output = ($out | Out-String).Trim() }
}

function Test-GaachiTask {
    # 작업이 실제로 등록되어 있는지 확인한다. cmdlet -> schtasks 순으로 본다.
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) { return $true }
    $r = Invoke-Schtasks @('/Query', '/TN', $TaskName)
    return ($r.Code -eq 0)
}

function Remove-GaachiTask {
    # cmdlet 과 schtasks.exe 양쪽으로 제거를 시도한다.
    $removed = $false
    try {
        $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($existing) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            Write-Host ("기존 작업을 제거했습니다(cmdlet): {0}" -f $TaskName) -ForegroundColor Yellow
            $removed = $true
        }
    } catch {
        Write-Host ("cmdlet 으로는 제거하지 못했습니다: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
    }
    if (-not $removed) {
        $r = Invoke-Schtasks @('/Delete', '/TN', $TaskName, '/F')
        if ($r.Code -eq 0) {
            Write-Host ("기존 작업을 제거했습니다(schtasks.exe): {0}" -f $TaskName) -ForegroundColor Yellow
            $removed = $true
        }
    }
    return $removed
}

function ConvertTo-XmlText {
    param([string]$Text)
    return $Text.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')
}

# --- 해제 ------------------------------------------------------------------
# (해제는 저장소 파일이 없어도 되어야 하므로 경로 점검보다 먼저 처리한다.)
if ($Remove) {
    $done = Remove-GaachiTask
    if ($done) {
        Write-Host '자동 게시 작업이 해제되었습니다.' -ForegroundColor Green
    } else {
        Write-Host ("등록된 작업이 없습니다: {0}" -f $TaskName) -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host '참고: 시작프로그램(방법 B)으로도 등록해 두셨다면 그쪽은 따로 해제해야 합니다.' -ForegroundColor Cyan
    Write-Host '  powershell -ExecutionPolicy Bypass -File .\automation\register_startup_v1.ps1 -Remove'
    Write-Host ''
    return
}

# --- 사전 점검 --------------------------------------------------------------
if (-not (Test-Path $Repo))                        { throw "저장소 폴더를 찾을 수 없습니다: $Repo" }
if (-not (Test-Path (Join-Path $Repo 'index.html'))) { throw "저장소 루트가 아닙니다(index.html 없음): $Repo" }
if (-not (Test-Path $Bat))                         { throw "실행 파일을 찾을 수 없습니다: $Bat" }

# --- 기존 작업 제거 (멱등) ---------------------------------------------------
$null = Remove-GaachiTask

# --- 실행 동작 --------------------------------------------------------------
# 창이 전혀 뜨지 않도록 VBS 런처를 거쳐 run_daily_v2.bat 을 호출한다.
if (Test-Path $Vbs) {
    $exeName = 'wscript.exe'
    $exeArgs = ('"{0}" //B //Nologo' -f $Vbs)
    $how     = 'wscript.exe -> run_hidden_v2.vbs -> run_daily_v2.bat (창 숨김)'
} else {
    $exeName = 'cmd.exe'
    $exeArgs = ('/c "{0}"' -f $Bat)
    $how     = 'cmd.exe -> run_daily_v2.bat'
}
$action = New-ScheduledTaskAction -Execute $exeName -Argument $exeArgs -WorkingDirectory $Repo

# --- 트리거 -----------------------------------------------------------------
# ① 로그온 3분 후 (네트워크가 올라올 시간 확보)
$trgLogon = New-ScheduledTaskTrigger -AtLogOn
$trgLogon.Delay = 'PT3M'
# ② 매일 09:00 (로컬 시간)
$trgDaily = New-ScheduledTaskTrigger -Daily -At '09:00'

# --- 설정 -------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
#  1차 시도 : Register-ScheduledTask (cmdlet)
# ---------------------------------------------------------------------------
$registered = $false
$howRegistered = ''
$firstError = ''
$wasDenied = $false

try {
    Register-ScheduledTask -TaskName $TaskName `
        -Action $action -Trigger @($trgLogon, $trgDaily) `
        -Settings $settings -Principal $principal `
        -Description $Desc | Out-Null
    $registered = $true
    $howRegistered = 'Register-ScheduledTask (PowerShell cmdlet)'
} catch {
    $firstError = $_.Exception.Message
    $wasDenied = ($firstError -match '0x80070005') -or
                 ($firstError -match 'Access is denied') -or
                 ($firstError -match '액세스가 거부')
    Write-Host ''
    if ($wasDenied) {
        Write-Host '[1차 실패] 권한이 없어 작업 스케줄러에 등록하지 못했습니다.' -ForegroundColor Red
        Write-Host '  Windows 가 돌려준 오류 : Access is denied (0x80070005)'
        Write-Host '  뜻 : 이 PC 는 작업 스케줄러에 새 작업을 만들 때 관리자 권한을 요구합니다.'
    } else {
        Write-Host '[1차 실패] 작업 스케줄러 등록 중 오류가 발생했습니다.' -ForegroundColor Red
        Write-Host ("  오류 내용 : {0}" -f $firstError)
    }
    Write-Host ''
    Write-Host '포기하기 전에 schtasks.exe 로 한 번 더 시도합니다...' -ForegroundColor Yellow
    Write-Host '(cmdlet 과 같은 서비스를 쓰므로 크게 기대하지는 마세요. 다만 통하는 PC 가 가끔 있습니다.)'
}

# ---------------------------------------------------------------------------
#  2차 시도 : schtasks.exe /Create /XML
#  cmdlet 이 만들던 설정(로그온 3분 후 / 매일 09:00 / 놓친 일정 실행 /
#  배터리에서도 실행 / 중복 실행 무시 / 1시간 제한 / 일반 권한)을
#  그대로 XML 로 옮겨 담는다.
# ---------------------------------------------------------------------------
if (-not $registered) {
    $xmlPath = $null
    try {
        $xmlTemplate = @'
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>{0}</Author>
    <Description>{1}</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{0}</UserId>
      <Delay>PT3M</Delay>
    </LogonTrigger>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T09:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{0}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{2}</Command>
      <Arguments>{3}</Arguments>
      <WorkingDirectory>{4}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
'@

        $xml = $xmlTemplate -f `
            (ConvertTo-XmlText $userId), `
            (ConvertTo-XmlText $Desc), `
            (ConvertTo-XmlText $exeName), `
            (ConvertTo-XmlText $exeArgs), `
            (ConvertTo-XmlText $Repo)

        # schtasks.exe 의 /XML 은 UTF-16(유니코드) 파일만 제대로 읽는다.
        $xmlPath = Join-Path $env:TEMP ('gaachi_task_{0}.xml' -f (Get-Date -Format 'yyyyMMddHHmmss'))
        [IO.File]::WriteAllText($xmlPath, $xml, [Text.Encoding]::Unicode)

        $r = Invoke-Schtasks @('/Create', '/TN', $TaskName, '/XML', $xmlPath, '/F')
        if ($r.Code -eq 0 -and (Test-GaachiTask)) {
            $registered = $true
            $howRegistered = 'schtasks.exe /Create /XML'
            Write-Host ''
            Write-Host '[2차 성공] schtasks.exe 로 등록되었습니다.' -ForegroundColor Green
        } else {
            Write-Host ''
            Write-Host '[2차 실패] schtasks.exe 로도 등록하지 못했습니다.' -ForegroundColor Red
            if ($r.Output) {
                Write-Host ("  schtasks.exe 출력 : {0}" -f $r.Output)
            }
        }
    } catch {
        Write-Host ''
        Write-Host ("[2차 실패] schtasks.exe 시도 중 오류: {0}" -f $_.Exception.Message) -ForegroundColor Red
    } finally {
        if ($xmlPath -and (Test-Path $xmlPath)) {
            Remove-Item $xmlPath -Force -ErrorAction SilentlyContinue
        }
    }
}

# ---------------------------------------------------------------------------
#  둘 다 실패 : 무엇을 하면 되는지 알려 주고 끝낸다
# ---------------------------------------------------------------------------
if (-not $registered) {
    Write-Host ''
    Write-Host '=== 작업 스케줄러 등록에 실패했습니다 ===' -ForegroundColor Red
    Write-Host ''
    Write-Host '이 PC 는 작업 스케줄러에 작업을 만들 때 관리자 권한을 요구합니다.'
    Write-Host '아래 두 가지 중 하나를 하시면 됩니다. 위쪽을 먼저 시도해 보세요.'
    Write-Host ''
    Write-Host '  방법 A (권장) : 관리자 권한으로 등록' -ForegroundColor Cyan
    Write-Host '    파일 탐색기에서 automation 폴더를 열고'
    Write-Host '      관리자로_등록하기_v1.bat'
    Write-Host '    파일을 더블클릭한 뒤, UAC 창에서 [예] 를 누르세요.'
    Write-Host '    -> 로그온 3분 후 + 매일 09:00 에 실행됩니다.'
    Write-Host '    -> 컴퓨터를 계속 켜 두어도 매일 실행됩니다.'
    Write-Host ''
    Write-Host '  방법 B : 관리자 권한을 쓸 수 없을 때 (시작프로그램 방식)' -ForegroundColor Cyan
    Write-Host '    PowerShell 에 아래 한 줄을 붙여 넣고 실행하세요.'
    Write-Host '      powershell -ExecutionPolicy Bypass -File .\automation\register_startup_v1.ps1'
    Write-Host '    -> 로그온할 때마다 실행됩니다. 관리자 권한이 전혀 필요 없습니다.'
    Write-Host '    -> 다만 컴퓨터를 며칠 계속 켜 두는 기간에는 실행되지 않습니다.'
    Write-Host ''
    Write-Host '자세한 설명 : automation\자동실행_등록_안내_v1.md' -ForegroundColor Cyan
    Write-Host ''
    exit 1
}

# ---------------------------------------------------------------------------
#  성공
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '등록 완료!' -ForegroundColor Green
Write-Host ("  작업 이름 : {0}" -f $TaskName)
Write-Host ("  저장소    : {0}" -f $Repo)
Write-Host ("  실행 계정 : {0} (일반 권한)" -f $userId)
Write-Host ("  실행 방식 : {0}" -f $how)
Write-Host ("  등록 경로 : {0}" -f $howRegistered)
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
