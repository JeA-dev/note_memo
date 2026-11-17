"""붙여넣기가 글자를 이미지로 만들어 버리지 않는지 검증.

커서가 이미지 바로 뒤에 있으면 currentCharFormat() 은 그 이미지의 서식이다.
그 서식으로 글자를 넣으면 Qt 가 글자마다 이미지를 그려서, 넣은 글자는 사라지고
앞의 스샷이 글자 수만큼 늘어난다. 저장할 때도 이미지 run 으로 적히므로 글자가
영영 사라진다. 데이터가 날아가는 버그라 경로마다 모두 확인한다.

    .venv\\Scripts\\python.exe -m tests.test_paste
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QMimeData, Qt  # noqa: E402
from PySide6.QtGui import QImage, QKeyEvent, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from notememo import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="notememo-paste-"))
config.DATA_DIR = _TMP
config.NOTES_DIR = _TMP / "notes"
config.IMAGES_DIR = _TMP / "images"
config.ATTACHMENTS_DIR = _TMP / "attachments"

from notememo.main_window import MainWindow  # noqa: E402

failures: list[str] = []

TEXT = "콜백의 첫 매개변수 e에 무슨 일인지 담겨 옵니다"


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


def shot(color: int, size: tuple[int, int] = (300, 150)) -> QImage:
    image = QImage(size[0], size[1], QImage.Format.Format_RGB32)
    image.fill(color)
    return image


def counts(editor) -> tuple[int, str]:
    """저장될 내용 기준으로 (이미지 run 수, 글자 전체)."""
    blocks = editor.blocks()
    images = sum(1 for b in blocks for r in b.get("runs", []) if r.get("image"))
    text = "".join(r.get("text", "")
                   for b in blocks for r in b.get("runs", []) if r.get("text"))
    return images, text


def put_cursor_after_image(editor) -> bool:
    """커서를 이미지 바로 뒤에 둔다. 사용자가 스샷 뒤를 클릭한 상황."""
    doc = editor.document()
    position = None
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            if fragment.charFormat().isImageFormat():
                position = fragment.position() + fragment.length()
            it += 1
        block = block.next()
    if position is None:
        return False
    cursor = QTextCursor(doc)
    cursor.setPosition(position)
    editor.setTextCursor(cursor)
    return True


def web_clipboard(text: str) -> QMimeData:
    """웹페이지에서 복사한 모양. text/html 은 있지만 Qt 리치 포맷은 없다."""
    data = QMimeData()
    data.setText(text)
    data.setHtml(f"<p>{text}</p>")
    return data


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    editor = win.editor

    # --- 웹페이지 복사 → 스샷 바로 뒤에 붙여넣기 (사용자가 신고한 경로) ---
    editor.clear()
    editor.insert_image(shot(0xFF3366AA))
    check(put_cursor_after_image(editor), "이미지를 찾지 못했다")
    editor.insertFromMimeData(web_clipboard(TEXT))
    images, text = counts(editor)
    check(images == 1, f"웹 복사 붙여넣기 후 이미지가 {images}개로 늘었다 (1개여야 한다)")
    check(text == TEXT, f"붙여넣은 글자가 사라졌다: {text!r}")

    # --- Ctrl+Shift+V 평문 붙여넣기도 같은 경로를 지난다 ----------------
    editor.clear()
    editor.insert_image(shot(0xFF33AA66))
    put_cursor_after_image(editor)
    QApplication.clipboard().setMimeData(web_clipboard(TEXT))
    editor.paste_plain()
    # 클립보드에 넘긴 QMimeData 를 비우지 않으면 Qt 가 종료할 때 죽는다.
    QApplication.clipboard().clear()
    images, text = counts(editor)
    check(images == 1, f"평문 붙여넣기 후 이미지가 {images}개로 늘었다")
    check(text == TEXT, f"평문 붙여넣기 글자가 사라졌다: {text!r}")

    # --- 사용자 시나리오 전체: 스샷 → 글자 → 다른 스샷 ------------------
    editor.clear()
    editor.insert_image(shot(0xFF3366AA))
    put_cursor_after_image(editor)
    editor.insertFromMimeData(web_clipboard(TEXT))
    editor.insert_image(shot(0xFFAA3366, (320, 160)))
    images, text = counts(editor)
    check(images == 2, f"스샷 2장이어야 하는데 {images}개다")
    check(text == TEXT, f"가운데 글자가 사라졌다: {text!r}")

    names = {r["image"] for b in editor.blocks()
             for r in b.get("runs", []) if r.get("image")}
    check(len(names) == 2, f"서로 다른 스샷 2장이어야 하는데 {len(names)}종이다: {names}")

    # 저장하고 다시 열어도 그대로여야 한다
    blocks = editor.blocks()
    editor.load_blocks(editor.date, blocks)
    images, text = counts(editor)
    check(images == 2, f"다시 열었을 때 이미지가 {images}개")
    check(text == TEXT, f"다시 열었을 때 글자가 사라졌다: {text!r}")

    # --- 타이핑은 원래 안전했다. 고치면서 깨지지 않았는지 확인 ----------
    editor.clear()
    editor.insert_image(shot(0xFF888888))
    put_cursor_after_image(editor)
    for ch in "가나다":
        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A,
                                       Qt.KeyboardModifier.NoModifier, ch))
    images, text = counts(editor)
    check(images == 1 and text == "가나다",
          f"이미지 뒤 타이핑이 깨졌다: 이미지 {images}개, 글자 {text!r}")

    # --- 이미지와 상관없는 자리에서는 서식이 유지돼야 한다 ---------------
    editor.clear()
    cursor = editor.textCursor()
    cursor.insertText("앞글자")
    editor.setTextCursor(cursor)
    editor.setCurrentCharFormat(__import__(
        "notememo.formatting", fromlist=["x"]).char_format(bold=True))
    editor.insertFromMimeData(web_clipboard("굵게"))
    runs = [r for b in editor.blocks() for r in b.get("runs", []) if r.get("text")]
    pasted = [r for r in runs if r.get("text") == "굵게"]
    check(bool(pasted) and pasted[0].get("b"),
          f"이미지와 무관한 자리인데 굵게 서식이 사라졌다: {runs}")

    if failures:
        print("FAIL")
        for line in failures:
            print("  -", line)
        return 1
    print("OK - 붙여넣은 글자가 이미지로 바뀌지 않는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
