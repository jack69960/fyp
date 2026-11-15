@echo off
REM Remove the login autostart entry
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'FYP-App.lnk';" ^
  "if (Test-Path $lnk) { Remove-Item $lnk -Force; Write-Host ('Removed: ' + $lnk) } else { Write-Host 'Autostart entry not found.' }"
echo.
pause
