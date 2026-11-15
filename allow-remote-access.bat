@echo off
REM 一次性脚本：让 Windows 防火墙放行 8501 端口，手机/平板/别的电脑才能连进来
REM 需要管理员权限，双击后点「是」即可
net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo 正在申请管理员权限，请在弹出的窗口点「是」...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
netsh advfirewall firewall delete rule name="FYP Streamlit 8501" >nul 2>&1
netsh advfirewall firewall add rule name="FYP Streamlit 8501" dir=in action=allow protocol=TCP localport=8501 profile=private,public
if "%errorlevel%"=="0" (
    echo.
    echo 已放行 TCP 8501。以后手机在同一 Wi-Fi 或开着 Tailscale 时就能直接打开。
) else (
    echo.
    echo 放行失败，请把这个窗口截图给饲养员。
)
echo.
pause
