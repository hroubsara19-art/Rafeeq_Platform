@echo off
echo Adding Attention Tracker Server to Windows Startup...
cd /d "%~dp0"

REM Get the startup folder path
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

REM Create a shortcut in the startup folder
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP%\منصة رفيق Attention Tracker.lnk'); $s.TargetPath = '%CD%\start_attention_server.bat'; $s.WorkingDirectory = '%CD%'; $s.Save()"

echo Done! The Attention Tracker Server will now start automatically when you log in.
echo To remove it, delete the shortcut from: %STARTUP%
