"""서식 툴바. 커서 위치의 서식에 맞춰 버튼 상태를 동기화한다."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QToolButton, QWidget

from . import formatting as fmt
from . import theme
from .layout import ColumnRow

_ICON = 16      # 그려서 쓰는 아이콘 한 변 (파일 리소스를 두지 않는다)
CARET = "▾"    # 드롭다운임을 알리는 작은 삼각형


def _swatch(color: str) -> QPixmap:
    pixmap = QPixmap(14, 14)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(theme.PALETTE["border"]))
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(0, 0, 13, 13, 3, 3)
    painter.end()
    return pixmap


def _canvas() -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(_ICON, _ICON)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    return pixmap, painter


def _align_icon(align: str, color: str) -> QPixmap:
    """길이가 다른 가로선 4줄의 배치로 정렬 상태를 그대로 보여준다."""
    pixmap, painter = _canvas()
    painter.setBrush(QColor(color))
    full, short = 13.0, 8.0
    widths = {
        fmt.LEFT: [full, short, full, short],
        "center": [full, short, full, short],
        "right": [full, short, full, short],
        "justify": [full, full, full, full],
    }[align]
    for row, width in enumerate(widths):
        if align == "center":
            x = (_ICON - width) / 2
        elif align == "right":
            x = _ICON - width - 1.5
        else:
            x = 1.5
        painter.drawRoundedRect(QRectF(x, 2.0 + row * 3.4, width, 1.8), 0.9, 0.9)
    painter.end()
    return pixmap


def _stroke(painter: QPainter, color: str, width: float = 1.5) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)


def _check_icon(color: str) -> QPixmap:
    """네모 테두리 + 체크. 체크박스 버튼용."""
    pixmap, painter = _canvas()
    _stroke(painter, color, 1.4)
    painter.drawRoundedRect(QRectF(1.8, 2.6, 12.4, 11.0), 2.4, 2.4)
    painter.drawPolyline([QPointF(4.6, 8.1), QPointF(7.0, 10.4), QPointF(11.6, 5.4)])
    painter.end()
    return pixmap


def _list_icon(color: str) -> QPixmap:
    """점 세 개 + 줄 세 개. 목록 버튼용."""
    pixmap, painter = _canvas()
    for row in range(3):
        y = 3.4 + row * 4.6
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(2.9, y), 1.35, 1.35)
        painter.drawRoundedRect(QRectF(6.4, y - 0.9, 7.6, 1.8), 0.9, 0.9)
    painter.end()
    return pixmap


def _indent_icon(color: str, outward: bool = False) -> QPixmap:
    """위아래는 전체 폭, 가운데 두 줄은 안으로 들어간 문단 + 방향 화살표."""
    pixmap, painter = _canvas()
    painter.setBrush(QColor(color))
    for row, y in enumerate((2.2, 6.0, 9.8, 13.6)):
        x = 1.5 if row in (0, 3) else 7.8
        painter.drawRoundedRect(QRectF(x, y - 0.85, 14.5 - x, 1.7), 0.85, 0.85)
    # 들여쓰기는 오른쪽, 내어쓰기는 왼쪽을 가리킨다.
    tip, base = (1.8, 5.6) if outward else (5.6, 1.8)
    painter.drawPolygon([
        QPointF(base, 6.2), QPointF(base, 11.2), QPointF(tip, 8.7),
    ])
    painter.end()
    return pixmap


def _highlight_icon(color: str) -> QPixmap:
    """형광펜 촉 + 그 색으로 칠한 자국."""
    pixmap, painter = _canvas()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(1.6, 11.4, 12.8, 3.0), 1.5, 1.5)   # 칠한 자국
    _stroke(painter, theme.PALETTE["ink_soft"], 1.3)
    painter.drawPolygon([                                            # 펜촉
        QPointF(4.6, 9.4), QPointF(9.4, 1.8),
        QPointF(12.0, 3.4), QPointF(7.2, 10.2),
    ])
    painter.end()
    return pixmap


def _save_icon(color: str) -> QPixmap:
    """플로피 모양: 몸통 + 위쪽 셔터 + 아래쪽 라벨.

    라벨이 몸통 아래 끝까지 닿으면 좌우 기둥만 남아 'H'처럼 보인다.
    아래·좌우로 몸통 색을 남겨 테두리가 닫히게 한다.
    """
    pixmap, painter = _canvas()
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(1.5, 1.5, 13.0, 13.0), 2.2, 2.2)
    painter.setBrush(QColor(theme.PALETTE["paper"]))
    painter.drawRect(QRectF(5.5, 1.5, 5.0, 3.6))        # 셔터
    painter.drawRect(QRectF(4.0, 8.2, 8.0, 4.6))        # 라벨
    painter.end()
    return pixmap


class _StrikeButton(QToolButton):
    """가운데 줄이 그어진 S.

    QToolButton 텍스트에는 QFont 취소선도 결합 문자도 제대로 그려지지 않아
    글자를 그린 뒤 그 위에 줄을 직접 얹는다. QSS 상태별 색을 그대로 따라간다.
    """

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self.isChecked():
            color = theme.PALETTE["accent"]
        elif self.underMouse():
            color = theme.PALETTE["ink"]
        else:
            color = theme.PALETTE["ink_soft"]

        half = self.fontMetrics().horizontalAdvance(self.text()) / 2 + 1.5
        center = self.rect().center()
        painter = QPainter(self)
        _stroke(painter, color, 1.2)
        painter.drawLine(
            QPointF(center.x() - half, center.y() + 1.0),
            QPointF(center.x() + half, center.y() + 1.0),
        )
        painter.end()


class FormatToolbar(ColumnRow):
    """에디터에 붙어 동작하는 얇은 서식 바."""

    saveRequested = Signal()

    def __init__(self, editor, parent=None):
        # 버튼 안쪽 여백(8px)만큼 당겨야 글자가 본문 왼쪽 선에 온다.
        super().__init__(parent, pad=8, top=5, bottom=5)
        self.setObjectName("Toolbar")
        self._editor = editor
        self._last_highlight = theme.HIGHLIGHT_COLORS[0]

        layout = self.row
        layout.setSpacing(3)

        self.size = self._build_size_button()
        layout.addWidget(self.size)
        layout.addWidget(self._separator())

        self.bold = self._button("B", "굵게  (Ctrl+B)", lambda: fmt.toggle_bold(editor), bold=True)
        self.italic = self._button("I", "기울임  (Ctrl+I)", lambda: fmt.toggle_italic(editor), italic=True)
        self.underline = self._button("U", "밑줄  (Ctrl+U)", lambda: fmt.toggle_underline(editor), underline=True)
        self.strike = self._button(
            "S", "취소선  (Ctrl+Shift+X)", lambda: fmt.toggle_strike(editor), cls=_StrikeButton
        )
        for button in (self.bold, self.italic, self.underline, self.strike):
            layout.addWidget(button)
        layout.addWidget(self._separator())

        self.highlight = self._build_highlight_button()
        layout.addWidget(self.highlight)
        layout.addWidget(self._separator())

        self.todo = self._icon_button(
            _check_icon, "체크박스  (Ctrl+Shift+C)", lambda: self._block(fmt.TODO)
        )
        self.bullet = self._icon_button(
            _list_icon, "목록  (Ctrl+Shift+8)", lambda: self._block(fmt.BULLET)
        )
        layout.addWidget(self.todo)
        layout.addWidget(self.bullet)
        layout.addWidget(self._separator())

        self.align = self._build_align_button()
        layout.addWidget(self.align)

        self.outdent = self._action_icon(
            lambda c: _indent_icon(c, outward=True),
            "내어쓰기  (Shift+Tab)", lambda: self.step_indent(-1),
        )
        self.indent = self._action_icon(
            _indent_icon, "들여쓰기  (Tab)", lambda: self.step_indent(1)
        )
        layout.addWidget(self.outdent)
        layout.addWidget(self.indent)
        layout.addWidget(self._separator())

        self.clear = self._button(
            "서식 지우기", "서식 지우기", lambda: fmt.clear_formatting(editor)
        )
        self.clear.setCheckable(False)
        layout.addWidget(self.clear)
        layout.addStretch(1)

        self.save = self._build_save_button()
        layout.addWidget(self.save)

        editor.currentCharFormatChanged.connect(self.sync)
        editor.cursorPositionChanged.connect(self.sync)
        self.sync()

    # --- 구성 --------------------------------------------------------

    def _icon_button(self, draw, tip, slot):
        """직접 그린 아이콘만 있는 토글 버튼.

        아이콘은 QSS 색을 따르지 않으므로 켜짐/꺼짐 두 벌을 미리 그려 두고 바꿔 끼운다.
        그래야 B/I/U 처럼 글자색이 바뀌는 버튼들과 상태 표현이 어긋나지 않는다.
        """
        button = self._button("", tip, slot)
        button.setIconSize(QSize(_ICON, _ICON))
        button._icons = {
            False: draw(theme.PALETTE["ink_soft"]),
            True: draw(theme.PALETTE["accent"]),
        }
        button.setIcon(button._icons[False])
        return button

    def _action_icon(self, draw, tip, slot):
        """켜짐 상태가 없는 아이콘 버튼 (누를 때마다 한 번 동작)."""
        button = self._button("", tip, slot)
        button.setCheckable(False)
        button.setIcon(draw(theme.PALETTE["ink_soft"]))
        button.setIconSize(QSize(_ICON, _ICON))
        return button

    @staticmethod
    def _set_toggle(button, on: bool) -> None:
        button.setChecked(on)
        button.setIcon(button._icons[on])

    def _button(self, label, tip, slot, *, bold=False, italic=False, underline=False, cls=QToolButton):
        button = cls(self)
        button.setObjectName("FmtButton")
        button.setText(label)
        button.setToolTip(tip)
        button.setCheckable(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        font = QFont(button.font())
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)
        button.setFont(font)

        # 버튼이 포커스를 가져가지 않으므로 클릭 후 에디터 상태만 다시 읽으면 된다.
        button.clicked.connect(lambda _=False, s=slot: (s(), self.sync(), self._editor.setFocus()))
        return button

    def _build_highlight_button(self) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("FmtButton")
        button.setText(CARET)
        button.setToolTip("형광펜  (Ctrl+H 로 마지막 색 적용)")
        button.setCheckable(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIcon(_highlight_icon(self._last_highlight))
        button.setIconSize(QSize(_ICON, _ICON))

        menu = QMenu(button)
        for label, color in theme.HIGHLIGHTS:
            action = QAction(_swatch(color), label, menu)
            action.triggered.connect(lambda _=False, c=color: self.apply_highlight(c))
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _build_size_button(self) -> QToolButton:
        """현재 글자 크기를 숫자로 보여주는 드롭다운."""
        button = QToolButton(self)
        button.setObjectName("FmtButton")
        button.setToolTip("글자 크기  (Ctrl+= 키우기 / Ctrl+- 줄이기)")
        button.setCheckable(False)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setText(f"가 {theme.BODY_PT} {CARET}")

        menu = QMenu(button)
        for point in theme.SIZES:
            suffix = "  (기본)" if point == theme.BODY_PT else ""
            action = QAction(f"{point}{suffix}", menu)
            action.triggered.connect(lambda _=False, p=point: self.apply_size(p))
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _build_align_button(self) -> QToolButton:
        """정렬 4개를 버튼으로 늘어놓기엔 툴바가 빡빡해 드롭다운 하나로 묶는다."""
        button = QToolButton(self)
        button.setObjectName("FmtButton")
        button.setText(CARET)
        button.setCheckable(False)
        button.setToolTip("정렬  (Ctrl+Shift+L / E / R / J)")
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(_ICON, _ICON))
        button.setIcon(_align_icon(fmt.LEFT, theme.PALETTE["ink_soft"]))

        menu = QMenu(button)
        for name, label, keys in fmt.ALIGN_LABELS:
            action = QAction(_align_icon(name, theme.PALETTE["ink"]), f"{label}\t{keys}", menu)
            action.triggered.connect(lambda _=False, a=name: self.apply_align(a))
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _build_save_button(self) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("SaveButton")
        button.setText("저장")
        button.setToolTip("저장  (Ctrl+S)")
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(_ICON, _ICON))
        button.clicked.connect(self.saveRequested)
        self._save_icons = {
            True: _save_icon(theme.PALETTE["accent"]),
            False: _save_icon(theme.PALETTE["ink_faint"]),
        }
        button.setIcon(self._save_icons[False])
        button.setProperty("dirty", "false")
        return button

    def _separator(self) -> QWidget:
        """버튼 높이를 다 채우지 않는 짧은 구분선. 줄이 덜 시끄러워 보인다."""
        holder = QWidget(self)
        holder.setFixedWidth(11)
        line = QFrame(holder)
        line.setObjectName("Sep")
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedWidth(1)
        box = QHBoxLayout(holder)
        box.setContentsMargins(5, 6, 5, 6)
        box.addWidget(line)
        return holder

    # --- 동작 --------------------------------------------------------

    def _block(self, block_type: str) -> None:
        fmt.toggle_block_type(self._editor, block_type)

    def apply_size(self, point: int) -> None:
        fmt.set_size(self._editor, point)
        self.sync()
        self._editor.setFocus()

    def step_size(self, delta: int) -> None:
        fmt.step_size(self._editor, delta)
        self.sync()
        self._editor.setFocus()

    def step_indent(self, delta: int) -> None:
        fmt.step_indent(self._editor, delta)
        self._editor.setFocus()

    def apply_align(self, align: str) -> None:
        fmt.set_alignment(self._editor, align)
        self.sync()
        self._editor.setFocus()

    def set_dirty(self, dirty: bool) -> None:
        """저장할 게 있는지를 버튼 모양으로 드러낸다."""
        self.save.setIcon(self._save_icons[bool(dirty)])
        self.save.setProperty("dirty", "true" if dirty else "false")
        # 속성 선택자로 건 QSS는 다시 polish 해야 반영된다.
        self.save.style().unpolish(self.save)
        self.save.style().polish(self.save)

    def apply_highlight(self, color: str | None = None) -> None:
        color = color or self._last_highlight
        self._last_highlight = color
        self.highlight.setIcon(_highlight_icon(color))
        fmt.toggle_highlight(self._editor, color)
        self.sync()
        self._editor.setFocus()

    def sync(self, *_args) -> None:
        """커서 위치의 서식으로 버튼 체크 상태를 맞춘다."""
        # 커서 위치가 아니라 선택 영역 기준으로 읽어야 역방향 선택에서도 맞는다.
        flags = fmt.read_char_flags(fmt.selection_char_format(self._editor))
        self.bold.setChecked(bool(flags.get("b")))
        self.italic.setChecked(bool(flags.get("i")))
        self.underline.setChecked(bool(flags.get("u")))
        self.strike.setChecked(bool(flags.get("s")))
        self.highlight.setChecked(bool(flags.get("hl")))
        self.size.setText(f"가 {fmt.current_size(self._editor)} {CARET}")

        block = self._editor.textCursor().block()
        block_type, _ = fmt.read_block_type(block)
        self._set_toggle(self.todo, block_type == fmt.TODO)
        self._set_toggle(self.bullet, block_type == fmt.BULLET)

        # 커서가 놓인 문단의 정렬을 아이콘에 반영한다.
        align = fmt.read_align(block)
        self.align.setIcon(_align_icon(align, theme.PALETTE["ink_soft"]))
