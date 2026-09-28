$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "OneDrive\Pulpit")
if (-not (Test-Path $DesktopPath)) {
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
}
$ShortcutPath = Join-Path $DesktopPath "Dyktowanie AI.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"C:\Users\filkn\OneDrive\Pulpit\Antigravity\wtyczka-dyktowanie\run_silent.vbs`""
$Shortcut.WorkingDirectory = "C:\Users\filkn\OneDrive\Pulpit\Antigravity\wtyczka-dyktowanie"
$Shortcut.IconLocation = "C:\Users\filkn\OneDrive\Pulpit\Antigravity\wtyczka-dyktowanie\icon.ico"
$Shortcut.Description = "Dyktowanie Mowy & Spotkania AI (Whisper RTX 3060)"
$Shortcut.Save()
Write-Output "Shortcut created at $ShortcutPath targeting run_silent.vbs"
