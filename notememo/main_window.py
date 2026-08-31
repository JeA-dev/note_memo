"""메인 윈도우: 날짜 전환, 자동저장, 단축키."""

from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from . import config, storage, theme
from . import formatting as fmt
from .editor import NoteEditor
from .header import NoteHeader
from .layout import ColumnRow
from .sidebar import Sidebar
from .storage import Note
from .toolbar import FormatToolbar

AUTOSAVE_MS = 1500


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("노트 메모")
        self.resize(1100, 760)
        self.setMinimumSize(820, 560)

        self._loaded = False
        self.editor = NoteEditor(self)
        self.toolbar = FormatToolbar(self.editor, self)
        self.sidebar = Sidebar(self)
        self.header = NoteHeader(self)

        self.status = QLabel("", self)
        self.status.setObjectName("StatusLabel")
        self.today_button = QPushButton("오늘", self)
        self.today_button.setObjectName("TodayButton")
        self.today_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.today_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.today_button.clicked.connect(self.go_today)

        self.setCentralWidget(self._build_layout())

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(AUTOSAVE_MS)
        self._save_timer.timeout.connect(self.save)

        self.editor.textChanged.connect(self._mark_dirty)
        self.header.titleEdited.connect(self._mark_dirty)
        self.header.titleCommitted.connect(self.editor.setFocus)
        self.toolbar.saveRequested.connect(self.save)
        # 스샷은 디스크에 이미 저장됐으니 노트 쪽도 바로 맞춰 둔다.
        self.editor.imagePasted.connect(self.save)
        self.sidebar.dateSelected.connect(self.go_to)

        self._register_shortcuts()

        config.ensure_dirs()
        self.go_to(_dt.date.today())

    # --- 레이아웃 ----------------------------------------------------

    def _build_layout(self) -> QWidget:
        status_row = ColumnRow(self, top=6, bottom=12)
        status_row.row.addWidget(self.status)
        status_row.row.addStretch(1)
        status_row.row.addWidget(self.today_button)

        right = QWidget(self)
        right.setObjectName("Root")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.header)
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.editor, 1)
        right_layout.addWidget(status_row)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setChildrenCollapsible(False)

        root = QWidget(self)
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(splitter)
        return root

    def _on_body(self, action):
        """본문에 포커스가 있을 때만 실행한다.

        제목 칸이나 검색창에서 서식 단축키를 누르면 본문으로 포커스를 훔쳐 가고,
        이어서 누른 글자가 엉뚱한 곳에 들어간다 (스페이스가 안 먹히는 것처럼 보였다).
        """
        def guarded() -> None:
            if self.editor.hasFocus():
                action()
        return guarded

    def _register_shortcuts(self) -> None:
        # Ctrl+B/I/U, Ctrl+Shift+X, Ctrl+Shift+V 는 QTextEdit 기본 동작과 겹치므로
        # 에디터의 keyPressEvent에서 직접 처리한다 (거기선 포커스가 이미 본문이다).
        window_wide = [
            ("Ctrl+S", self.save),
            ("Ctrl+T", self.go_today),
            ("Ctrl+F", self.sidebar.search.setFocus),
            ("Alt+Left", lambda: self.step_day(-1)),
            ("Alt+Right", lambda: self.step_day(1)),
        ]
        body_only = [
            ("Ctrl+H", self.toolbar.apply_highlight),
            ("Ctrl+=", lambda: self.toolbar.step_size(1)),
            ("Ctrl++", lambda: self.toolbar.step_size(1)),     # Shift 를 같이 눌러도
            ("Ctrl+-", lambda: self.toolbar.step_size(-1)),
            ("Ctrl+0", lambda: self.toolbar.apply_size(theme.BODY_PT)),
            ("Ctrl+Shift+C", lambda: self._block(fmt.TODO)),
            ("Ctrl+Shift+8", lambda: self._block(fmt.BULLET)),
            ("Ctrl+Shift+L", lambda: self.toolbar.apply_align(fmt.LEFT)),
            ("Ctrl+Shift+E", lambda: self.toolbar.apply_align("center")),
            ("Ctrl+Shift+R", lambda: self.toolbar.apply_align("right")),
            ("Ctrl+Shift+J", lambda: self.toolbar.apply_align("justify")),
        ]
        for keys, slot in window_wide:
            QShortcut(QKeySequence(keys), self, activated=slot)
        for keys, slot in body_only:
            QShortcut(QKeySequence(keys), self, activated=self._on_body(slot))

    def _block(self, block_type: str) -> None:
        fmt.toggle_block_type(self.editor, block_type)
        self.toolbar.sync()
        self.editor.setFocus()

    # --- 날짜 전환 ---------------------------------------------------

    def go_to(self, date: _dt.date) -> None:
        if self._loaded and date == self.editor.date:
            return
        if self._loaded:
            self.save()                   # 전환 전에 현재 노트를 확정 저장

        note = storage.load_note(date)    # 제목과 본문을 한 번에 읽는다
        self.header.set_note(date, note.title)
        self.editor.load_blocks(date, note.blocks)
        self._loaded = True

        self.sidebar.set_date(date)
        self.sidebar.refresh(date)
        self.status.setText("저장됨" if not note.is_empty() else "저장된 내용 없음")
        self.toolbar.set_dirty(False)
        self.editor.setFocus()

    def go_today(self) -> None:
        self.go_to(_dt.date.today())

    def step_day(self, delta: int) -> None:
        self.go_to(self.editor.date + _dt.timedelta(days=delta))

    # --- 저장 --------------------------------------------------------

    def _mark_dirty(self) -> None:
        """제목과 본문 어느 쪽이 바뀌든 여기로 모인다."""
        if self.editor.autosave_suspended:
            return                        # 로드나 이미지 크기 재조정 중
        self.status.setText("작성 중…")
        self.toolbar.set_dirty(True)
        self._save_timer.start()

    def save(self) -> None:
        self._save_timer.stop()
        if not self._loaded:
            # 아직 아무 노트도 열지 않았다. 빈 문서를 저장하면 기존 노트를 지운다.
            return
        date = self.editor.date
        note = Note(self.header.title(), self.editor.blocks())
        storage.save_note(date, note)

        if note.is_empty():
            self.status.setText("저장된 내용 없음")
        else:
            self.status.setText(f"저장됨 · {_dt.datetime.now():%H:%M}")
        self.toolbar.set_dirty(False)

        # 노트 목록은 mtime 캐시를 쓰므로 매번 다시 그려도 부담이 없다.
        self.sidebar.refresh(date)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.save()
        super().closeEvent(event)
