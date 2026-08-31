"""note_memo 엔트리포인트."""

from __future__ import annotations

import datetime as _dt
import sys
import traceback

from PySide6.QtCore import QSharedMemory
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

# 공유 메모리 한 조각을 선점해 중복 실행을 막는다. 두 인스턴스가 같은 노트를
# 자동저장하면 서로를 덮어쓴다. 윈도우는 프로세스가 죽으면 자동으로 놓아주므로
# 강제 종료해도 잠금이 남지 않는다.
_SINGLE_INSTANCE_KEY = "note_memo_single_instance_v1"

from notememo import config, theme
from notememo.main_window import MainWindow


def _install_crash_log() -> None:
    """pythonw.exe 로 띄우면 콘솔이 없어 오류가 그냥 사라진다.

    잡히지 않은 예외를 로그 파일에 남기고 사용자에게도 알린다.
    """
    log_path = config.DATA_DIR / "error.log"

    def hook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            config.ensure_dirs()
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(f"\n=== {_dt.datetime.now():%Y-%m-%d %H:%M:%S} ===\n{text}")
        except OSError:
            pass
        if sys.__stderr__ is not None:      # pythonw 로 띄우면 stderr 자체가 없다
            print(text, file=sys.__stderr__)
        if QApplication.instance() is not None:
            QMessageBox.critical(
                None,
                "노트 메모 오류",
                f"오류가 발생해 작업을 마치지 못했습니다.\n\n{exc}\n\n자세한 내용: {log_path}",
            )

    sys.excepthook = hook


def _claim_single_instance() -> QSharedMemory | None:
    """이미 떠 있으면 None. 아니면 앱이 사는 동안 붙잡고 있어야 하는 핸들."""
    guard = QSharedMemory(_SINGLE_INSTANCE_KEY)
    if guard.attach():          # 다른 인스턴스가 이미 선점했다
        guard.detach()
        return None
    return guard if guard.create(1) else None


def main() -> int:
    app = QApplication(sys.argv)
    _install_crash_log()

    guard = _claim_single_instance()
    if guard is None:
        # 실행 파일은 뜨는 데 몇 초 걸려서 조급하게 두 번 누르기 쉽다.
        # 먼저 뜬 창을 쓰게 두고 조용히 빠진다.
        return 0
    app.setApplicationName(config.APP_NAME)
    app.setApplicationDisplayName("노트 메모")

    icon_path = config.resource_path("assets/note_memo.ico")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    font = QFont()
    font.setFamilies(theme.SANS_STACK)
    font.setPointSize(theme.BODY_PT - 1)
    app.setFont(font)
    app.setStyleSheet(theme.stylesheet())

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
