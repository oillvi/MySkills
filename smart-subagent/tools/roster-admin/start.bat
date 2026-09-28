@echo off
rem 兜底入口（协议未注册时用）：起后端 + 开页面
start "" /b pythonw.exe "%~dp0server.py" 2>nul
if errorlevel 1 start "" /min python.exe "%~dp0server.py"
start "" "http://127.0.0.1:8765/"
