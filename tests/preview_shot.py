"""디자인 확인용: 샘플 노트를 채운 창을 PNG로 렌더링한다.

    .venv\\Scripts\\python.exe -m tests.preview_shot [출력경로]
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QPainter, QLinearGradient, QColor, QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from notememo import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="notememo-shot-"))
config.DATA_DIR = _TMP
config.NOTES_DIR = _TMP / "notes"
config.IMAGES_DIR = _TMP / "images"

from notememo import storage, theme  # noqa: E402
from notememo.main_window import MainWindow  # noqa: E402

TODAY = _dt.date.today()
Y = theme.HIGHLIGHT_COLORS[0]
M = theme.HIGHLIGHT_COLORS[1]


def fake_screenshot(width=1180, height=430) -> QImage:
    """스샷처럼 보이는 더미 이미지."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor("#26313F"))
    gradient.setColorAt(1.0, QColor("#3E5166"))
    painter.fillRect(0, 0, width, height, gradient)
    painter.setPen(QColor("#7FE3C0"))
    painter.setFont(QFont("Consolas", 34))
    painter.drawText(60, 130, "$ deploy --prod")
    painter.setPen(QColor("#E8EEF5"))
    painter.setFont(QFont("Consolas", 26))
    painter.drawText(60, 210, "cache invalidation: SKIPPED")
    painter.drawText(60, 270, "504 Gateway Timeout  x 41")
    painter.setPen(QColor("#F0A5A5"))
    painter.drawText(60, 350, "-> rollback required")
    painter.end()
    return image


TITLE = "배포 장애 기록"

SAMPLE = [
    {"type": "text", "runs": [
        {"text": "16시 20분경 프로덕션 응답이 "},
        {"text": "504로 전면 실패", "b": True, "hl": Y},
        {"text": ". 캐시 무효화 단계가 통째로 빠져 있었다."},
    ]},
    {"type": "text", "runs": []},
    {"type": "text", "align": "center", "runs": [{"text": "당시 콘솔", "sz": 16}]},
    {"type": "text", "align": "center", "runs": [{"image": "shot.png"}]},
    {"type": "text", "runs": [
        {"text": "재현 조건은 "},
        {"text": "빌드 캐시가 살아있을 때", "i": True, "hl": M},
        {"text": "만."},
    ]},
    {"type": "text", "runs": []},
    {"type": "text", "runs": [{"text": "할 일", "sz": 16}]},
    {"type": "todo", "checked": True, "runs": [{"text": "핫픽스 롤백 배포"}]},
    {"type": "todo", "checked": False, "runs": [{"text": "무효화 단계 파이프라인에 되돌리기"}]},
    {"type": "todo", "checked": False, "runs": [{"text": "알림 임계값 조정"}]},
    {"type": "text", "runs": []},
    {"type": "bullet", "runs": [{"text": "회고는 금요일 오전"}]},
    {"type": "text", "indent": 1, "runs": [{"text": "— 들여쓴 보충 설명"}]},
    {"type": "bullet", "runs": [{"text": "런북에 "}, {"text": "체크리스트", "u": True}, {"text": " 추가"}]},
]


def seed() -> None:
    config.ensure_dirs()
    for offset, blocks in ((0, SAMPLE), (1, None), (3, None), (4, None)):
        date = TODAY - _dt.timedelta(days=offset)
        if blocks is None:
            storage.save_note(date, storage.Note(
                f"{config.format_short(date)} 메모",
                [{"type": "text", "runs": [{"text": "짧은 기록"}]}],
            ))
            continue
        directory = config.image_dir(date)
        directory.mkdir(parents=True, exist_ok=True)
        fake_screenshot().save(str(directory / "shot.png"), "PNG")
        storage.save_note(date, storage.Note(TITLE, blocks))


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("preview.png")
    app = QApplication(sys.argv)
    font = QFont()
    font.setFamilies(theme.SANS_STACK)
    font.setPointSize(theme.BODY_PT - 1)
    app.setFont(font)
    app.setStyleSheet(theme.stylesheet())

    seed()
    window = MainWindow()
    window.resize(1180, 820)
    window.show()
    app.processEvents()
    window.go_to(TODAY)
    app.processEvents()
    window.editor._refit_images()
    window.toolbar.set_dirty(True)      # 저장 버튼 활성 상태도 함께 확인
    app.processEvents()

    window.grab().save(str(out), "PNG")
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
