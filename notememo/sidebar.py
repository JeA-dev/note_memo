"""사이드바: 검색, 캘린더, 최근 노트 목록."""

from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import config, storage, theme


def _to_qdate(date: _dt.date) -> QDate:
    return QDate(date.year, date.month, date.day)


def _to_date(qdate: QDate) -> _dt.date:
    return _dt.date(qdate.year(), qdate.month(), qdate.day())


class Sidebar(QWidget):
    dateSelected = Signal(object)   # datetime.date

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(262)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 10, 12)
        layout.setSpacing(10)

        self.search = QLineEdit(self)
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("노트 검색  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._rebuild_list)
        layout.addWidget(self.search)

        self.calendar = QCalendarWidget(self)
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(
            QCalendarWidget.HorizontalHeaderFormat.SingleLetterDayNames
        )
        self.calendar.setNavigationBarVisible(True)
        self.calendar.setFixedHeight(226)
        self.calendar.clicked.connect(lambda qdate: self.dateSelected.emit(_to_date(qdate)))
        self._style_calendar_selection()
        layout.addWidget(self.calendar)

        self.list_label = QLabel("최근 노트", self)
        self.list_label.setObjectName("SectionLabel")
        layout.addWidget(self.list_label)

        self.note_list = QListWidget(self)
        self.note_list.setObjectName("NoteList")
        self.note_list.setUniformItemSizes(False)
        self.note_list.setWordWrap(True)
        self.note_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.note_list, 1)

        self._dates: list[_dt.date] = []
        self._current: _dt.date | None = None

    def _style_calendar_selection(self) -> None:
        """선택한 날짜 배경. QSS의 selection-background-color 는 포커스가 없는
        캘린더 뷰에 적용되지 않아 팔레트로 직접 지정한다."""
        palette = self.calendar.palette()
        for group in (
            QPalette.ColorGroup.Active,
            QPalette.ColorGroup.Inactive,
            QPalette.ColorGroup.Disabled,
        ):
            palette.setColor(group, QPalette.ColorRole.Highlight, QColor(theme.PALETTE["accent_soft"]))
            palette.setColor(group, QPalette.ColorRole.HighlightedText, QColor(theme.PALETTE["ink"]))
        self.calendar.setPalette(palette)

    # --- 갱신 --------------------------------------------------------

    def refresh(self, current: _dt.date | None = None) -> None:
        """노트 목록과 캘린더 표시를 디스크 상태에 맞춰 다시 그린다."""
        if current is not None:
            self._current = current
        self._dates = storage.list_note_dates()
        self._mark_calendar()
        self._rebuild_list()

    def set_date(self, date: _dt.date) -> None:
        """시그널을 되쏘지 않고 캘린더 선택만 옮긴다."""
        self._current = date
        blocked = self.calendar.blockSignals(True)
        self.calendar.setSelectedDate(_to_qdate(date))
        self.calendar.blockSignals(blocked)
        self._select_in_list(date)

    def _mark_calendar(self) -> None:
        self.calendar.setDateTextFormat(QDate(), QTextCharFormat())   # 기존 표시 초기화
        marked = QTextCharFormat()
        marked.setFontWeight(QFont.Weight.Bold)
        marked.setForeground(QColor(theme.PALETTE["accent"]))
        for date in self._dates:
            self.calendar.setDateTextFormat(_to_qdate(date), marked)

    def _rebuild_list(self) -> None:
        query = self.search.text().strip()
        dates = storage.search(query) if query else self._dates
        self.list_label.setText(f"검색 결과 {len(dates)}건" if query else "최근 노트")

        self.note_list.clear()
        for date in dates:
            title = storage.title_of(date) or "제목 없음"
            item = QListWidgetItem(f"{config.format_short(date)}\n{title}")
            item.setData(Qt.ItemDataRole.UserRole, date)
            self.note_list.addItem(item)
        if self._current is not None:
            self._select_in_list(self._current)

    def _select_in_list(self, date: _dt.date) -> None:
        for row in range(self.note_list.count()):
            item = self.note_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == date:
                self.note_list.setCurrentItem(item)
                return
        self.note_list.clearSelection()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        date = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(date, _dt.date):
            self.dateSelected.emit(date)
