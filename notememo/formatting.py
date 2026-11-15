"""서식의 단일 진실 공급원.

툴바, 단축키, 직렬화, 자동서식이 모두 이 모듈의 매핑을 공유한다.
지원 서식은 아래 화이트리스트로 닫혀 있고, 그 밖의 서식은 저장 시 떨어져 나간다.
"""

from __future__ import annotations

import math
import re
from typing import Any

from PySide6.QtCore import QPointF, QUrl, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPolygonF,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTextImageFormat,
    QTextLength,
    QTextListFormat,
)

from . import theme

# 블록 타입. 노트 제목은 별도 칸으로 빠졌으므로 본문에 제목 서식은 두지 않는다.
TEXT = "text"
BULLET = "bullet"
TODO = "todo"
IMAGE = "image"
DIVIDER = "divider"

DIVIDER_PROP = QTextFormat.Property.UserProperty + 10
DIVIDER_STYLE_PROP = QTextFormat.Property.UserProperty + 11

DEFAULT_DIVIDER_STYLE = "dashed"
DIVIDER_STYLES = [
    ("dashed", "점선 구분선  (---)"),
    ("solid", "실선 구분선  (───)"),
    ("bold", "굵은 구분선  (━━━)"),
    ("double", "이중선 구분선  (═══)"),
]

LIST_TYPES = (BULLET, TODO)
_MARKER = QTextBlockFormat.MarkerType

# 정렬 (문단 단위). JSON 값 <-> Qt 플래그
LEFT = "left"
ALIGNMENTS: dict[str, Qt.AlignmentFlag] = {
    LEFT: Qt.AlignmentFlag.AlignLeft,
    "center": Qt.AlignmentFlag.AlignHCenter,
    "right": Qt.AlignmentFlag.AlignRight,
    "justify": Qt.AlignmentFlag.AlignJustify,
}
ALIGN_LABELS = [
    (LEFT, "왼쪽 정렬", "Ctrl+Shift+L"),
    ("center", "가운데 정렬", "Ctrl+Shift+E"),
    ("right", "오른쪽 정렬", "Ctrl+Shift+R"),
    ("justify", "양쪽 정렬", "Ctrl+Shift+J"),
]


# --- 문자 서식 -----------------------------------------------------

STAR_RED = "#E61B1B"        # 손글씨 느낌의 빨간 별표 강조 색상
DEFAULT_STAR = "☆"


def char_format(
    *,
    size: int | None = None,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    strike: bool = False,
    highlight: str | None = None,
    color: str | None = None,
) -> QTextCharFormat:
    """run 플래그로부터 QTextCharFormat을 만든다. 글꼴은 항상 본문 글꼴이다."""
    fmt = QTextCharFormat()
    fmt.setFontFamilies(theme.SANS_STACK)
    fmt.setFontPointSize(theme.clamp_size(size))
    fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    fmt.setFontItalic(italic)
    fmt.setFontUnderline(underline)
    fmt.setFontStrikeOut(strike)
    if highlight:
        fmt.setBackground(QColor(highlight))
    if color:
        fmt.setForeground(QColor(color))
    return fmt


def read_char_flags(fmt: QTextCharFormat) -> dict[str, Any]:
    """화이트리스트에 있는 플래그만 뽑아낸다. 글꼴 종류는 무시."""
    flags: dict[str, Any] = {}
    if fmt.fontWeight() >= QFont.Weight.Bold:
        flags["b"] = True
    if fmt.fontItalic():
        flags["i"] = True
    if fmt.fontUnderline():
        flags["u"] = True
    if fmt.fontStrikeOut():
        flags["s"] = True
    brush = fmt.background()
    if brush.style() != Qt.BrushStyle.NoBrush and brush.color().alpha() > 0:
        flags["hl"] = brush.color().name().upper()
    fg = fmt.foreground()
    if fg.style() != Qt.BrushStyle.NoBrush and fg.color().isValid() and fg.color().alpha() > 0:
        hex_color = fg.color().name().upper()
        if hex_color != theme.PALETTE["ink"].upper():
            flags["c"] = hex_color

    # Qt는 크기 미설정을 0 이나 -1 로 돌려준다. 기본값이면 키를 넣지 않는다.
    point = round(fmt.fontPointSize())
    if point > 0 and point != theme.BODY_PT:
        flags["sz"] = theme.clamp_size(point)
    return flags


