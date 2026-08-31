# 바탕화면에 "노트 메모" 바로가기를 만든다.
#   powershell -ExecutionPolicy Bypass -File tools\create_shortcut.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$icon = Join-Path $root "assets\note_memo.ico"

if (-not (Test-Path $pythonw)) {
    Write-Error "가상환경이 없습니다. 먼저 run.bat 을 한 번 실행하세요: $pythonw"
}
if (-not (Test-Path $icon)) {
    & $pythonw (Join-Path $root "tools\make_icon.py")
}

$desktop = [Environment]::GetFolderPath("Desktop")
$linkPath = Join-Path $desktop "노트 메모.lnk"

$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($linkPath)
# pythonw.exe 를 직접 가리켜 콘솔 창이 뜨지 않게 한다.
$link.TargetPath = $pythonw
$link.Arguments = '"' + (Join-Path $root "main.py") + '"'
$link.WorkingDirectory = $root
$link.IconLocation = $icon
$link.Description = "날짜별 다이어리 노트"
$link.Save()

Write-Host "바로가기 생성: $linkPath"
