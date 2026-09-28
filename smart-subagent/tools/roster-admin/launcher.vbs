' roster-admin:// 协议唤起器：静默拉起 server.py（已有人在跑则 server 自己退出）
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
server = dir & "\server.py"

started = False
On Error Resume Next
sh.Run "pythonw.exe """ & server & """", 0, False
If Err.Number = 0 Then started = True
Err.Clear
If Not started Then
  sh.Run "cmd.exe /c start """" /min python.exe """ & server & """", 0, False
End If