def flags_to_kwargs(flags: dict[str, Any]) -> dict[str, Any]:
    """JSON run 플래그를 char_format() 인자로 변환."""
    return {
        "size": flags.get("sz"),
        "bold": bool(flags.get("b")),
        "italic": bool(flags.get("i")),
        "underline": bool(flags.get("u")),
        "strike": bool(flags.get("s")),
        "highlight": flags.get("hl"),
        "color": flags.get("c"),
    }


# --- 블록 서식 -----------------------------------------------------

MAX_INDENT = 12     # Qt 들여쓰기는 단계 값이다. 이상한 값이 들어오면 잘라낸다.


def clamp_indent(indent: int | None) -> int:
    try:
        return max(0, min(MAX_INDENT, int(indent or 0)))
    except (TypeError, ValueError):
        return 0


def block_format(
    block_type: str = TEXT,
    checked: bool = False,
    image: bool = False,
    align: str = LEFT,
    indent: int = 0,
    divider_style: str = DEFAULT_DIVIDER_STYLE,
) -> QTextBlockFormat:
    proportional = QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
    fmt = QTextBlockFormat()
    fmt.setAlignment(ALIGNMENTS.get(align, ALIGNMENTS[LEFT]))
    fmt.setIndent(clamp_indent(indent))
    if block_type == DIVIDER:
        fmt.setProperty(
            QTextFormat.Property.BlockTrailingHorizontalRulerWidth,
            QTextLength(QTextLength.Type.PercentageLength, 100),
        )
        fmt.setBackground(QColor(0, 0, 0, 0))
        fmt.setProperty(DIVIDER_PROP, True)
        fmt.setProperty(DIVIDER_STYLE_PROP, divider_style)
        fmt.setTopMargin(10)
        fmt.setBottomMargin(10)
        fmt.setLineHeight(100, proportional)
        fmt.setMarker(_MARKER.NoMarker)
        return fmt
    if image:
        # 이미지 줄에 본문 줄간격(170%)을 주면 이미지 높이의 70%만큼 빈 공간이 생긴다.
        fmt.setLineHeight(100, proportional)
        fmt.setTopMargin(10)
        fmt.setBottomMargin(10)
    else:
        fmt.setLineHeight(theme.LINE_HEIGHT_PCT, proportional)
        fmt.setTopMargin(0)
        fmt.setBottomMargin(6)
    if block_type == TODO:
        fmt.setMarker(_MARKER.Checked if checked else _MARKER.Unchecked)
    else:
        fmt.setMarker(_MARKER.NoMarker)
    return fmt


def read_block_type(block) -> tuple[str, bool]:
    """(타입, 체크 여부)."""
    fmt = block.blockFormat()
    if (
        fmt.boolProperty(DIVIDER_PROP)
        or fmt.hasProperty(QTextFormat.Property.BlockTrailingHorizontalRulerWidth)
    ) and not block.text():
        return DIVIDER, False
    if block.textList() is not None:
        if fmt.marker() != _MARKER.NoMarker:
            return TODO, fmt.marker() == _MARKER.Checked
        return BULLET, False
    return TEXT, False


def read_divider_style(block) -> str:
    """구분선 블록의 스타일(dashed, solid, bold, double)."""
    fmt = block.blockFormat()
    style = fmt.property(DIVIDER_STYLE_PROP)
    return str(style) if style in ("dashed", "solid", "bold", "double") else DEFAULT_DIVIDER_STYLE


def read_align(block) -> str:
    """문단의 가로 정렬. Qt는 미설정을 0으로 돌려주기도 하므로 왼쪽으로 정규화한다."""
    horizontal = block.blockFormat().alignment() & Qt.AlignmentFlag.AlignHorizontal_Mask
    for name, flag in ALIGNMENTS.items():
        if name != LEFT and horizontal & flag:
            return name
    return LEFT


def read_indent(block) -> int:
    """문단 들여쓰기 단계.

    Qt는 목록 항목에서 Backspace로 빠져나갈 때 글자가 제자리에 남도록 이 값을
    올려 둔다. 저장하지 않으면 다시 열었을 때 줄이 왼쪽으로 튀어버린다.
    """
    return clamp_indent(block.blockFormat().indent())


