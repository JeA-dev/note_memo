"""노트 위쪽의 날짜 섹션과 제목 섹션."""

from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QLineEdit, QToolButton, QVBoxLayout

from . import config, tags, theme
from .layout import ColumnRow

MAX_TITLE_LEN = 200


def _trash_icon(color: str) -> QPixmap:
    """휴지통 모양 아이콘 (16x16)."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # 손잡이
    painter.drawPolyline([QPointF(6.0, 3.2), QPointF(6.0, 1.8), QPointF(10.0, 1.8), QPointF(10.0, 3.2)])
    # 뚜껑선
    painter.drawLine(QPointF(2.5, 3.4), QPointF(13.5, 3.4))
    # 몸통
    path = QPainterPath()
    path.moveTo(4.2, 4.6)
    path.lineTo(4.8, 12.8)
    path.arcTo(QRectF(4.8, 11.8, 2.0, 2.0), 180, 90)
    path.lineTo(9.2, 13.8)
    path.arcTo(QRectF(9.2, 11.8, 2.0, 2.0), 270, 90)
    path.lineTo(11.8, 4.6)
    painter.drawPath(path)
    # 안쪽 세로선 2개
    painter.drawLine(QPointF(6.6, 6.2), QPointF(6.8, 11.2))
    painter.drawLine(QPointF(9.4, 6.2), QPointF(9.2, 11.2))
    painter.end()
    return pixmap


class _DeleteNoteButton(QToolButton):
    """호버 시 붉은색 경고 아이콘으로 전환되는 노트 삭제 버튼."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DeleteNoteButton")
        self.setText("노트 삭제")
        self.setToolTip("현재 노트 삭제  (Ctrl+Shift+Delete)")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(15, 15))
        self._icon_normal = _trash_icon(theme.PALETTE["ink_soft"])
        self._icon_hover = _trash_icon("#DC2626")
        self.setIcon(self._icon_normal)

    def enterEvent(self, event) -> None:
        if self.isEnabled():
            self.setIcon(self._icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setIcon(self._icon_normal)
        super().leaveEvent(event)


class NoteHeader(ColumnRow):
    """날짜(보조) 위에 제목(주인공)을 얹은 헤더.

    날짜는 메타데이터라 작게 두고, 명조 큰 글씨는 제목이 가져간다.
    """

    titleEdited = Signal()
    titleCommitted = Signal()      # Enter - 본문으로 넘어갈 차례
    deleteRequested = Signal()     # 노트 삭제 버튼 클릭

    def __init__(self, parent=None):
        super().__init__(parent, top=16, bottom=12)
        self.setObjectName("NoteHeader")

        # 날짜/제목은 세로로 쌓이므로 ColumnRow 의 가로줄 안에 세로 상자를 하나 둔다.
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.row.addLayout(layout, 1)

        self.date_label = QLabel(self)
        self.date_label.setObjectName("DateLabel")
        layout.addWidget(self.date_label)

        self.title_input = QLineEdit(self)
        self.title_input.setObjectName("TitleInput")
        self.title_input.setPlaceholderText("제목 없음")
        self.title_input.setMaxLength(MAX_TITLE_LEN)
        self.title_input.textEdited.connect(self.titleEdited)
        self.title_input.textChanged.connect(self._apply_tag_color)
        self.title_input.returnPressed.connect(self.titleCommitted)
        layout.addWidget(self.title_input)
        self._tag_color: str | None = None

        self.delete_button = _DeleteNoteButton(self)
        self.delete_button.clicked.connect(self.deleteRequested.emit)
        self.row.addWidget(
            self.delete_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def _apply_tag_color(self) -> None:
        """제목 앞 `[태그]` 색을 제목 줄 전체에 입힌다.

        QLineEdit 은 일부 글자만 색을 바꿀 수 없다. 유일한 방법인 QInputMethodEvent
        트릭은 한글 조합 중인 글자를 건드려서 쓰면 안 된다. 그래서 헤더에서는 제목
        전체를 태그 색으로 칠하고, 태그만 따로 칠하는 것은 목록에서만 한다.
        """
        color = tags.title_color(self.title_input.text())
        if color == self._tag_color:
            return
        self._tag_color = color
        self.title_input.setStyleSheet(f"color: {color};" if color else "")

    def title(self) -> str:
        return self.title_input.text().strip()

    def set_note(self, date: _dt.date, title: str, has_content: bool = True) -> None:
        """날짜와 제목을 채운다. 로드가 자동저장을 트리거하지 않게 시그널을 막는다."""
        self.date_label.setText(config.format_full(date))
        blocked = self.title_input.blockSignals(True)
        self.title_input.setText(title)
        self.title_input.setCursorPosition(0)
        self.title_input.blockSignals(blocked)
        self._apply_tag_color()      # 로드 때는 textChanged 가 막혀 있어 직접 부른다
        self.set_delete_enabled(has_content)

    def set_delete_enabled(self, enabled: bool) -> None:
        self.delete_button.setEnabled(enabled)
        self.delete_button.setToolTip(
            "현재 노트 삭제  (Ctrl+Shift+Delete)" if enabled else "삭제할 노트가 없습니다"
        )

    def focus_title(self) -> None:
        self.title_input.setFocus()
        self.title_input.selectAll()
