"""구분선 블록에서 Enter 를 눌렀을 때의 동작 검증.

구분선은 '빈 블록 + 블록 서식' 이라, Qt 기본 동작에 맡기면 블록을 쪼개며 서식까지
복제해 구분선이 하나 더 생기고(복제), 한 번 더 누르면 서식이 지워져 사라진다(소실).
두 증상이 다시 나오지 않는지 본다.

    .venv\\Scripts\\python.exe -m tests.test_divider
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from notememo import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="notememo-divider-"))
config.DATA_DIR = _TMP
config.NOTES_DIR = _TMP / "notes"
config.IMAGES_DIR = _TMP / "images"
config.ATTACHMENTS_DIR = _TMP / "attachments"

from notememo import formatting as fmt  # noqa: E402

from notememo.main_window import MainWindow  # noqa: E402

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


def press_enter(editor, shift: bool = False) -> None:
    mod = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, mod, "\r"))


def dividers(editor) -> list:
    """실제로 선이 그려지는 블록들. 화면에 보이는 구분선의 수와 같다."""
    doc = editor.document()
    found = []
    for i in range(doc.blockCount()):
        block = doc.findBlockByNumber(i)
        if fmt.read_block_type(block)[0] == fmt.DIVIDER and not block.text():
            found.append(block)
    return found


def fresh_note(editor, style: str = "double"):
    """'ABC' 한 줄 + 구분선 + 빈 본문 줄 을 만들고 커서를 구분선 맨 앞에 둔다."""
    editor.clear()
    cursor = editor.textCursor()
    cursor.setBlockFormat(fmt.block_format(fmt.TEXT))
    cursor.insertText("ABC")
    editor.setTextCursor(cursor)
    fmt.insert_divider(editor, style)
    block = dividers(editor)[0]
    moved = QTextCursor(editor.document())
    moved.setPosition(block.position())
    editor.setTextCursor(moved)
    return block


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    editor = win.editor

    # --- Enter 를 여러 번 눌러도 구분선은 늘 하나 ----------------------
    fresh_note(editor)
    check(len(dividers(editor)) == 1, "준비 단계부터 구분선이 하나가 아님")
    for n in range(1, 6):
        press_enter(editor)
        count = len(dividers(editor))
        check(count == 1, f"Enter {n}회 후 구분선이 {count}개 (1개여야 한다)")

    # 빈 줄은 구분선 '위' 에 쌓이고, 구분선은 계속 마지막 본문 줄보다 앞에 있다
    doc = editor.document()
    types = [fmt.read_block_type(doc.findBlockByNumber(i))[0] for i in range(doc.blockCount())]
    check(types.count(fmt.DIVIDER) == 1, f"문서에 구분선 블록이 하나가 아님: {types}")
    check(types[0] == fmt.TEXT and doc.findBlockByNumber(0).text() == "ABC",
          "구분선 위의 원래 본문이 사라짐")
    check(types.index(fmt.DIVIDER) == len(types) - 2,
          f"빈 줄이 구분선 위에 쌓이지 않음: {types}")

    # 커서는 새로 생긴 빈 줄에 있어야 바로 타이핑할 수 있다
    cursor_block = editor.textCursor().block()
    check(fmt.read_block_type(cursor_block)[0] == fmt.TEXT,
          "Enter 후 커서가 아직 구분선 블록에 있음")
    check(cursor_block.blockNumber() < types.index(fmt.DIVIDER),
          "커서가 구분선 위의 빈 줄이 아님")

    # --- 스타일이 보존되는가 ------------------------------------------
    for style in ("dashed", "solid", "bold", "double"):
        fresh_note(editor, style)
        press_enter(editor)
        found = dividers(editor)
        check(len(found) == 1, f"[{style}] Enter 후 구분선이 {len(found)}개")
        if found:
            check(fmt.read_divider_style(found[0]) == style,
                  f"[{style}] Enter 후 스타일이 {fmt.read_divider_style(found[0])} 로 바뀜")

    # --- Shift+Enter 도 구분선을 망가뜨리면 안 된다 --------------------
    fresh_note(editor)
    press_enter(editor, shift=True)
    found = dividers(editor)
    check(len(found) == 1, f"Shift+Enter 후 구분선이 {len(found)}개")
    doc = editor.document()
    check(not any(" " in doc.findBlockByNumber(i).text() for i in range(doc.blockCount())),
          "Shift+Enter 가 구분선 블록에 줄바꿈 문자를 넣음")

    # --- Ctrl+Z 로 원래대로 돌아오는가 --------------------------------
    fresh_note(editor)
    before = doc.blockCount()
    press_enter(editor)
    editor.undo()
    check(editor.document().blockCount() == before,
          f"되돌리기 후 블록 수가 {editor.document().blockCount()} (원래 {before})")
    check(len(dividers(editor)) == 1, "되돌리기 후 구분선이 하나가 아님")

    # --- 저장하고 다시 열어도 그대로인가 ------------------------------
    fresh_note(editor)
    press_enter(editor)
    press_enter(editor)
    blocks = editor.blocks()
    check(sum(1 for b in blocks if b.get("type") == fmt.DIVIDER) == 1,
          f"저장된 블록에 구분선이 하나가 아님: {[b.get('type') for b in blocks]}")
    editor.load_blocks(_dt.date(2026, 11, 15), blocks)
    check(len(dividers(editor)) == 1,
          f"다시 열었을 때 구분선이 {len(dividers(editor))}개")
    check(fmt.read_divider_style(dividers(editor)[0]) == "double"
          if dividers(editor) else False,
          "다시 열었을 때 이중선 스타일이 풀림")

    # --- 구분선이 아닌 줄에서는 평소대로 동작해야 한다 -----------------
    editor.clear()
    cursor = editor.textCursor()
    cursor.insertText("가나다")
    editor.setTextCursor(cursor)
    before = editor.document().blockCount()
    press_enter(editor)
    check(editor.document().blockCount() == before + 1,
          "보통 줄에서 Enter 가 줄을 늘리지 않음")

    # --- Enter 는 매번 한 줄씩 늘어나야 한다 (먹히지 않는 Enter 금지) ---
    # Qt 는 '빈 블록 + 기본값 아닌 블록 서식' 에서 Enter 를 서식 지우기로 써버린다.
    # 저장 후 다시 연 노트는 모든 블록이 명시적 서식을 갖는다.
    editor.clear()
    cursor = editor.textCursor()
    cursor.insertText("첫 줄")
    cursor.insertBlock()
    cursor.insertBlock()
    cursor.insertText("셋째 줄")
    editor.setTextCursor(cursor)
    reopened = editor.blocks()
    editor.load_blocks(_dt.date(2026, 11, 15), reopened)
    doc = editor.document()
    moved = QTextCursor(doc)
    moved.setPosition(doc.findBlockByNumber(1).position())   # 가운데 빈 줄
    editor.setTextCursor(moved)
    count = doc.blockCount()
    for n in range(1, 4):
        press_enter(editor)
        count += 1
        check(doc.blockCount() == count,
              f"다시 연 노트의 빈 줄에서 Enter {n}회 후 블록 "
              f"{doc.blockCount()}개 (기대 {count}개). Enter 가 먹히지 않는다")

    # 빈 구분선 위 줄에서도 Enter 가 매번 먹혀야 한다
    fresh_note(editor)
    press_enter(editor)                      # 구분선 위에 빈 줄 생성, 커서도 그리로
    doc = editor.document()
    count = doc.blockCount()
    for n in range(1, 4):
        press_enter(editor)
        count += 1
        check(doc.blockCount() == count,
              f"구분선 위 빈 줄에서 Enter {n}회 후 블록 "
              f"{doc.blockCount()}개 (기대 {count}개)")
    check(len(dividers(editor)) == 1, "빈 줄 Enter 반복 후 구분선이 하나가 아님")

    if failures:
        print("FAIL")
        for line in failures:
            print("  -", line)
        return 1
    print("OK - 구분선이 복제되지도, 사라지지도 않는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