def step_indent(editor, delta: int) -> None:
    """커서가 걸친 문단들의 들여쓰기를 한 단계 넣거나 뺀다.

    들여쓰기만 병합한다. setBlockFormat 은 리스트 연결(objectIndex)까지 지운다.
    """
    cursor = editor.textCursor()
    document = cursor.document()
    start, end = sorted((cursor.selectionStart(), cursor.selectionEnd()))
    block = document.findBlock(start)
    last = document.findBlock(end)

    worker = QTextCursor(document)
    # Qt 는 beginEditBlock 시점의 커서 위치를 되돌리기 기록에 남긴다. 위치를 먼저
    # 잡지 않으면 Ctrl+Z 때 커서가 문서 맨 앞(0)으로 가서 화면이 위로 튄다.
    worker.setPosition(block.position())
    worker.beginEditBlock()
    while block.isValid():
        if read_block_type(block)[0] != DIVIDER:
            only_indent = QTextBlockFormat()
            only_indent.setIndent(clamp_indent(read_indent(block) + delta))
            worker.setPosition(block.position())
            worker.mergeBlockFormat(only_indent)
        if block == last:
            break
        block = block.next()
    worker.endEditBlock()


def set_alignment(editor, align: str) -> None:
    """커서가 걸친 문단들의 정렬만 바꾼다.

    setBlockFormat 은 리스트 연결(objectIndex)까지 지우므로 반드시 merge 여야 한다.
    """
    only_align = QTextBlockFormat()
    only_align.setAlignment(ALIGNMENTS.get(align, ALIGNMENTS[LEFT]))
    editor.textCursor().mergeBlockFormat(only_align)


def list_format() -> QTextListFormat:
    fmt = QTextListFormat()
    fmt.setStyle(QTextListFormat.Style.ListDisc)
    fmt.setIndent(1)
    return fmt


def _fragment_spans(block) -> list[tuple[dict, int, int]]:
    """블록 내 텍스트 프래그먼트의 (char_format 인자, 시작, 끝). 이미지는 제외."""
    spans = []
    it = block.begin()
    while not it.atEnd():
        fragment = it.fragment()
        if fragment.isValid() and not fragment.charFormat().isImageFormat():
            spans.append((
                flags_to_kwargs(read_char_flags(fragment.charFormat())),
                fragment.position(),
                fragment.position() + fragment.length(),
            ))
        it += 1
    return spans


def apply_block_type(
    cursor: QTextCursor,
    block_type: str,
    checked: bool = False,
    keep_layout: bool = True,
) -> None:
    """커서가 걸친 모든 블록의 타입을 바꾼다. 리스트 진입과 이탈까지 처리.

    블록 서식을 통째로 갈아끼우므로, 정렬과 들여쓰기는 미리 읽어뒀다가 다시 실어
    보낸다. 그러지 않으면 가운데 정렬한 문단을 체크박스로 바꾸는 순간 정렬이 풀린다.
    """
    doc = cursor.document()
    start, end = sorted((cursor.selectionStart(), cursor.selectionEnd()))
    block = doc.findBlock(start)
    last = doc.findBlock(end)
    cursor_kwargs = flags_to_kwargs(read_char_flags(cursor.charFormat()))

    worker = QTextCursor(doc)
    # Qt 는 beginEditBlock 시점의 커서 위치를 되돌리기 기록에 남긴다. 위치를 먼저
    # 잡지 않으면 Ctrl+Z 때 커서가 문서 맨 앞(0)으로 가서 화면이 위로 튄다.
    worker.setPosition(block.position())
    worker.beginEditBlock()
    while block.isValid():
        keep_checked = checked
        if block_type == TODO and not checked:
            # 이미 체크된 항목을 다시 체크박스로 지정할 때 상태를 유지한다.
            was_type, was_checked = read_block_type(block)
            keep_checked = was_checked if was_type == TODO else False

        align = read_align(block) if keep_layout else LEFT
        indent = read_indent(block) if keep_layout else 0
        spans = _fragment_spans(block)      # 글자 크기 등은 여기 담아 두고 되돌린다

        if block.textList() is not None:
            block.textList().remove(block)

        worker.setPosition(block.position())
        # setBlockFormat이 리스트 연결(objectIndex)을 지우므로 반드시 createList보다 먼저.
        worker.setBlockFormat(
            block_format(block_type, keep_checked, align=align, indent=indent)
        )
        if block_type in LIST_TYPES:
            worker.createList(list_format())

        if spans:
            # 목록 불릿(●) 크기는 blockCharFormat 을 따르므로 첫 글자 크기에 맞춘다.
            worker.setBlockCharFormat(char_format(size=spans[0][0].get("size")))
            # 글꼴은 블록 서식과 무관하게 다시 입혀 문서를 정규화한다.
            for kwargs, frag_start, frag_end in spans:
                span = QTextCursor(doc)
                span.setPosition(frag_start)
                span.setPosition(frag_end, QTextCursor.MoveMode.KeepAnchor)
                span.setCharFormat(char_format(**kwargs))
        else:
            # 빈 줄에서 목록을 켤 때도 현재 지정한 글자 크기·서식을 유지한다.
            worker.setBlockCharFormat(char_format(size=cursor_kwargs.get("size")))
            worker.setCharFormat(char_format(**cursor_kwargs))

        if block == last:
            break
        block = block.next()
    worker.endEditBlock()


