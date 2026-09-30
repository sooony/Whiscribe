$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = $PWD.Path }
$IconPath = Join-Path $ScriptDir "icon.ico"
$VbsPath = Join-Path $ScriptDir "run_silent.vbs"

$WshShell = New-Object -ComObject WScript.Shell

$ExePath = Join-Path $ScriptDir "dist\Whiscribe-Portable\Whiscribe.exe"
$UseExe = Test-Path $ExePath

$Target = if ($UseExe) { $ExePath } else { "wscript.exe" }
$Arguments = if ($UseExe) { "" } else { "`"$VbsPath`"" }
$WorkDir = if ($UseExe) { (Split-Path -Parent $ExePath) } else { $ScriptDir }
$Icon = if ($UseExe) { "$ExePath,0" } else { "$IconPath,0" }

# 1. Skrot w Menu Start Windows
$StartMenuDir = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs")
$StartMenuShortcut = Join-Path $StartMenuDir "Whiscribe.lnk"
$Shortcut1 = $WshShell.CreateShortcut($StartMenuShortcut)
$Shortcut1.TargetPath = $Target
$Shortcut1.Arguments = $Arguments
$Shortcut1.WorkingDirectory = $WorkDir
$Shortcut1.IconLocation = $Icon
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
$Shortcut2.TargetPath = $Target
$Shortcut2.Arguments = $Arguments
$Shortcut2.WorkingDirectory = $WorkDir
$Shortcut2.IconLocation = $Icon
$Shortcut2.Description = "Whiscribe - AI Voice Typing (Whisper Large-v3-Turbo)"
$Shortcut2.Save()
Write-Output "Desktop shortcut created: $DesktopShortcut"

# 3. Skrot w Autostarcie Windows (Startup) - automatyczne dzialanie po wlaczeniu komputera
$StartupDir = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs\Startup")
$StartupShortcut = Join-Path $StartupDir "Whiscribe.lnk"
$Shortcut3 = $WshShell.CreateShortcut($StartupShortcut)
$Shortcut3.TargetPath = $Target
$Shortcut3.Arguments = $Arguments
$Shortcut3.WorkingDirectory = $WorkDir
$Shortcut3.IconLocation = $Icon
$Shortcut3.Description = "Whiscribe - AI Voice Typing (Whisper Large-v3-Turbo)"
$Shortcut3.Save()
Write-Output "Startup shortcut created: $StartupShortcut"

# Usuniecie starych/zdezaktualizowanych skrotow jesli istnieja
$OldShortcuts = @(
    "Dyktowanie AI.lnk",
    "Whiscribe AI.lnk",
    "Whiscribe portable.lnk",
    "Whiscribe pyt.lnk"
)
foreach ($old in $OldShortcuts) {
    $p = Join-Path $DesktopPath $old
    if (Test-Path $p) {
        Remove-Item $p -Force
        Write-Output "Removed obsolete shortcut: $p"
    }
}

