Set WshShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Kill existing processes
WshShell.Run "taskkill /F /IM python.exe", 0, true
WshShell.Run "taskkill /F /IM waitress-serve.exe", 0, true
WScript.Sleep 2000

' Start services hidden
WshShell.Run chr(34) & strPath & "\venv\Scripts\waitress-serve.exe" & chr(34) & " --host=0.0.0.0 --port=5000 app:app", 0, false
WScript.Sleep 2000
WshShell.Run chr(34) & strPath & "\venv\Scripts\pythonw.exe" & chr(34) & " bot.py", 0, false