# --- 토글 (에디터 대상) --------------------------------------------

def _merge(editor, fmt: QTextCharFormat) -> None:
    """선택 영역이 있으면 선택 영역에, 없으면 다음 입력 서식에 적용된다.

    빈 문단이거나 선택 영역이 문단 첫 글자를 포함하면 blockCharFormat 도 함께
    갱신해야 목록 불릿(●) 크기가 본문 글자 크기와 어긋나지 않고, 첫 글자를 지우거나
    목록을 시작할 때 이전 문단의 서식(큰 글자 등)으로 되돌아가지 않는다.
    """
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    if not cursor.hasSelection():
        if cursor.positionInBlock() == 0:
            cursor.mergeBlockCharFormat(fmt)
    else:
        doc = cursor.document()
        start, end = sorted((cursor.selectionStart(), cursor.selectionEnd()))
        block = doc.findBlock(start)
        last = doc.findBlock(end)
        worker = QTextCursor(doc)
        while block.isValid():
            first_visible = block.position() + (len(block.text()) - len(block.text().lstrip()))
            if start <= first_visible:
                worker.setPosition(block.position())
                worker.mergeBlockCharFormat(fmt)
            if block == last:
                break
            block = block.next()
    editor.mergeCurrentCharFormat(fmt)
    cursor.endEditBlock()


def selection_char_format(editor) -> QTextCharFormat:
    """켜짐/꺼짐을 판단할 때 기준으로 삼을 문자 서식.

    선택 영역이 있으면 그 **첫 글자**를 본다. QTextEdit.currentCharFormat() 은
    커서 위치 기준이라, 오른쪽에서 왼쪽으로 끌어 선택하면 커서가 선택 앞쪽에 놓여
    선택 밖 글자의 서식을 읽는다. 그래서 이미 칠한 형광펜을 다시 눌러도 꺼지지 않고
    볼드/기울임/밑줄/취소선도 같은 증상을 보였다.
    """
    cursor = editor.textCursor()
    if not cursor.hasSelection():
        return editor.currentCharFormat()
    document = cursor.document()
    probe = QTextCursor(document)
    probe.setPosition(min(cursor.selectionStart() + 1, document.characterCount() - 1))
    return probe.charFormat()


def toggle_bold(editor) -> None:
    on = selection_char_format(editor).fontWeight() >= QFont.Weight.Bold
    fmt = QTextCharFormat()
    fmt.setFontWeight(QFont.Weight.Normal if on else QFont.Weight.Bold)
    _merge(editor, fmt)


def toggle_italic(editor) -> None:
    fmt = QTextCharFormat()
    fmt.setFontItalic(not selection_char_format(editor).fontItalic())
    _merge(editor, fmt)


def toggle_underline(editor) -> None:
    fmt = QTextCharFormat()
    fmt.setFontUnderline(not selection_char_format(editor).fontUnderline())
    _merge(editor, fmt)


def toggle_strike(editor) -> None:
    fmt = QTextCharFormat()
    fmt.setFontStrikeOut(not selection_char_format(editor).fontStrikeOut())
    _merge(editor, fmt)


def current_highlight(editor) -> str | None:
    return read_char_flags(selection_char_format(editor)).get("hl")


def toggle_highlight(editor, color: str) -> None:
    """이미 칠해진 곳에 같은 색을 다시 적용하면 해제한다."""
    fmt = QTextCharFormat()
    if current_highlight(editor) == color.upper():
        fmt.setBackground(QColor(0, 0, 0, 0))
    else:
        fmt.setBackground(QColor(color))
    _merge(editor, fmt)


