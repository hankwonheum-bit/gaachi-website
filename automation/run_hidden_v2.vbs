' gaachi - launch run_daily_v2.bat with no visible window (Task Scheduler)
' ASCII ONLY, on purpose. See run_daily_v2.bat for the reason.
Option Explicit
Dim sh, fso, bat, rc
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
bat = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "run_daily_v2.bat")
rc = sh.Run("""" & bat & """", 0, True)
WScript.Quit rc
