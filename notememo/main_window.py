"""메인 윈도우: 날짜 전환, 자동저장, 단축키."""

from __future__ import annotations

import datetime as _dt
import os
import subprocess

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from . import config, storage, theme
from . import formatting as fmt
from .attachment import AttachmentBar
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
        self._attachments: list[dict] = []
        self.editor = NoteEditor(self)
        self.toolbar = FormatToolbar(self.editor, self)
        self.attachment_bar = AttachmentBar(self)
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
        self.editor.filesDropped.connect(self.handle_files_dropped)
        self.header.titleEdited.connect(self._mark_dirty)
        self.header.titleCommitted.connect(self.editor.setFocus)
        self.header.deleteRequested.connect(lambda: self.confirm_and_delete_note(self.editor.date))
        self.toolbar.saveRequested.connect(self.save)
        self.toolbar.attachRequested.connect(self.attach_files)
        # 스샷은 디스크에 이미 저장됐으니 노트 쪽도 바로 맞춰 둔다.
        self.editor.imagePasted.connect(self.save)
        self.sidebar.dateSelected.connect(self.go_to)
        self.sidebar.deleteRequested.connect(self.confirm_and_delete_note)

        self.attachment_bar.deleteRequested.connect(self.delete_attachment)
        self.attachment_bar.openRequested.connect(self.open_attachment)
        self.attachment_bar.showInFolderRequested.connect(self.show_attachment_in_folder)
        self.attachment_bar.insertRequested.connect(self.insert_attachment_to_editor)

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
        right_layout.addWidget(self.attachment_bar)
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
            ("Ctrl+Shift+Delete", lambda: self.confirm_and_delete_note(self.editor.date)),
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
        has_content = not note.is_empty() or config.note_path(date).is_file()
        self.header.set_note(date, note.title, has_content=has_content)
        self.editor.load_blocks(date, note.blocks)
        self._attachments = list(note.attachments)
        self.attachment_bar.set_attachments(date, self._attachments)
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
        self.header.set_delete_enabled(True)
        self._save_timer.start()

    def save(self) -> None:
        self._save_timer.stop()
        if not self._loaded:
            # 아직 아무 노트도 열지 않았다. 빈 문서를 저장하면 기존 노트를 지운다.
            return
        date = self.editor.date
        note = Note(self.header.title(), self.editor.blocks(), self._attachments)
        storage.save_note(date, note)

        if note.is_empty():
            self.status.setText("저장된 내용 없음")
            self.header.set_delete_enabled(False)
        else:
            self.status.setText(f"저장됨 · {_dt.datetime.now():%H:%M}")
            self.header.set_delete_enabled(True)
        self.toolbar.set_dirty(False)

        # 노트 목록은 mtime 캐시를 쓰므로 매번 다시 그려도 부담이 없다.
        self.sidebar.refresh(date)

    # --- 첨부파일 ----------------------------------------------------

    def attach_files(self) -> None:
        if not self._loaded:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "파일 첨부 (PDF, 이미지, 동영상 등)",
            "",
            "모든 지원 파일 (*.pdf *.png *.jpg *.jpeg *.gif *.bmp *.webp *.mp4 *.mkv *.avi *.mov *.wmv *.webm);;"
            "PDF 문서 (*.pdf);;"
            "이미지 파일 (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;"
            "동영상 파일 (*.mp4 *.mkv *.avi *.mov *.wmv *.webm);;"
            "모든 파일 (*.*)",
        )
        if files:
            self.add_attachment_files(files)

    def handle_files_dropped(self, file_paths: list[str]) -> None:
        if not self._loaded:
            return
        self.add_attachment_files(file_paths)

    def add_attachment_files(self, file_paths: list[str]) -> None:
        date = self.editor.date
        added = False
        for path_str in file_paths:
            att = storage.save_attachment(date, path_str)
            if att:
                self._attachments.append(att)
                added = True
                # 이미지 파일이면 본문에도 자동 삽입
                if att.get("type") == "image":
                    image = QImage(path_str)
                    if not image.isNull():
                        self.editor.insert_image(image)

        if added:
            self.attachment_bar.set_attachments(date, self._attachments)
            self._mark_dirty()
            self.save()

    def open_attachment(self, stored_name: str) -> None:
        path = storage.attachment_path(self.editor.date, stored_name)
        if path.is_file():
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                os.startfile(str(path))

    def show_attachment_in_folder(self, stored_name: str) -> None:
        path = storage.attachment_path(self.editor.date, stored_name)
        if path.is_file():
            subprocess.run(["explorer.exe", f"/select,{path}"], check=False)

    def insert_attachment_to_editor(self, stored_name: str) -> None:
        path = storage.attachment_path(self.editor.date, stored_name)
        if path.is_file():
            image = QImage(str(path))
            if not image.isNull():
                self.editor.insert_image(image)

    def delete_attachment(self, stored_name: str) -> None:
        target = next((a for a in self._attachments if a.get("name") == stored_name), None)
        if not target:
            return
        orig_name = target.get("original_name") or target.get("name", "파일")
        reply = QMessageBox.question(
            self,
            "첨부파일 삭제",
            f"'{orig_name}' 첨부파일을 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            storage.delete_attachment_file(self.editor.date, stored_name)
            self._attachments = [a for a in self._attachments if a.get("name") != stored_name]
            self.attachment_bar.set_attachments(self.editor.date, self._attachments)
            self._mark_dirty()
            self.save()

    # --- 노트 삭제 ----------------------------------------------------

    def delete_note(self, date: _dt.date | None = None) -> bool:
        """확인 대화상자 없이 바로 삭제 (테스트 및 내부 호출용)."""
        return self._do_delete_note(date or self.editor.date)

    def confirm_and_delete_note(self, date: _dt.date | None = None, prompt: bool = True) -> bool:
        target_date = date or self.editor.date
        note_on_disk = storage.load_note(target_date)
        is_current = (target_date == self.editor.date)

        if is_current:
            title = self.header.title() or note_on_disk.title
            has_content = bool(
                title
                or self.editor.blocks()
                or self._attachments
                or config.note_path(target_date).is_file()
            )
        else:
            title = note_on_disk.title
            has_content = bool(not note_on_disk.is_empty() or config.note_path(target_date).is_file())

        if not has_content:
            return False

        if prompt:
            date_str = config.format_full(target_date)
            title_str = f"'{title}'" if title else "제목 없음"
            reply = QMessageBox.question(
                self,
                "노트 삭제",
                f"{date_str}\n{title_str}\n\n이 노트를 삭제하시겠습니까?\n작성된 내용과 첨부파일이 모두 삭제되며, 복구할 수 없습니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        return self._do_delete_note(target_date)

    def _do_delete_note(self, target_date: _dt.date) -> bool:
        is_current = (target_date == self.editor.date)
        if is_current:
            self._save_timer.stop()
            self._suspend_autosave = True
            try:
                self.header.set_note(target_date, "", has_content=False)
                self.editor.load_blocks(target_date, [])
                self._attachments = []
                self.attachment_bar.set_attachments(target_date, [])
            finally:
                self._suspend_autosave = False
            self.toolbar.set_dirty(False)

        storage.delete_note(target_date)

        if is_current:
            if target_date != _dt.date.today():
                self.go_to(_dt.date.today())
                self.status.setText(f"{config.format_short(target_date)} 노트가 삭제되었습니다")
            else:
                self.sidebar.refresh(target_date)
                self.status.setText("노트가 삭제되었습니다")
        else:
            self.sidebar.refresh(self.editor.date)
            self.status.setText(f"{config.format_short(target_date)} 노트가 삭제되었습니다")
        return True

    def closeEvent(self, event) -> None:  # noqa: N802
        self.save()
        super().closeEvent(event)
