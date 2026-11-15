@echo off
REM Register the app to start silently every time you log in (no admin needed)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$startup = [Environment]::GetFolderPath('Startup'); $lnk = Join-Path $startup 'FYP-App.lnk';" ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut($lnk);" ^
  "$s.TargetPath = 'C:\Windows\System32\wscript.exe';" ^
  "$s.Arguments = '\"C:\Users\jack\Desktop\fyp\start-app-hidden.vbs\"';" ^
  "$s.WorkingDirectory = 'C:\Users\jack\Desktop\fyp';" ^
  "$s.Description = 'Start FYP Streamlit app';" ^
  "$s.Save(); Write-Host ('Created: ' + $lnk)"
echo.
echo Done. The app will start silently next time you log in.
pause
