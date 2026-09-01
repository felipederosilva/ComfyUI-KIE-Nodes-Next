Option Explicit

Dim fso, sh, root, customNodes, userData, backupRoot, removed
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

root = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
If Not IsComfyRoot(root) Then
    MsgBox "The expected ComfyUI Desktop installation was not found:" & vbCrLf & root & vbCrLf & vbCrLf & "Nothing was changed.", 48, "KIE Nodes Next full uninstall"
    WScript.Quit 1
End If

If IsComfyRunning() Then
    MsgBox "Close ComfyUI completely, then run this uninstaller again.", 48, "KIE Nodes Next full uninstall"
    WScript.Quit 1
End If

customNodes = root & "\custom_nodes"
userData = root & "\user\KIE-Nodes-Next"
If MsgBox("This removes every active KIE Nodes Next folder from:" & vbCrLf & customNodes & vbCrLf & vbCrLf & "It also removes KIE Nodes Next saved settings/catalog data. ComfyUI, workflows, and other custom nodes are not touched." & vbCrLf & vbCrLf & "Removed files are moved to a backup outside ComfyUI.", 33, "Confirm KIE Nodes Next full uninstall") <> 1 Then
    WScript.Quit 0
End If

backupRoot = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\KIE-Nodes-Next\uninstalled\" & TimeStamp()
EnsureFolder backupRoot
removed = RemoveKieNodeFolders(customNodes, backupRoot)
If fso.FolderExists(userData) Then
    fso.MoveFolder userData, backupRoot & "\user-KIE-Nodes-Next"
    removed = removed + 1
End If
WriteReport backupRoot & "\uninstall-report.txt", root, removed

MsgBox "KIE Nodes Next has been fully uninstalled." & vbCrLf & vbCrLf & "Removed items: " & removed & vbCrLf & "Backup: " & backupRoot & vbCrLf & vbCrLf & "You can now place a clean KIE Nodes Next folder manually in:" & vbCrLf & customNodes, 64, "KIE Nodes Next full uninstall"

Function IsComfyRoot(path)
    IsComfyRoot = fso.FolderExists(path & "\custom_nodes") And fso.FileExists(path & "\main.py")
End Function

Function RemoveKieNodeFolders(customPath, backupPath)
    Dim folder, child, name, count
    count = 0
    Set folder = fso.GetFolder(customPath)
    For Each child In folder.SubFolders
        name = LCase(child.Name)
        If name = "comfyui-kie-nodes-next" Or name = "kie-nodes-next" Or InStr(name, "kie-nodes-next.backup") > 0 Then
            fso.MoveFolder child.Path, backupPath & "\" & child.Name & "-" & count
            count = count + 1
        End If
    Next
    RemoveKieNodeFolders = count
End Function

Function IsComfyRunning()
    Dim svc, procs, p, n, cmd
    IsComfyRunning = False
    On Error Resume Next
    Set svc = GetObject("winmgmts:\\.\root\cimv2")
    Set procs = svc.ExecQuery("SELECT Name, CommandLine FROM Win32_Process")
    For Each p In procs
        n = LCase(CStr(p.Name & ""))
        cmd = LCase(CStr(p.CommandLine & ""))
        If n = "comfyui.exe" Or (n = "python.exe" And InStr(cmd, "comfyui") > 0) Then IsComfyRunning = True
    Next
    On Error GoTo 0
End Function

Sub EnsureFolder(path)
    Dim parent
    If fso.FolderExists(path) Then Exit Sub
    parent = fso.GetParentFolderName(path)
    If parent <> "" And Not fso.FolderExists(parent) Then EnsureFolder parent
    If Not fso.FolderExists(path) Then fso.CreateFolder path
End Sub

Function TimeStamp()
    Dim d
    d = Now
    TimeStamp = Year(d) & Right("0" & Month(d), 2) & Right("0" & Day(d), 2) & "-" & Right("0" & Hour(d), 2) & Right("0" & Minute(d), 2) & Right("0" & Second(d), 2)
End Function

Sub WriteReport(path, comfyRoot, count)
    Dim out
    Set out = fso.CreateTextFile(path, True)
    out.WriteLine "KIE Nodes Next full uninstall"
    out.WriteLine "ComfyUI root: " & comfyRoot
    out.WriteLine "Removed items: " & count
    out.WriteLine "All items were moved outside ComfyUI."
    out.Close
End Sub
