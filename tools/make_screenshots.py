"""README 에 넣을 화면 이미지를 만든다.

오프스크린에는 폰트가 없어 글자가 네모로 깨지므로 실제 플랫폼으로 실행해야 한다.

    QT_QPA_PLATFORM=windows .venv\\Scripts\\python.exe -m tools.make_screenshots

결과: docs\\screenshot-*.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QImage, QPainter, QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import preview_shot as sample  # noqa: E402  샘플 노트 재사용
from notememo import theme  # noqa: E402
from notememo.main_window import MainWindow  # noqa: E402

OUT = ROOT / "docs"


def framed(image: QImage, radius: int = 10) -> QImage:
    """가장자리를 둥글게 다듬어 문서에 얹었을 때 깔끔하게 보이게 한다."""
    rounded = QImage(image.size(), QImage.Format.Format_ARGB32)
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(theme.PALETTE["paper"]))
    painter.drawRoundedRect(rounded.rect(), radius, radius)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.drawImage(0, 0, image)
    painter.end()
    return rounded


def main() -> int:
    app = QApplication(sys.argv)
    font = QFont()
    font.setFamilies(theme.SANS_STACK)
    font.setPointSize(theme.BODY_PT - 1)
    app.setFont(font)
    app.setStyleSheet(theme.stylesheet())

    sample.seed()
    window = MainWindow()
    window.resize(1180, 900)
    window.show()
    app.processEvents()
    window.go_to(sample.TODAY)
    app.processEvents()
    window.editor._refit_images()
    app.processEvents()

    OUT.mkdir(parents=True, exist_ok=True)
    shot = window.grab().toImage()

    saved = []
    # 전체 화면
    path = OUT / "screenshot-main.png"
    framed(shot).save(str(path), "PNG")
    saved.append(path)

    # 서식 툴바만 크게 (버튼이 작아 전체 샷에서는 잘 안 보인다)
    toolbar = window.toolbar
    top_left = toolbar.mapTo(window, toolbar.rect().topLeft())
    strip = shot.copy(top_left.x(), top_left.y(), toolbar.width(), toolbar.height())
    path = OUT / "screenshot-toolbar.png"
    strip.scaled(
        strip.width() * 2, strip.height() * 2,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ).save(str(path), "PNG")
    saved.append(path)

    # 저장 버튼의 미저장 상태
    window.toolbar.set_dirty(True)
    app.processEvents()
    dirty = window.grab().toImage()
    button = window.toolbar.save
    corner = button.mapTo(window, button.rect().topLeft())
    strip = dirty.copy(corner.x() - 8, corner.y() - 6, button.width() + 16, button.height() + 12)
    path = OUT / "screenshot-save.png"
    strip.scaled(
        strip.width() * 3, strip.height() * 3,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ).save(str(path), "PNG")
    saved.append(path)

    window.close()
    for path in saved:
        print(f"{path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.0f}KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
