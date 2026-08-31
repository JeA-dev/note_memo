"""바로가기용 아이콘(.ico)을 앱 팔레트로 그려서 assets/ 에 저장한다."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPolygonF  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from notememo import theme  # noqa: E402

P = theme.PALETTE


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256.0

    # 종이
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(P["paper"]))
    painter.drawRoundedRect(QRectF(30 * s, 18 * s, 196 * s, 220 * s), 18 * s, 18 * s)

    # 왼쪽 가죽 제본
    painter.setBrush(QColor(P["accent"]))
    painter.drawRoundedRect(QRectF(30 * s, 18 * s, 40 * s, 220 * s), 18 * s, 18 * s)
    painter.drawRect(QRectF(52 * s, 18 * s, 18 * s, 220 * s))

    # 본문 줄
    painter.setBrush(QColor(P["border"]))
    for i, width in enumerate((120, 132, 96)):
        painter.drawRoundedRect(
            QRectF(92 * s, (66 + i * 34) * s, width * s, 10 * s), 5 * s, 5 * s
        )

    # 형광펜 한 줄
    painter.setBrush(QColor(theme.HIGHLIGHT_COLORS[0]))
    painter.drawRoundedRect(QRectF(92 * s, 168 * s, 108 * s, 22 * s), 6 * s, 6 * s)

    # 책갈피 리본. 글자를 쓰면 오프스크린 렌더링에서 폰트가 없어 깨지므로 도형만 쓴다.
    painter.setBrush(QColor(P["accent"]))
    ribbon = QPolygonF([
        QPointF(176 * s, 18 * s),
        QPointF(212 * s, 18 * s),
        QPointF(212 * s, 96 * s),
        QPointF(194 * s, 78 * s),
        QPointF(176 * s, 96 * s),
    ])
    painter.drawPolygon(ribbon)
    painter.end()
    return image


def main() -> int:
    QGuiApplication(sys.argv)
    out = Path(__file__).resolve().parent.parent / "assets" / "note_memo.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    # 윈도우가 크기별로 골라 쓰도록 가장 큰 크기로 저장한다.
    if not draw(256).save(str(out), "ICO"):
        print("ICO 저장 실패")
        return 1
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
