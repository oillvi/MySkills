@echo off
rem 一次性安装：注册 roster-admin:// 协议（HKCU，免提权）
rem 之后双击 花名册管理.html 即可自动唤起后端
python "%~dp0server.py" --install
echo.
echo 完成。浏览器首次会弹一次"打开外部程序?"，勾选记住即可。
pause
