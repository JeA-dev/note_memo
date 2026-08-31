"""독립 실행 파일(노트메모.exe)을 만든다.

파이썬이 없는 컴퓨터에서도 더블클릭으로 돌아가는 단일 exe 를 뽑는다.

    .venv\\Scripts\\python.exe -m pip install pyinstaller
    .venv\\Scripts\\python.exe -m tools.build_exe

결과: dist\\노트메모.exe  (약 45MB, 첫 실행 5~6초 / 이후 3초)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "노트메모"

# 쓰지 않는 Qt 모듈을 빼서 용량을 줄인다. QtCore/QtGui/QtWidgets 만 쓴다.
EXCLUDES = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtMultimedia",
    "PySide6.QtPdf",
    "PySide6.QtDataVisualization",
    "tkinter",
    "unittest",
    "pydoc",
]


def main() -> int:
    icon = ROOT / "assets" / "note_memo.ico"
    if not icon.is_file():
        print("아이콘이 없어 먼저 만듭니다...")
        subprocess.run([sys.executable, "-m", "tools.make_icon"], cwd=ROOT, check=True)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",                       # 단일 파일 (제출·배포가 간단하다)
        "--windowed",                      # 콘솔 창 없이
        "--name", NAME,
        "--icon", str(icon),
        # 창/작업표시줄 아이콘용으로 번들에 넣는다 (config.resource_path 가 찾는다).
        "--add-data", f"{icon};assets",
    ]
    for module in EXCLUDES:
        command += ["--exclude-module", module]
    command.append(str(ROOT / "main.py"))

    print("빌드 시작 (몇 분 걸립니다)...")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    exe = ROOT / "dist" / f"{NAME}.exe"
    size = exe.stat().st_size / (1024 * 1024) if exe.is_file() else 0
    print(f"\n완료: {exe}  ({size:.0f}MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
