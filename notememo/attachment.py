"""첨부파일 목록(자동 줄바꿈 + 마우스 오버 전체 목록 팝업) 및 개별 파일 칩 위젯."""

from __future__ import annotations

import datetime as _dt
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import storage, theme
from .layout import ColumnRow


def _build_type_badge(date: _dt.date, stored_name: str, file_type: str, parent: QWidget) -> QWidget:
    if file_type == "image":
        path = storage.attachment_path(date, stored_name)
        if path.is_file():
            pix = QPixmap(str(path))
            if not pix.isNull():
                thumb = QLabel(parent)
                scaled = pix.scaled(
                    18, 18,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                cropped = scaled.copy(
                    max(0, (scaled.width() - 18) // 2),
                    max(0, (scaled.height() - 18) // 2),
                    18, 18,
                )
                thumb.setPixmap(cropped)
                thumb.setFixedSize(18, 18)
                thumb.setStyleSheet("border-radius: 3px;")
                return thumb

    badge = QLabel(parent)
    badge.setObjectName("AttachmentBadge")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedHeight(18)

    badges = {
        "pdf": ("PDF", "#D9534F"),
        "video": ("영상", "#4A77D4"),
        "image": ("이미지", "#5C946E"),
        "file": ("파일", "#8A8073"),
    }
    text, bg = badges.get(file_type, ("파일", "#8A8073"))
    badge.setText(text)
    badge.setStyleSheet(
        f"background-color: {bg}; color: #FFFFFF; font-size: 9px; "
        f"font-weight: bold; border-radius: 3px; padding: 0 4px;"
    )
    return badge


class FlowLayout(QLayout):
    """가로 폭을 넘어가면 자동으로 다음 줄로 넘기는 플로우 레이아웃."""

    def __init__(self, parent: QWidget | None = None, h_spacing: int = 6, v_spacing: int = 6):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._h_space = h_spacing
        self._v_space = v_spacing
        self._items: list = []

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, max(1, width), 0), True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = eff.x()
        y = eff.y()
        line_h = 0

        for item in self._items:
            sz = item.sizeHint()
            next_x = x + sz.width() + self._h_space
            if next_x - self._h_space > eff.right() + 1 and line_h > 0:
                x = eff.x()
                y = y + line_h + self._v_space
                next_x = x + sz.width() + self._h_space
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), sz))
            x = next_x
            line_h = max(line_h, sz.height())

        return y + line_h - rect.y() + m.bottom()


