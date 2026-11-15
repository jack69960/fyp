@echo off
REM One-click launcher: Neo4j -> Streamlit -> browser
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-app.ps1"
if errorlevel 1 pause
