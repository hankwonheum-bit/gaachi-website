' 가치앤같이 사례 자동 게시 - 창 없이 run_daily_v1.bat 실행 (작업 스케줄러용)
Option Explicit
Dim sh, bat, rc
Set sh = CreateObject("WScript.Shell")
bat = "C:\Users\user\Documents\GitHub\gaachi-website\automation\run_daily_v1.bat"
rc = sh.Run("""" & bat & """", 0, True)
WScript.Quit rc