class _FlowContainer(QWidget):
    """FlowLayout 의 높이를 폭에 맞춰 동기화하는 컨테이너."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("AttachmentContainer")
        self.setStyleSheet("background: transparent;")
        self.flow = FlowLayout(self, h_spacing=6, v_spacing=5)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sync_height(self, width: int | None = None) -> None:
        if self.flow.count() == 0:
            self.setFixedHeight(0)
            return
        avail = width if width is not None and width > 50 else max(300, self.width())
        h = max(28, self.flow.heightForWidth(avail))
        if self.height() != h:
            self.setFixedHeight(h)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.sync_height(event.size().width())


class AttachmentChip(QFrame):
    """첨부파일 1개를 나타내는 칩 위젯."""

    deleteRequested = Signal(str)
    openRequested = Signal(str)
    showInFolderRequested = Signal(str)
    insertRequested = Signal(str)

    def __init__(self, date: _dt.date, attachment: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setObjectName("AttachmentChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self._date = date
        self._attachment = attachment
        self._stored_name = attachment.get("name", "")
        self._orig_name = attachment.get("original_name") or self._stored_name
        self._file_type = attachment.get("type") or storage.get_file_type(self._orig_name)
        self._size = int(attachment.get("size", 0) or 0)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(5)

        badge = _build_type_badge(self._date, self._stored_name, self._file_type, self)
        layout.addWidget(badge)

        name_label = QLabel(self)
        name_label.setObjectName("AttachmentName")
        elided = name_label.fontMetrics().elidedText(
            self._orig_name, Qt.TextElideMode.ElideMiddle, 145
        )
        name_label.setText(elided)
        layout.addWidget(name_label)

        size_label = QLabel(f"({storage.format_size(self._size)})", self)
        size_label.setObjectName("AttachmentSize")
        layout.addWidget(size_label)

        if self._file_type == "image":
            insert_btn = QToolButton(self)
            insert_btn.setObjectName("AttachmentInsert")
            insert_btn.setText("+본문")
            insert_btn.setToolTip("본문에 이미지 삽입")
            insert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            insert_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            insert_btn.clicked.connect(lambda: self.insertRequested.emit(self._stored_name))
            layout.addWidget(insert_btn)

        del_btn = QToolButton(self)
        del_btn.setObjectName("AttachmentDelete")
        del_btn.setText("×")
        del_btn.setToolTip("첨부파일 삭제")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        del_btn.clicked.connect(lambda: self.deleteRequested.emit(self._stored_name))
        layout.addWidget(del_btn)

        self.setToolTip(
            f"{self._orig_name} ({storage.format_size(self._size)})\n"
            "클릭: 파일 열기 | 우클릭: 추가 옵션"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.openRequested.emit(self._stored_name)
            event.accept()
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        open_act = menu.addAction("열기")
        folder_act = menu.addAction("폴더에서 보기")
        insert_act = None
        if self._file_type == "image":
            insert_act = menu.addAction("본문에 이미지 삽입")
        menu.addSeparator()
        del_act = menu.addAction("삭제")

        chosen = menu.exec(event.globalPos())
        if chosen == open_act:
            self.openRequested.emit(self._stored_name)
        elif chosen == folder_act:
            self.showInFolderRequested.emit(self._stored_name)
        elif chosen == insert_act and insert_act:
            self.insertRequested.emit(self._stored_name)
        elif chosen == del_act:
            self.deleteRequested.emit(self._stored_name)


class _AttachmentPopupRow(QFrame):
    """전체 목록 팝업 내 개별 파일 행 (긴 파일명을 생략 없이 표시)."""

    deleteRequested = Signal(str)
    openRequested = Signal(str)
    showInFolderRequested = Signal(str)
    insertRequested = Signal(str)

    def __init__(self, date: _dt.date, attachment: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setObjectName("AttachmentPopupRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stored_name = attachment.get("name", "")
        self._orig_name = attachment.get("original_name") or self._stored_name
        self._file_type = attachment.get("type") or storage.get_file_type(self._orig_name)
        self._size = int(attachment.get("size", 0) or 0)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        badge = _build_type_badge(date, self._stored_name, self._file_type, self)
        layout.addWidget(badge)

        name_label = QLabel(self._orig_name, self)
        name_label.setObjectName("AttachmentName")
        layout.addWidget(name_label, 1)

        size_label = QLabel(storage.format_size(self._size), self)
        size_label.setObjectName("AttachmentSize")
        layout.addWidget(size_label)

        if self._file_type == "image":
            insert_btn = QToolButton(self)
            insert_btn.setObjectName("AttachmentPopupAction")
            insert_btn.setText("+본문")
            insert_btn.setToolTip("본문에 이미지 삽입")
            insert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            insert_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            insert_btn.clicked.connect(lambda: self.insertRequested.emit(self._stored_name))
            layout.addWidget(insert_btn)

        folder_btn = QToolButton(self)
        folder_btn.setObjectName("AttachmentPopupAction")
        folder_btn.setText("폴더")
        folder_btn.setToolTip("폴더에서 보기")
        folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        folder_btn.clicked.connect(lambda: self.showInFolderRequested.emit(self._stored_name))
        layout.addWidget(folder_btn)

        del_btn = QToolButton(self)
        del_btn.setObjectName("AttachmentDelete")
        del_btn.setText("×")
        del_btn.setToolTip("첨부파일 삭제")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        del_btn.clicked.connect(lambda: self.deleteRequested.emit(self._stored_name))
        layout.addWidget(del_btn)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.openRequested.emit(self._stored_name)
            event.accept()
            return
        super().mousePressEvent(event)


class AttachmentPopup(QFrame):
    """마우스 커서를 올리거나 클릭했을 때 전체 첨부파일 리스트를 보여주는 팝업."""

    mouseEntered = Signal()
    mouseLeft = Signal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setObjectName("AttachmentPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(theme.stylesheet())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        self.header_label = QLabel("첨부파일 전체 목록", self)
        self.header_label.setObjectName("AttachmentPopupHeader")
        outer.addWidget(self.header_label)

        self._list_widget = QWidget(self)
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("background: transparent; border: none;")
        self._scroll.setWidget(self._list_widget)
        outer.addWidget(self._scroll)

    def populate(
        self,
        date: _dt.date,
        attachments: list[dict[str, Any]],
        on_open,
        on_folder,
        on_insert,
        on_delete,
    ) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.header_label.setText(f"첨부파일 전체 목록 ({len(attachments)}개)")

        for att in attachments:
            row = _AttachmentPopupRow(date, att, self._list_widget)
            row.openRequested.connect(on_open)
            row.showInFolderRequested.connect(on_folder)
            row.insertRequested.connect(on_insert)
            row.deleteRequested.connect(on_delete)
            self._list_layout.addWidget(row)

        self._list_widget.adjustSize()
        row_h = 34
        content_h = len(attachments) * row_h + max(0, len(attachments) - 1) * 4 + 4
        self._scroll.setFixedHeight(min(280, max(36, content_h)))
        self.setMinimumWidth(440)
        self.adjustSize()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.mouseEntered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.mouseLeft.emit()
        super().leaveEvent(event)


class _SummaryTabButton(QToolButton):
    """마우스 오버를 감지해 전체 목록 팝업을 띄우는 탭 버튼."""

    hovered = Signal()
    unhovered = Signal()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.hovered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.unhovered.emit()
        super().leaveEvent(event)


class AttachmentBar(ColumnRow):
    """첨부파일이 있을 때만 표시되는 가로 바 (자동 줄바꿈 + 전체 목록 호버 탭)."""

    deleteRequested = Signal(str)
    openRequested = Signal(str)
    showInFolderRequested = Signal(str)
    insertRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent, pad=0, top=6, bottom=6)
        self.setObjectName("AttachmentBar")

        self._date: _dt.date = _dt.date.today()
        self._attachments: list[dict[str, Any]] = []

        self.summary_tab = _SummaryTabButton(self)
        self.summary_tab.setObjectName("AttachmentSummaryTab")
        self.summary_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.summary_tab.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.summary_tab.setFixedHeight(26)
        self.summary_tab.setToolTip("마우스를 올리거나 클릭하면 전체 첨부파일 목록을 봅니다")

        self.container = _FlowContainer(self)

        self.row.setSpacing(8)
        self.row.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.row.addWidget(self.summary_tab, 0, Qt.AlignmentFlag.AlignTop)
        self.row.addWidget(self.container, 1)

        self.popup = AttachmentPopup(self)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(220)
        self._hide_timer.timeout.connect(self.popup.hide)

        self.summary_tab.hovered.connect(self.show_popup)
        self.summary_tab.unhovered.connect(self._schedule_hide_popup)
        self.summary_tab.clicked.connect(self._toggle_popup)
        self.popup.mouseEntered.connect(self._hide_timer.stop)
        self.popup.mouseLeft.connect(self._schedule_hide_popup)

        self.hide()

    def set_attachments(self, date: _dt.date, attachments: list[dict[str, Any]]) -> None:
        self._date = date
        self._attachments = list(attachments)

        flow = self.container.flow
        while flow.count():
            item = flow.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not attachments:
            self.popup.hide()
            self.hide()
            return

        self.summary_tab.setText(f"첨부 {len(attachments)}개 ▾")

        for att in attachments:
            chip = AttachmentChip(date, att, self.container)
            chip.deleteRequested.connect(self.deleteRequested)
            chip.openRequested.connect(self.openRequested)
            chip.showInFolderRequested.connect(self.showInFolderRequested)
            chip.insertRequested.connect(self.insertRequested)
            flow.addWidget(chip)

        self.popup.populate(
            date,
            self._attachments,
            lambda name: (self.popup.hide(), self.openRequested.emit(name)),
            lambda name: (self.popup.hide(), self.showInFolderRequested.emit(name)),
            lambda name: (self.popup.hide(), self.insertRequested.emit(name)),
            lambda name: (self.popup.hide(), self.deleteRequested.emit(name)),
        )

        self.show()
        # 레이아웃 반영 후 줄바꿈 높이 계산
        avail_w = max(
            260,
            min(self.width(), theme.CONTENT_WIDTH) - self.summary_tab.sizeHint().width() - 16
            if self.width() > 200
            else theme.CONTENT_WIDTH - 2 * theme.DOC_MARGIN - self.summary_tab.sizeHint().width() - 16,
        )
        self.container.sync_height(avail_w)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "popup"):
            self.popup.hide()
        if self._attachments:
            margins = self.row.contentsMargins()
            avail_w = max(200, self.width() - margins.left() - margins.right() - self.summary_tab.width() - 12)
            self.container.sync_height(avail_w)

    def hideEvent(self, event) -> None:  # noqa: N802
        if hasattr(self, "popup"):
            self.popup.hide()
        super().hideEvent(event)

    def show_popup(self) -> None:
        if not self._attachments:
            return
        self._hide_timer.stop()
        pos = self.summary_tab.mapToGlobal(QPoint(0, self.summary_tab.height() + 4))
        self.popup.move(pos)
        self.popup.show()
        self.popup.raise_()

    def _toggle_popup(self) -> None:
        if self.popup.isVisible():
            self.popup.hide()
        else:
            self.show_popup()

    def _schedule_hide_popup(self) -> None:
        self._hide_timer.start()
