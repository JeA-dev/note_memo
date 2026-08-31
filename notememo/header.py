"""노트 위쪽의 날짜 섹션과 제목 섹션."""

from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout

from . import config
from .layout import ColumnRow

MAX_TITLE_LEN = 200


class NoteHeader(ColumnRow):
    """날짜(보조) 위에 제목(주인공)을 얹은 헤더.

    날짜는 메타데이터라 작게 두고, 명조 큰 글씨는 제목이 가져간다.
    """

    titleEdited = Signal()
    titleCommitted = Signal()      # Enter - 본문으로 넘어갈 차례

    def __init__(self, parent=None):
        super().__init__(parent, top=16, bottom=12)
        self.setObjectName("NoteHeader")

        # 날짜/제목은 세로로 쌓이므로 ColumnRow 의 가로줄 안에 세로 상자를 하나 둔다.
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.row.addLayout(layout)

        self.date_label = QLabel(self)
        self.date_label.setObjectName("DateLabel")
        layout.addWidget(self.date_label)

        self.title_input = QLineEdit(self)
        self.title_input.setObjectName("TitleInput")
        self.title_input.setPlaceholderText("제목 없음")
        self.title_input.setMaxLength(MAX_TITLE_LEN)
        self.title_input.textEdited.connect(self.titleEdited)
        self.title_input.returnPressed.connect(self.titleCommitted)
        layout.addWidget(self.title_input)

    def title(self) -> str:
        return self.title_input.text().strip()

    def set_note(self, date: _dt.date, title: str) -> None:
        """날짜와 제목을 채운다. 로드가 자동저장을 트리거하지 않게 시그널을 막는다."""
        self.date_label.setText(config.format_full(date))
        blocked = self.title_input.blockSignals(True)
        self.title_input.setText(title)
        self.title_input.setCursorPosition(0)
        self.title_input.blockSignals(blocked)

    def focus_title(self) -> None:
        self.title_input.setFocus()
        self.title_input.selectAll()
