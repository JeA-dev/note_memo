"""필기 영역. 캡쳐 붙여넣기, 이미지 폭 맞춤, 체크박스 클릭을 담당한다."""

from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QPointF, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QImage,
    QPainter,
    QPen,
    QTextCursor,
)
from PySide6.QtWidgets import QTextEdit

from . import formatting as fmt
from . import serializer, storage, theme

RICH_MIME = "application/x-qrichtext"
MARKER_HIT_WIDTH = 26       # 체크박스 클릭으로 인정할 왼쪽 여백 폭

# QTextEdit 기본 Ctrl+B/I/U 대신 우리 토글을 써서 서식 화이트리스트를 유지한다.
_CHAR_TOGGLES = {
    Qt.Key.Key_B: fmt.toggle_bold,
    Qt.Key.Key_I: fmt.toggle_italic,
    Qt.Key.Key_U: fmt.toggle_underline,
}


class NoteEditor(QTextEdit):
    """날짜 하나에 대응하는 필기 영역."""

    imagePasted = Signal()
    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Editor")
        self.setAcceptRichText(True)
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Tab 은 포커스 이동이 아니라 들여쓰기로 쓴다 (keyPressEvent 에서 처리).
        self.setTabChangesFocus(False)
        self.setPlaceholderText("오늘 무슨 일이 있었나요?  ( Win+Shift+S 로 캡쳐한 뒤 Ctrl+V )")

        self._date: _dt.date = _dt.date.today()
        self._force_plain = False
        self._suspend_autosave = False
        self._right_margin = -1

        self.document().setDocumentMargin(theme.DOC_MARGIN)
        fmt.register_star_resources(self.document())
        self.setCurrentCharFormat(fmt.char_format())

        self._refit_timer = QTimer(self)
        self._refit_timer.setSingleShot(True)
        self._refit_timer.setInterval(150)
        self._refit_timer.timeout.connect(self._refit_images)

        self.document().contentsChanged.connect(self._refresh_check_styles)

    # --- 상태 --------------------------------------------------------

    @property
    def date(self) -> _dt.date:
        return self._date

    @property
    def autosave_suspended(self) -> bool:
        return self._suspend_autosave

    def load_blocks(self, date: _dt.date, blocks: list[dict]) -> None:
        """해당 날짜의 본문을 문서에 채운다. 자동저장은 트리거하지 않는다.

        블록은 윈도우가 읽어서 넘겨준다 (제목까지 필요해 파일을 한 번만 읽는다).
        """
        self._date = date
        self._suspend_autosave = True
        try:
            serializer.blocks_to_document(
                self.document(),
                blocks,
                self._load_image,
                self.content_width(),
                self.devicePixelRatioF(),
            )
        finally:
            self._suspend_autosave = False
        self.setCurrentCharFormat(fmt.char_format())
        self.moveCursor(QTextCursor.MoveOperation.End)
        self._refresh_check_styles()

    def blocks(self) -> list[dict]:
        return serializer.document_to_blocks(self.document())

    def content_width(self) -> int:
        """본문 텍스트가 실제로 쓸 수 있는 픽셀 폭.

        세로 스크롤바가 아직 없으면 그 폭을 미리 빼둔다. 그러지 않으면 스샷을 넣어
        스크롤바가 생기는 순간 이미지가 본문 폭을 넘어 가로 스크롤이 생긴다.
        """
        scrollbar = self.verticalScrollBar()
        reserved = 0 if scrollbar.isVisible() else scrollbar.sizeHint().width()
        usable = (
            self.viewport().width()
            - 2 * int(self.document().documentMargin())
            - reserved
            - 4
        )
        return max(160, usable)

    def _load_image(self, name: str) -> QImage | None:
        path = storage.image_path(self._date, name)
        if not path.is_file():
            return None
        image = QImage(str(path))
        return None if image.isNull() else image

    # --- 캡쳐 붙여넣기 ------------------------------------------------

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802
        return source.hasImage() or source.hasUrls() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        if source.hasImage():                       # 캡쳐도구 Ctrl+V - 핵심 경로
            image = QImage(source.imageData())
            if not image.isNull():
                self.insert_image(image)
                return

        if source.hasUrls():                        # 이미지 또는 파일 복사/드래그
            local_files = [url.toLocalFile() for url in source.urls() if url.isLocalFile()]
            if local_files:
                self.filesDropped.emit(local_files)
                return

        if source.hasFormat(RICH_MIME) and not self._force_plain:
            super().insertFromMimeData(source)      # 앱 내부 복사 - 서식 유지
            self._adopt_foreign_images()
            return

        # 외부 HTML은 우리 스키마 밖의 서식을 끌고 오므로 평문으로만 받는다.
        self.textCursor().insertText(source.text(), self.currentCharFormat())

    def paste_plain(self) -> None:
        self._force_plain = True
        try:
            self.paste()
        finally:
            self._force_plain = False

    def insert_image(self, image: QImage) -> None:
        """스샷을 디스크에 저장하고 커서 위치에 인라인 삽입한다."""
        name = storage.save_image(self._date, image)
        if not name:
            return

        cursor = self.textCursor()
        cursor.beginEditBlock()
        block_type, _ = fmt.read_block_type(cursor.block())
        if cursor.block().text() or block_type != fmt.TEXT:
            cursor.insertBlock()                    # 이미지는 항상 독립 문단으로
        serializer.insert_image_paragraph(
            cursor, name, image, self.content_width(), self.devicePixelRatioF()
        )
        cursor.insertBlock()                        # 스샷 뒤에 바로 이어서 타이핑
        cursor.setBlockFormat(fmt.block_format(fmt.TEXT))
        cursor.setCharFormat(fmt.char_format())
        cursor.endEditBlock()

        self.setTextCursor(cursor)
        self.setCurrentCharFormat(fmt.char_format())
        self.ensureCursorVisible()
        self.imagePasted.emit()

    def _adopt_foreign_images(self) -> None:
        """다른 날짜에서 붙여넣은 이미지를 현재 날짜 폴더로 가져오고 리소스를 등록한다."""
        doc = self.document()
        changed = False
        for name in self._image_names():
            storage.adopt_image(self._date, name)
            image = self._load_image(name)
            if image is not None:
                serializer.register_image(doc, name, image)
                changed = True
        if changed:
            doc.markContentsDirty(0, doc.characterCount())

    def _image_names(self) -> list[str]:
        names = []
        block = self.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                char_fmt = it.fragment().charFormat()
                if char_fmt.isImageFormat():
                    name = char_fmt.toImageFormat().name()
                    if name and not name.startswith("builtin:"):
                        names.append(name)
                it += 1
            block = block.next()
        return names

    # --- 이미지 폭 재조정 ---------------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_side_margins()
        self._refit_timer.start()

    def _apply_side_margins(self) -> None:
        """본문 폭은 유지하되 남는 공간을 전부 오른쪽에 둔다.

        전체 화면에서 가운데로 몰리면 위쪽 날짜·제목·툴바와 왼쪽 끝이 어긋나 보인다.
        왼쪽을 비우지 않아야 본문이 헤더와 같은 선에서 시작한다.
        """
        scrollbar = self.verticalScrollBar().sizeHint().width()
        right = max(0, self.width() - scrollbar - theme.CONTENT_WIDTH)
        if right != self._right_margin:
            self._right_margin = right
            self.setViewportMargins(0, 0, right, 0)

    def _refit_images(self) -> None:
        """표시 크기만 본문 폭에 맞춰 갱신한다. 디스크 원본과 저장 내용은 그대로."""
        max_width = self.content_width()
        doc = self.document()
        updates = []

        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                it += 1
                char_fmt = fragment.charFormat()
                if not char_fmt.isImageFormat():
                    continue
                image_fmt = char_fmt.toImageFormat()
                name = image_fmt.name()
                if not name or name.startswith("builtin:"):
                    continue
                target = serializer.image_format(
                    name, self._load_image(name), max_width, self.devicePixelRatioF()
                )
                if abs(target.width() - image_fmt.width()) > 0.5:
                    updates.append((fragment.position(), target))
            block = block.next()

        if not updates:
            return

        self._suspend_autosave = True
        try:
            cursor = QTextCursor(doc)
            cursor.beginEditBlock()
            for position, image_fmt in updates:
                cursor.setPosition(position)
                cursor.setPosition(position + 1, QTextCursor.MoveMode.KeepAnchor)
                cursor.setCharFormat(image_fmt)
            cursor.endEditBlock()
        finally:
            self._suspend_autosave = False

    # --- 체크박스 -----------------------------------------------------

    def _marker_rect_hit(self, pos) -> bool:
        """클릭이 체크박스 마커 영역(문단 텍스트 왼쪽 들여쓰기)에 들어왔는가."""
        cursor = self.cursorForPosition(pos)
        block_type, _ = fmt.read_block_type(cursor.block())
        if block_type != fmt.TODO:
            return False
        start = QTextCursor(cursor.block())
        text_left = self.cursorRect(start).left()
        return text_left - MARKER_HIT_WIDTH <= pos.x() < text_left

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._marker_rect_hit(event.position().toPoint()):
            fmt.toggle_checked(self.cursorForPosition(event.position().toPoint()).block())
            self._refresh_check_styles()
            event.accept()
            return
        super().mousePressEvent(event)

    def _refresh_check_styles(self) -> None:
        """완료된 항목을 흐린 취소선으로 보이게 한다.

        문서를 수정하지 않는 뷰 전용 표시라서 저장 내용에는 영향이 없다.
        """
        selections = []
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            block_type, checked = fmt.read_block_type(block)
            if block_type == fmt.TODO and checked and block.length() > 1:
                selection = QTextEdit.ExtraSelection()
                cursor = QTextCursor(doc)
                cursor.setPosition(block.position())
                cursor.setPosition(
                    block.position() + block.length() - 1, QTextCursor.MoveMode.KeepAnchor
                )
                selection.cursor = cursor
                selection.format.setForeground(QColor(theme.PALETTE["ink_faint"]))
                selection.format.setFontStrikeOut(True)
                selections.append(selection)
            block = block.next()
        self.setExtraSelections(selections)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        self._paint_dividers()

    def _paint_dividers(self) -> None:
        """구분선 블록의 가로선을 본문 폭에 맞춰 그린다."""
        doc = self.document()
        content_w = self.content_width()
        left = float(doc.documentMargin())
        right = left + content_w
        viewport_h = self.viewport().height()

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        block = doc.begin()
        while block.isValid():
            block_type, _ = fmt.read_block_type(block)
            if block_type == fmt.DIVIDER and not block.text():
                center_y = float(self.cursorRect(QTextCursor(block)).center().y())
                if -20 <= center_y <= viewport_h + 20:
                    style = fmt.read_divider_style(block)
                    self._draw_divider_line(painter, left, right, center_y, style)
            block = block.next()

        painter.end()

    def _draw_divider_line(
        self, painter: QPainter, left: float, right: float, y: float, style: str
    ) -> None:
        if style == "solid":
            pen = QPen(QColor(theme.PALETTE["border"]))
            pen.setWidthF(1.2)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(left, y), QPointF(right, y))
        elif style == "bold":
            pen = QPen(QColor(theme.PALETTE["ink_soft"]))
            pen.setWidthF(2.0)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(left, y), QPointF(right, y))
        elif style == "double":
            pen = QPen(QColor(theme.PALETTE["border"]))
            pen.setWidthF(1.0)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(left, y - 1.5), QPointF(right, y - 1.5))
            painter.drawLine(QPointF(left, y + 1.5), QPointF(right, y + 1.5))
        else:  # "dashed"
            pen = QPen(QColor(theme.PALETTE["ink_faint"]))
            pen.setWidthF(1.2)
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([4, 3])
            painter.setPen(pen)
            painter.drawLine(QPointF(left, y), QPointF(right, y))

    # --- 키 입력 -----------------------------------------------------

    def keyPressEvent(self, event) -> None:  # noqa: N802
        modifiers = event.modifiers()
        ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
        shift = modifiers & Qt.KeyboardModifier.ShiftModifier

        if ctrl and shift and event.key() == Qt.Key.Key_V:
            self.paste_plain()
            return
        if ctrl and not shift and event.key() in _CHAR_TOGGLES:
            _CHAR_TOGGLES[event.key()](self)
            return
        if ctrl and shift and event.key() == Qt.Key.Key_X:
            fmt.toggle_strike(self)
            return
        if ctrl and shift and event.key() == Qt.Key.Key_D:
            fmt.insert_divider(self)
            return
        alt = modifiers & Qt.KeyboardModifier.AltModifier
        if (ctrl and alt and event.key() == Qt.Key.Key_S) or (ctrl and shift and event.key() == Qt.Key.Key_P):
            fmt.insert_red_star(self)
            return
        # Shift+Tab 은 보통 Key_Backtab 으로 오지만 플랫폼에 따라 Key_Tab+Shift 로도
        # 온다. 내어쓰기를 먼저 걸러야 들여쓰기로 잘못 잡히지 않는다.
        if not ctrl and (event.key() == Qt.Key.Key_Backtab
                         or (event.key() == Qt.Key.Key_Tab and shift)):
            fmt.step_indent(self, -1)
            return
        if event.key() == Qt.Key.Key_Tab and not ctrl:
            fmt.step_indent(self, 1)
            return
        if event.key() == Qt.Key.Key_Space and not ctrl and fmt.try_autoformat(self):
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not shift:
            if fmt.try_divider_autoformat_on_enter(self):
                return
            if fmt.try_list_exit(self):
                return

        # 구분선 블록에서 글자를 입력하면 일반 본문 문단으로 전환
        cur = self.textCursor()
        cur_block = cur.block()
        if (
            fmt.read_block_type(cur_block)[0] == fmt.DIVIDER
            and not cur_block.text()
            and not (ctrl or (modifiers & Qt.KeyboardModifier.AltModifier))
            and event.text()
            and event.text().isprintable()
        ):
            cur.setBlockFormat(fmt.block_format(fmt.TEXT))
            cur.setCharFormat(fmt.char_format())
            self.setTextCursor(cur)

        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        cursor = self.cursorForPosition(event.position().toPoint())
        name = self._image_name_at(cursor)
        if name:
            path = storage.image_path(self._date, name)
            if path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def _image_name_at(self, cursor: QTextCursor) -> str | None:
        for probe in (cursor.position(), cursor.position() + 1):
            check = QTextCursor(self.document())
            check.setPosition(max(0, probe))
            char_fmt = check.charFormat()
            if char_fmt.isImageFormat():
                name = char_fmt.toImageFormat().name()
                if name and not name.startswith("builtin:"):
                    return name
        return None
