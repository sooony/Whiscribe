$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = $PWD.Path }
$IconPath = Join-Path $ScriptDir "icon.ico"
$VbsPath = Join-Path $ScriptDir "run_silent.vbs"

$WshShell = New-Object -ComObject WScript.Shell

# 1. Skrot w Menu Start Windows
$StartMenuDir = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs")
$StartMenuShortcut = Join-Path $StartMenuDir "Whiscribe.lnk"
$Shortcut1 = $WshShell.CreateShortcut($StartMenuShortcut)
$Shortcut1.TargetPath = "wscript.exe"
$Shortcut1.Arguments = "`"$VbsPath`""
$Shortcut1.WorkingDirectory = $ScriptDir
$Shortcut1.IconLocation = "$IconPath,0"
$Shortcut1.Description = "Whiscribe - AI Voice Typing (Whisper Large-v3-Turbo)"
$Shortcut1.Save()
Write-Output "Start Menu shortcut created: $StartMenuShortcut"

# 2. Skrot na Pulpicie (Desktop)
$DesktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "OneDrive\Pulpit")
if (-not (Test-Path $DesktopPath)) {
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
}
$DesktopShortcut = Join-Path $DesktopPath "Whiscribe.lnk"
$Shortcut2 = $WshShell.CreateShortcut($DesktopShortcut)
$Shortcut2.TargetPath = "wscript.exe"
$Shortcut2.Arguments = "`"$VbsPath`""
$Shortcut2.WorkingDirectory = $ScriptDir
$Shortcut2.IconLocation = "$IconPath,0"
$Shortcut2.Description = "Whiscribe - AI Voice Typing (Whisper Large-v3-Turbo)"
$Shortcut2.Save()
Write-Output "Desktop shortcut created: $DesktopShortcut"

# Usuniecie starego skrotu 'Dyktowanie AI.lnk' jesli istnieje
$OldShortcut = Join-Path $DesktopPath "Dyktowanie AI.lnk"
if (Test-Path $OldShortcut) {
    Remove-Item $OldShortcut -Force
    Write-Output "Removed old shortcut: $OldShortcut"
}
