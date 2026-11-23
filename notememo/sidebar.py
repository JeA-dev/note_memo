"""사이드바: 검색, 캘린더, 최근 노트 목록."""

from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QDate, QPointF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPalette,
    QTextCharFormat,
    QTextLayout,
    QTextOption,
)
from PySide6.QtWidgets import (
    QCalendarWidget,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from . import config, storage, tags, theme


def _to_qdate(date: _dt.date) -> QDate:
    return QDate(date.year, date.month, date.day)


def _to_date(qdate: QDate) -> _dt.date:
    return _dt.date(qdate.year(), qdate.month(), qdate.day())


DATE_ROLE = Qt.ItemDataRole.UserRole + 1     # 항목에 함께 그릴 날짜 문자열


class _NoteItemDelegate(QStyledItemDelegate):
    """날짜 한 줄 + 제목(접어서 여러 줄)로 목록 항목을 그린다.

    기본 델리게이트는 항목 높이를 실제로 그릴 때의 뷰포트 폭과 무관하게 정해 버린다.
    그래서 폭이 모자라면 다음 줄로 넘기지 못하고 '...' 로 잘라 냈다. 목록을 다시
    그리는 도중 스크롤바가 생기면 그 전에 들어간 항목만 넓은 폭으로 계산되기
    때문에, 같은 목록 안에서 어떤 노트는 제목이 두 줄로 다 보이고 어떤 노트는
    한 줄로 잘렸다. 접는 폭을 직접 계산해 모든 항목이 같은 규칙을 따르게 한다.
    """

    PAD_X = 9        # 기존 QSS 의 item padding 과 같은 값
    PAD_Y = 7
    GAP = 2          # 날짜 줄과 제목 사이
    # 제목 줄 수 상한. storage 가 제목을 42자+줄임표로 이미 막아 두는데, 그 길이는
    # 가장 넓게 잡아도(한글로 꽉 채워도) 세 줄이면 들어간다. 즉 이 상한 때문에
    # 제목이 잘리는 일은 없고, 혹시 모를 경우를 위한 안전장치로만 둔다.
    TITLE_LINES = 3

    def initStyleOption(self, option, index) -> None:  # noqa: N802
        # 글자는 아래에서 직접 그린다. 기본 델리게이트에는 배경과 선택 표시만 맡긴다.
        super().initStyleOption(option, index)
        option.text = ""

    def _wrap_width(self, option) -> int:
        """글자를 접을 폭. 크기 계산과 그리기가 반드시 같은 값을 써야 한다."""
        view = option.widget
        # 항목 가로폭은 뷰포트 폭 그대로다 (QSS 의 item margin 은 빠지지 않는다).
        width = view.viewport().width() if view is not None else option.rect.width()
        if width <= 0:
            width = option.rect.width()
        return max(40, width - 2 * self.PAD_X)

    @staticmethod
    def _tag_formats(text: str) -> list:
        """제목 안 `[태그]` 구간마다 색과 굵기를 지정한다.

        QTextLayout 에 서식을 쥐어 주면 접는 폭 계산과 그리기가 같은 글꼴을 쓰므로,
        굵게 해도 줄바꿈 위치가 어긋나지 않는다.
        """
        formats = []
        for start, end, name in tags.tag_spans(text):
            char_format = QTextCharFormat()
            char_format.setForeground(QColor(tags.color_of(name)))
            char_format.setFontWeight(QFont.Weight.Bold)
            span = QTextLayout.FormatRange()
            span.start = start
            span.length = end - start
            span.format = char_format
            formats.append(span)
        return formats

    def _build_layout(self, text: str, option, width: int):
        """최대 TITLE_LINES 줄까지 접은 레이아웃. (레이아웃, 줄 수, 소비한 글자 수)."""
        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        layout = QTextLayout(text, option.font)
        layout.setTextOption(text_option)
        layout.setFormats(self._tag_formats(text))
        layout.beginLayout()
        lines = 0
        consumed = 0
        offset = 0.0
        while lines < self.TITLE_LINES:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            # 줄 위치를 정해 주지 않으면 Qt 가 다음 줄을 만들지 않고 멈춘다.
            line.setPosition(QPointF(0.0, offset))
            offset += line.height()
            consumed = line.textStart() + line.textLength()
            lines += 1
        layout.endLayout()
        return layout, max(lines, 1), consumed

    def _title_layout(self, title: str, option, width: int):
        """제목 레이아웃. 줄 수 상한을 넘치면 '…' 로 줄여 다시 접는다."""
        text = title or ""
        layout, lines, consumed = self._build_layout(text, option, width)
        if text and consumed < len(text):
            metrics = QFontMetrics(option.font)
            head = text[:consumed]
            tail = metrics.elidedText(text[consumed:], Qt.TextElideMode.ElideRight, width)
            layout, lines, _ = self._build_layout(head + tail, option, width)
        return layout, lines

    def _title_lines(self, title: str, option, width: int) -> list[str]:
        """제목이 실제로 어떤 줄들로 그려지는지. 테스트와 높이 계산에 쓴다."""
        layout, _ = self._title_layout(title, option, width)
        text = layout.text()
        out = []
        for i in range(layout.lineCount()):
            line = layout.lineAt(i)
            out.append(text[line.textStart():line.textStart() + line.textLength()])
        return out or [""]

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        opt = self._prepared(option, index)
        metrics = QFontMetrics(opt.font)
        title = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        _, lines = self._title_layout(title, opt, self._wrap_width(opt))
        height = self.PAD_Y * 2 + metrics.height() * (1 + lines) + self.GAP
        return QSize(self._wrap_width(opt) + 2 * self.PAD_X, height)

    def _prepared(self, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        return opt

    def paint(self, painter, option, index) -> None:
        opt = self._prepared(option, index)
        super().paint(painter, opt, index)           # 배경·선택·호버

        metrics = QFontMetrics(opt.font)
        date_text = str(index.data(DATE_ROLE) or "")
        title = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        width = self._wrap_width(opt)
        x = opt.rect.left() + self.PAD_X
        y = opt.rect.top() + self.PAD_Y

        painter.save()
        painter.setFont(opt.font)
        painter.setPen(QColor(theme.PALETTE["ink_soft"]))
        painter.drawText(x, y + metrics.ascent(), metrics.elidedText(
            date_text, Qt.TextElideMode.ElideRight, width))
        y += metrics.height() + self.GAP

        painter.setPen(QColor(theme.PALETTE["ink"]))
        layout, _ = self._title_layout(title, opt, width)
        layout.draw(painter, QPointF(x, y))          # 태그 색은 레이아웃이 입힌다
        painter.restore()


class _NoteListWidget(QListWidget):
    """Delete 키로 선택된 노트를 삭제할 수 있는 리스트 위젯."""

    deletePressed = Signal(object)

    def resizeEvent(self, event) -> None:  # noqa: N802
        # 스크롤바가 생기거나 사라지면 접히는 폭이 달라진다. 높이를 다시 재게 한다.
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self.scheduleDelayedItemsLayout()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            item = self.currentItem()
            if item:
                date = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(date, _dt.date):
                    self.deletePressed.emit(date)
                    return
        super().keyPressEvent(event)


class Sidebar(QWidget):
    dateSelected = Signal(object)   # datetime.date
    deleteRequested = Signal(object)  # datetime.date

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

        self.note_list = _NoteListWidget(self)
        self.note_list.setObjectName("NoteList")
        self.note_list.setUniformItemSizes(False)
        self.note_list.setWordWrap(True)
        self.note_list.setItemDelegate(_NoteItemDelegate(self.note_list))
        self.note_list.itemClicked.connect(self._on_item_clicked)
        self.note_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.note_list.customContextMenuRequested.connect(self._show_context_menu)
        self.note_list.deletePressed.connect(self.deleteRequested.emit)
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
        self._assign_tag_colors()
        self._mark_calendar()
        self._rebuild_list()

    def _assign_tag_colors(self) -> None:
        """새로 생긴 태그에 색을 나눠 준다.

        오래된 노트부터 넘겨야 이미 쓰던 태그의 색이 그대로 남는다
        (_dates 는 최신순이라 뒤집는다).
        """
        tags.prime(storage.title_of(d) or "" for d in reversed(self._dates))

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
            item = QListWidgetItem(title)
            item.setData(DATE_ROLE, config.format_short(date))
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

    def _show_context_menu(self, pos) -> None:
        item = self.note_list.itemAt(pos)
        if not item:
            return
        date = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(date, _dt.date):
            return

        self.note_list.setCurrentItem(item)
        menu = QMenu(self)
        open_action = menu.addAction("노트 열기")
        delete_action = menu.addAction("노트 삭제")

        action = menu.exec(self.note_list.viewport().mapToGlobal(pos))
        if action == open_action:
            self.dateSelected.emit(date)
        elif action == delete_action:
            self.deleteRequested.emit(date)
