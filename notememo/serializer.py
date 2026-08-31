"""QTextDocument <-> 블록 JSON 양방향 변환.

데이터 유실 위험이 가장 큰 지점이므로 왕복 동일성을 tests/test_serializer.py 로 검증한다.

이미지는 **블록 안의 run** 이다. 한 문단에 스샷을 둘 나란히 놓을 수 있어야 하므로
이미지를 독립 블록으로 두지 않는다 (그러면 저장할 때마다 줄이 나뉘어 버린다).
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextCursor, QTextDocument, QTextImageFormat

from . import formatting as fmt
from .formatting import IMAGE, TEXT, TODO

ImageLoader = Callable[[str], "QImage | None"]

# 이미지를 못 찾았을 때 쓸 자리표시자 크기
_MISSING_W, _MISSING_H = 320, 90


# --- 이미지 ---------------------------------------------------------

def image_format(name: str, image: QImage | None, max_width: int, dpr: float = 1.0) -> QTextImageFormat:
    """디스크 원본은 그대로 두고 표시 크기만 본문 폭에 맞춘다."""
    image_fmt = QTextImageFormat()
    image_fmt.setName(name)
    if image is None or image.isNull() or image.width() <= 0 or image.height() <= 0:
        image_fmt.setWidth(_MISSING_W)
        image_fmt.setHeight(_MISSING_H)
        return image_fmt

    # 고DPI 화면에서 캡쳐한 스샷이 화면에서 보이던 크기로 들어오도록 DPR로 나눈다.
    natural = image.width() / max(dpr, 1.0)
    width = max(1.0, min(natural, float(max_width)))
    image_fmt.setWidth(width)
    image_fmt.setHeight(round(image.height() * width / image.width()))
    return image_fmt


def register_image(doc: QTextDocument, name: str, image: QImage | None) -> None:
    if image is not None and not image.isNull():
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(name), image)


def insert_image_run(
    cursor: QTextCursor,
    name: str,
    image: QImage | None,
    max_width: int,
    dpr: float = 1.0,
) -> None:
    """커서 위치에 이미지만 넣는다. 문단 서식은 건드리지 않는다."""
    register_image(cursor.document(), name, image)
    cursor.insertImage(image_format(name, image, max_width, dpr))


def insert_image_paragraph(
    cursor: QTextCursor,
    name: str,
    image: QImage | None,
    max_width: int,
    dpr: float = 1.0,
    align: str = fmt.LEFT,
    indent: int = 0,
) -> None:
    """이미지 하나만 있는 문단을 만든다 (붙여넣기 경로)."""
    cursor.setBlockFormat(fmt.block_format(TEXT, image=True, align=align, indent=indent))
    insert_image_run(cursor, name, image, max_width, dpr)


# --- 문서 -> 블록 ---------------------------------------------------

def document_to_blocks(doc: QTextDocument) -> list[dict[str, Any]]:
    """문단 하나가 블록 하나. 이미지는 등장 순서대로 run 이 된다."""
    out: list[dict[str, Any]] = []

    block = doc.begin()
    while block.isValid():
        block_type, checked = fmt.read_block_type(block)
        runs: list[dict[str, Any]] = []

        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            it += 1
            if not fragment.isValid():
                continue

            char_fmt = fragment.charFormat()
            if char_fmt.isImageFormat():
                name = char_fmt.toImageFormat().name()
                if name:
                    # 같은 이미지가 연달아 있으면 Qt 가 한 프래그먼트로 묶는다.
                    # 프래그먼트의 글자 수(각 U+FFFC)가 곧 이미지 개수다.
                    for _ in range(max(1, len(fragment.text()))):
                        runs.append({"image": name})
                continue

            # U+2028(소프트 줄바꿈)은 그대로 둬야 왕복 시 문단이 쪼개지지 않는다.
            text = fragment.text()
            if not text:
                continue
            flags = fmt.read_char_flags(char_fmt)
            if runs and "text" in runs[-1] and _same_flags(runs[-1], flags):
                runs[-1]["text"] += text          # 인접 run 병합
            else:
                runs.append({"text": text, **flags})

        out.append(_make_block(
            block_type, checked, fmt.read_align(block), fmt.read_indent(block), runs
        ))
        block = block.next()

    return _trim_trailing_empty(out)


def _make_block(
    block_type: str, checked: bool, align: str, indent: int, runs: list[dict]
) -> dict[str, Any]:
    block: dict[str, Any] = {"type": block_type}
    if block_type == TODO:
        block["checked"] = checked
    if align != fmt.LEFT:       # 기본값은 키를 빼서 파일을 깔끔하게 유지한다
        block["align"] = align
    if indent:
        block["indent"] = indent
    block["runs"] = [dict(run) for run in runs]
    return block


def _same_flags(run: dict[str, Any], flags: dict[str, Any]) -> bool:
    return {k: v for k, v in run.items() if k != "text"} == flags


def has_image(block: dict[str, Any]) -> bool:
    return any(run.get("image") for run in block.get("runs", []))


def _is_empty(block: dict[str, Any]) -> bool:
    """글자도 이미지도 없는 문단."""
    return not any(run.get("text") or run.get("image") for run in block.get("runs", []))


def _trim_trailing_empty(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """끝에 남은 빈 문단을 잘라낸다.

    체크박스와 목록은 사용자가 일부러 만든 구조라서 비어 있어도 남긴다.
    """
    while blocks and blocks[-1].get("type") == TEXT and _is_empty(blocks[-1]):
        blocks.pop()
    return blocks


# --- 블록 -> 문서 ---------------------------------------------------

def normalize_block(block: dict[str, Any]) -> dict[str, Any]:
    """옛 형식의 독립 이미지 블록을 이미지 run 하나를 가진 문단으로 바꾼다."""
    if block.get("type") != IMAGE:
        return block
    moved = {k: v for k, v in block.items() if k not in ("type", "file", "runs")}
    moved["type"] = TEXT
    moved["runs"] = [{"image": block.get("file") or ""}]
    return moved


def blocks_to_document(
    doc: QTextDocument,
    blocks: list[dict[str, Any]],
    image_loader: ImageLoader,
    max_width: int,
    dpr: float = 1.0,
) -> None:
    """문서를 blocks 내용으로 교체한다. 되돌리기 스택과 수정 플래그도 초기화한다."""
    doc.clear()
    cursor = QTextCursor(doc)
    cursor.beginEditBlock()

    first = True
    for raw in blocks:
        block = normalize_block(raw)
        if not first:
            cursor.insertBlock()
        first = False

        block_type = block.get("type", TEXT)
        # setBlockFormat이 리스트 연결(objectIndex)을 지우므로 반드시 createList보다 먼저.
        cursor.setBlockFormat(fmt.block_format(
            block_type,
            bool(block.get("checked", False)),
            image=has_image(block),
            align=block.get("align", fmt.LEFT),
            indent=fmt.clamp_indent(block.get("indent")),
        ))
        if block_type in fmt.LIST_TYPES:
            cursor.createList(fmt.list_format())

        for run in block.get("runs", []):
            name = run.get("image")
            if name:
                insert_image_run(cursor, name, image_loader(name), max_width, dpr)
                continue
            text = run.get("text", "")
            if text:
                cursor.insertText(text, fmt.char_format(**fmt.flags_to_kwargs(run)))

    cursor.endEditBlock()
    doc.clearUndoRedoStacks()
    doc.setModified(False)
