@echo off
REM Stop Streamlit (port 8501) and Neo4j
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$conns = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue;" ^
  "if ($conns) { $conns | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Write-Host ('Stopping Streamlit PID ' + $_); Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }" ^
  "else { Write-Host 'Streamlit is not running.' }"
call "C:\Users\jack\neo4j\stop-neo4j.bat"
echo.
pause