# --- 글자 크기 -----------------------------------------------------

def current_size(editor) -> int:
    point = round(selection_char_format(editor).fontPointSize())
    return theme.clamp_size(point) if point > 0 else theme.BODY_PT


def set_size(editor, point: int) -> None:
    fmt = QTextCharFormat()
    fmt.setFontPointSize(theme.clamp_size(point))
    _merge(editor, fmt)


def step_size(editor, delta: int) -> None:
    """제공 크기 목록에서 한 칸 위/아래로 옮긴다."""
    sizes = theme.SIZES
    try:
        index = sizes.index(current_size(editor))
    except ValueError:
        index = sizes.index(theme.BODY_PT)
    set_size(editor, sizes[max(0, min(len(sizes) - 1, index + delta))])


# --- 블록 토글 -----------------------------------------------------

def toggle_block_type(editor, block_type: str) -> None:
    """이미 그 타입이면 본문으로 되돌린다."""
    cursor = editor.textCursor()
    saved_kwargs = flags_to_kwargs(read_char_flags(editor.currentCharFormat()))
    if not cursor.hasSelection() and not cursor.block().text():
        cursor.setCharFormat(char_format(**saved_kwargs))
    current, _ = read_block_type(cursor.block())
    apply_block_type(cursor, TEXT if current == block_type else block_type)
    if not cursor.hasSelection():
        editor.setCurrentCharFormat(char_format(**saved_kwargs))


def clear_formatting(editor) -> None:
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    if cursor.hasSelection():
        cursor.setCharFormat(char_format())
    else:
        cursor.setBlockCharFormat(char_format())
        cursor.setCharFormat(char_format())
    apply_block_type(cursor, TEXT, keep_layout=False)   # 정렬·들여쓰기도 되돌린다
    cursor.endEditBlock()
    editor.setCurrentCharFormat(char_format())


def toggle_checked(block) -> None:
    block_type, checked = read_block_type(block)
    if block_type != TODO:
        return
    # setBlockFormat은 리스트 연결(objectIndex)까지 지우므로 마커만 병합한다.
    marker_only = QTextBlockFormat()
    marker_only.setMarker(_MARKER.Unchecked if checked else _MARKER.Checked)
    QTextCursor(block).mergeBlockFormat(marker_only)


def insert_divider(editor, style: str = DEFAULT_DIVIDER_STYLE) -> None:
    """커서 위치에 구분선을 삽입하고 바로 아래에 본문 문단을 생성하여 입력을 이어간다."""
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    block = cursor.block()
    block_type, _ = read_block_type(block)

    # 현재 줄에 글자가 있거나 목록/체크박스인 경우 새 줄을 열어 구분선을 넣는다.
    if block.text() or block_type != TEXT:
        cursor.insertBlock()

    cursor.setBlockFormat(block_format(DIVIDER, divider_style=style))
    if cursor.block().textList() is not None:
        cursor.block().textList().remove(cursor.block())

    # 구분선 바로 아래에 일반 본문 줄을 만들어 이어서 타이핑할 수 있게 한다.
    cursor.insertBlock()
    cursor.setBlockFormat(block_format(TEXT))
    cursor.setCharFormat(char_format())
    cursor.endEditBlock()

    editor.setTextCursor(cursor)
    editor.setCurrentCharFormat(char_format())
    editor.ensureCursorVisible()


BUILTIN_STAR_SKETCH = "builtin:star_sketch"
BUILTIN_STAR_FILLED = "builtin:star_filled"


def make_star_image(filled: bool = False, color: str = STAR_RED, px: int = 48) -> QImage:
    """고해상도 스케치 스타일 또는 채움 스타일의 빨간 별표 QImage 생성."""
    scale = 3.0
    total = int(px * scale)
    img = QImage(total, total, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(scale, scale)
    cx, cy = px / 2.0, px / 2.0
    r_out = px * 0.44
    if filled:
        r_in = px * 0.19
        points = [
            QPointF(
                cx + (r_out if i % 2 == 0 else r_in) * math.cos(-math.pi / 2 + i * math.pi / 5),
                cy + (r_out if i % 2 == 0 else r_in) * math.sin(-math.pi / 2 + i * math.pi / 5),
            )
            for i in range(10)
        ]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF(points))
    else:
        # 손글씨로 쓱쓱 그은 5점 별 (스케치 스타일)
        points = [
            QPointF(
                cx + r_out * math.cos(-math.pi / 2 + i * 4 * math.pi / 5),
                cy + r_out * math.sin(-math.pi / 2 + i * 4 * math.pi / 5),
            )
            for i in range(6)
        ]
        pen = QPen(QColor(color))
        pen.setWidthF(px * 0.08)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(points)
    painter.end()
    return img


