On Error Resume Next
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

exePath = scriptDir & "\dist\Whiscribe-Portable\Whiscribe.exe"
If fso.FileExists(exePath) Then
    WshShell.CurrentDirectory = scriptDir & "\dist\Whiscribe-Portable"
    WshShell.Run Chr(34) & exePath & Chr(34), 0, False
Else
    WshShell.CurrentDirectory = scriptDir
    WshShell.Run Chr(34) & scriptDir & "\venv\Scripts\pythonw.exe" & Chr(34) & " " & Chr(34) & scriptDir & "\app.py" & Chr(34), 0, False
End If

Set WshShell = Nothing
