"""독립 실행 파일(노트메모.exe)을 만든다.

파이썬이 없는 컴퓨터에서도 더블클릭으로 돌아가는 단일 exe 를 뽑는다.

    .venv\\Scripts\\python.exe -m pip install pyinstaller
    .venv\\Scripts\\python.exe -m tools.build_exe

결과: dist\\노트메모.exe  (약 45MB, 첫 실행 5~6초 / 이후 3초)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from notememo import __version__ as VERSION  # noqa: E402

NAME = "노트메모"

# 윈도우 파일 속성(오른쪽 클릭 → 속성 → 자세히)에 박히는 정보.
# 0x0412 = 한국어, 0x04B0(1200) = 유니코드.
_VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={tup}, prodvers={tup},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('041204B0', [
      StringStruct('FileDescription', '노트 메모 - 날짜별 다이어리 노트 앱'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', '노트 메모'),
      StringStruct('ProductVersion', '{version}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [0x0412, 1200])])
  ]
)
"""


def write_version_file(build_dir: Path) -> Path:
    """PyInstaller 가 읽을 버전 정보 파일을 만든다. 버전은 notememo.__version__ 하나뿐이다."""
    parts = [int(p) for p in VERSION.split(".")]
    while len(parts) < 4:
        parts.append(0)
    build_dir.mkdir(parents=True, exist_ok=True)
    path = build_dir / "version_info.txt"
    path.write_text(
        _VERSION_INFO.format(tup=tuple(parts[:4]), version=VERSION, name=NAME),
        encoding="utf-8",
    )
    return path

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
        "--version-file", str(write_version_file(ROOT / "build")),
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
    if not exe.is_file():
        print("빌드는 끝났는데 exe 가 없습니다.")
        return 1
    size = exe.stat().st_size / (1024 * 1024)
    print(f"\n완료: {exe}  ({size:.0f}MB)")

    # 릴리스에 올릴 파일은 버전을 파일명에 달아 둔다. 받는 쪽에서 무엇을 받았는지
    # 바로 알 수 있고, 여러 버전을 올려도 섞이지 않는다.
    release = ROOT / "dist" / f"{NAME}-v{VERSION}.exe"
    shutil.copy2(exe, release)
    print(f"릴리스용: {release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