def register_star_resources(doc) -> None:
    """문서에 스케치 별표 인라인 이미지 리소스를 등록한다."""
    resource_type = doc.ResourceType.ImageResource
    doc.addResource(resource_type, QUrl(BUILTIN_STAR_SKETCH), make_star_image(filled=False))
    doc.addResource(resource_type, QUrl(BUILTIN_STAR_FILLED), make_star_image(filled=True))


def insert_star_run(cursor: QTextCursor, star_type: str = "sketch", size: int | float | None = None) -> None:
    """커서 위치에 인라인 별표 이미지를 삽입한다."""
    doc = cursor.document()
    register_star_resources(doc)
    pt = size or round(cursor.charFormat().fontPointSize()) or theme.BODY_PT
    px = max(14, round(pt * 1.35))

    img_fmt = QTextImageFormat()
    img_fmt.setName(BUILTIN_STAR_FILLED if star_type == "filled" else BUILTIN_STAR_SKETCH)
    img_fmt.setWidth(px)
    img_fmt.setHeight(px)
    img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
    if pt != theme.BODY_PT:
        img_fmt.setFontPointSize(theme.clamp_size(pt))
    cursor.insertImage(img_fmt)


def insert_red_star(editor, star_type: str = "sketch") -> None:
    """커서 위치(또는 선택 앞)에 손글씨 스케치 느낌의 빨간 별표를 삽입한다."""
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    cur_sz = current_size(editor)

    if cursor.hasSelection():
        cursor.setPosition(cursor.selectionStart())

    insert_star_run(cursor, star_type=star_type, size=cur_sz)

    # 별표 뒤에 공백 하나를 넣고 본문 입력 서식을 복원
    reset_fmt = char_format(size=cur_sz)
    cursor.setCharFormat(reset_fmt)
    cursor.insertText(" ", reset_fmt)
    cursor.endEditBlock()

    editor.setTextCursor(cursor)
    editor.setCurrentCharFormat(reset_fmt)
    editor.ensureCursorVisible()


# --- 마크다운식 자동 서식 ------------------------------------------

_AUTOFORMAT = [
    (re.compile(r"^[-*]$"), BULLET),
    (re.compile(r"^\[\s?\]$"), TODO),
    (re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$"), DIVIDER),
]


def try_autoformat(editor) -> bool:
    """스페이스바 직전의 접두어를 블록 서식으로 바꾼다. 처리했으면 True."""
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return False
    block = cursor.block()
    if read_block_type(block)[0] != TEXT:
        return False
    prefix = block.text()[: cursor.positionInBlock()]
    if prefix != block.text():      # 커서 뒤에 글자가 더 있으면 건드리지 않는다
        return False

    for pattern, block_type in _AUTOFORMAT:
        if not pattern.match(prefix):
            continue
        # 접두어('-')를 지우는 순간 빈 블록이 되어 blockCharFormat(이전 줄 크기)으로
        # 돌아가 버리므로 현재 입력 서식을 보존해 다시 입힌다.
        saved_kwargs = flags_to_kwargs(read_char_flags(editor.currentCharFormat()))
        # Ctrl+Z 한 번으로 되돌아가도록 하나의 undo 단위로 묶는다.
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(prefix)
        )
        cursor.removeSelectedText()
        if block_type == DIVIDER:
            cursor.setBlockFormat(block_format(DIVIDER))
            cursor.insertBlock()
            cursor.setBlockFormat(block_format(TEXT))
            cursor.setCharFormat(char_format(**saved_kwargs))
        else:
            cursor.setCharFormat(char_format(**saved_kwargs))
            apply_block_type(cursor, block_type)
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        editor.setCurrentCharFormat(char_format(**saved_kwargs))
        return True
    return False


