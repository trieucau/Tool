$desktop = [Environment]::GetFolderPath('Desktop')
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$desktop\Mo 3 App Movie AI.lnk")
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"E:\Tool\start_all_hidden.vbs`""
$Shortcut.WorkingDirectory = "E:\Tool"
$Shortcut.Save()
