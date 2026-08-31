@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" goto check

echo [note_memo] 첫 실행: 가상환경을 만들고 PySide6를 설치합니다. 몇 분 걸립니다...
py -3 -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

:check
rem 의존성이 깨졌는지 먼저 확인한다. pythonw 로 띄우면 오류가 화면에 안 보인다.
".venv\Scripts\python.exe" -c "import PySide6" >nul 2>&1
if not errorlevel 1 goto launch
echo [note_memo] 의존성이 없어 다시 설치합니다...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

:launch
start "" ".venv\Scripts\pythonw.exe" "main.py"
exit /b 0

:fail
echo.
echo [note_memo] 실행 준비에 실패했습니다. 위 메시지를 확인해 주세요.
pause
exit /b 1
