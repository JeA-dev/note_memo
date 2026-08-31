"""본문 단 폭에 맞춰 끝나는 가로줄."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from . import theme


class ColumnRow(QWidget):
    """왼쪽은 본문과 같은 선에서 시작하고, 오른쪽은 본문 단 폭에서 끝나는 가로줄.

    전체 화면에서 오른쪽 끝 버튼이 화면 가장자리까지 밀려나면
    본문과 동떨어져 보이므로, 남는 폭은 오른쪽 여백으로 흡수한다.
    """

    def __init__(self, parent=None, *, pad: int = 0, top: int = 0, bottom: int = 0):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._pad = theme.DOC_MARGIN - pad
        self._top = top
        self._bottom = bottom

        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(self._pad, top, self._pad, bottom)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        right = max(self._pad, self.width() - theme.CONTENT_WIDTH - self._pad)
        if self.row.contentsMargins().right() != right:
            self.row.setContentsMargins(self._pad, self._top, right, self._bottom)