def try_empty_line_enter(editor) -> bool:
    """빈 본문 줄에서 Enter 를 눌렀을 때 줄을 직접 늘린다. 처리했으면 True.

    Qt 는 '빈 블록 + 기본값이 아닌 블록 서식' 에서 Enter 를 누르면 줄을 늘리는 대신
    블록 서식을 지운다(목록에서 빠져나오라는 뜻). 이 앱은 목록 빠져나오기를
    try_list_exit 에서 이미 직접 처리하므로, 이 규칙은 'Enter 가 한 번 먹지 않는다'
    는 증상으로만 나타난다. 저장 후 다시 연 노트는 모든 블록이 명시적 서식을 갖기
    때문에 빈 줄마다 이 증상이 생긴다.
    """
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return False
    block = cursor.block()
    if block.text() or read_block_type(block)[0] != TEXT:
        return False
    if not block.blockFormat().properties():
        return False                       # 기본 서식이면 Qt 기본 동작이 이미 맞다

    block_fmt = QTextBlockFormat(block.blockFormat())
    char_fmt = QTextCharFormat(editor.currentCharFormat())
    cursor.beginEditBlock()
    cursor.insertBlock(block_fmt, char_fmt)
    cursor.endEditBlock()
    editor.setTextCursor(cursor)
    editor.setCurrentCharFormat(char_fmt)
    editor.ensureCursorVisible()
    return True


def try_divider_enter(editor) -> bool:
    """구분선 줄에서 Enter: 구분선 위에 빈 본문 줄을 만들고 커서를 그리로 옮긴다.

    구분선은 '빈 블록 + 블록 서식' 이라서 Qt 기본 동작에 맡기면 블록을 쪼개면서
    구분선 서식까지 복제한다. 그래서 구분선이 하나 더 생기고, 한 번 더 누르면
    이번엔 Qt 가 빈 블록의 서식을 지워버려 구분선이 사라진다. 양쪽 서식을 직접
    지정해 Qt 의 서식 상속에 기대지 않는다.
    """
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return False
    block = cursor.block()
    if read_block_type(block)[0] != DIVIDER:
        return False

    style = read_divider_style(block)
    doc = editor.document()
    number = block.blockNumber()

    worker = QTextCursor(doc)
    # 위치를 먼저 잡아야 Ctrl+Z 때 커서가 문서 맨 앞으로 튀지 않는다.
    worker.setPosition(block.position())
    worker.beginEditBlock()
    worker.insertBlock()
    above = QTextCursor(doc.findBlockByNumber(number))
    above.setBlockFormat(block_format(TEXT))
    above.setBlockCharFormat(char_format())
    QTextCursor(doc.findBlockByNumber(number + 1)).setBlockFormat(
        block_format(DIVIDER, divider_style=style)
    )
    worker.endEditBlock()

    moved = QTextCursor(doc)
    moved.setPosition(doc.findBlockByNumber(number).position())
    editor.setTextCursor(moved)
    editor.setCurrentCharFormat(char_format())
    editor.ensureCursorVisible()
    return True


def try_divider_autoformat_on_enter(editor) -> bool:
    """줄 전체가 '---', '***', '___' (3개 이상)일 때 Enter를 누르면 구분선으로 치환."""
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return False
    block = cursor.block()
    if read_block_type(block)[0] != TEXT:
        return False
    text = block.text().strip()
    if not re.match(r"^(?:-{3,}|\*{3,}|_{3,})$", text):
        return False
    saved_kwargs = flags_to_kwargs(read_char_flags(editor.currentCharFormat()))
    cursor.beginEditBlock()
    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    cursor.setBlockFormat(block_format(DIVIDER))
    cursor.insertBlock()
    cursor.setBlockFormat(block_format(TEXT))
    cursor.setCharFormat(char_format(**saved_kwargs))
    cursor.endEditBlock()
    editor.setTextCursor(cursor)
    editor.setCurrentCharFormat(char_format(**saved_kwargs))
    return True


def try_list_exit(editor) -> bool:
    """빈 리스트 항목에서 Enter를 누르면 본문으로 빠져나온다. 처리했으면 True."""
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return False
    block = cursor.block()
    if read_block_type(block)[0] not in LIST_TYPES or block.text():
        return False
    saved_kwargs = flags_to_kwargs(read_char_flags(editor.currentCharFormat()))
    cursor.setCharFormat(char_format(**saved_kwargs))
    apply_block_type(cursor, TEXT)
    editor.setCurrentCharFormat(char_format(**saved_kwargs))
    return True
