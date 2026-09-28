On Error Resume Next
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
WshShell.Run Chr(34) & scriptDir & "\venv\Scripts\pythonw.exe" & Chr(34) & " " & Chr(34) & scriptDir & "\app.py" & Chr(34), 0
Set WshShell = Nothing
