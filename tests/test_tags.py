"""제목 앞 `[태그]` 자동 색칠 검증.

색은 저장하지 않고 태그 이름에서 계산한다. 그래서 '같은 태그는 언제나 같은 색'
이 깨지면 노트를 열 때마다 색이 달라진다. 파이썬 `hash()` 는 실행마다 소금이
바뀌므로 쓰면 안 되는데, 그 실수를 잡는 것이 이 테스트의 핵심이다.

    .venv\\Scripts\\python.exe -m tests.test_tags
"""

from __future__ import annotations

import datetime as _dt
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows"     # 글자 폭을 재야 한다

from PySide6.QtWidgets import QApplication, QStyleOptionViewItem  # noqa: E402

from notememo import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="notememo-tags-"))
config.DATA_DIR = _TMP
config.NOTES_DIR = _TMP / "notes"
config.IMAGES_DIR = _TMP / "images"
config.ATTACHMENTS_DIR = _TMP / "attachments"

from notememo import storage, tags, theme  # noqa: E402
from notememo.main_window import MainWindow  # noqa: E402

failures: list[str] = []

BODY = [{"type": "text", "runs": [{"text": "본문"}]}]


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


def main() -> int:
    # --- 태그 찾기 ------------------------------------------------------
    cases = {
        "[ JS ] 예외처리": [(0, 6, "js")],
        "[JS]붙여쓰기": [(0, 4, "js")],
        "[js] 소문자": [(0, 4, "js")],
        "[로컬AI] Ollama 이해하기": [(0, 6, "로컬ai")],
        "태그 없는 제목": [],
        "[] 빈 태그": [],
    }
    for title, expected in cases.items():
        got = tags.tag_spans(title)
        check(got == expected, f"{title!r}: 태그 {got} (기대 {expected})")

    # 제목 중간의 태그도 찾아야 한다 (한 노트에 과목 둘)
    two = tags.tag_spans("[ JS ] 이벤트 / [로컬AI] LM Studio 설치")
    check(len(two) == 2, f"태그 두 개를 못 찾음: {two}")
    if len(two) == 2:
        check(two[0][2] == "js" and two[1][2] == "로컬ai", f"태그 이름이 다름: {two}")
        check(tags.color_for(two[0][2]) != tags.color_for(two[1][2]),
              "서로 다른 태그인데 같은 색이다")

    # --- 같은 태그는 같은 색, 표기가 달라도 같은 색 ----------------------
    same = {tags.title_color(t) for t in ("[ JS ] 복습", "[JS]복습", "[js] 복습", "[ js ] 복습")}
    check(len(same) == 1, f"표기만 다른 같은 태그인데 색이 갈린다: {same}")
    check(tags.title_color("태그 없는 제목") is None, "태그가 없는데 색이 나왔다")
    for name in ("js", "로컬ai", "python", "css"):
        check(tags.color_for(name) in theme_palette(),
              f"{name}: 팔레트에 없는 색 {tags.color_for(name)}")

    # --- 실행을 다시 해도 같은 색이어야 한다 (hash() 소금 실수 잡기) -----
    script = (
        "import sys; sys.path.insert(0, r'" + str(Path(__file__).resolve().parent.parent) + "');"
        "from notememo import tags;"
        "print(','.join(tags.color_for(n) for n in ['js','로컬ai','python','css']))"
    )
    runs = set()
    for _ in range(3):
        out = subprocess.run([sys.executable, "-c", script], capture_output=True,
                             text=True, encoding="utf-8")
        runs.add(out.stdout.strip())
    check(len(runs) == 1,
          f"파이썬을 새로 띄울 때마다 색이 달라진다 (hash() 를 쓰고 있지 않은지): {runs}")

    # --- 목록과 헤더에 실제로 반영되는가 ---------------------------------
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(theme.stylesheet())
    storage.save_note(_dt.date(2026, 11, 20), storage.Note("[로컬AI] Ollama 이해하기", BODY, []))
    storage.save_note(_dt.date(2026, 11, 13), storage.Note("[ JS ] 예외처리", BODY, []))
    storage.save_note(_dt.date(2026, 11, 10), storage.Note("태그 없는 제목", BODY, []))

    win = MainWindow()
    win.resize(960, 700)
    win.show()
    app.processEvents()
    win.go_to(_dt.date(2026, 11, 20))
    app.processEvents()

    # 헤더: 제목 줄 전체가 태그 색
    sheet = win.header.title_input.styleSheet()
    check(tags.color_for("로컬ai").lower() in sheet.lower(),
          f"헤더 제목에 태그 색이 안 들어갔다: {sheet!r}")

    win.go_to(_dt.date(2026, 11, 10))
    app.processEvents()
    check(not win.header.title_input.styleSheet(),
          "태그 없는 노트인데 헤더에 색이 남아 있다")

    # 목록: 태그 구간에만 색 서식이 붙는가
    view = win.sidebar.note_list
    delegate = view.itemDelegate()
    for row in range(view.count()):
        item = view.item(row)
        formats = delegate._tag_formats(item.text())
        expected = tags.tag_spans(item.text())
        check(len(formats) == len(expected),
              f"{item.text()!r}: 색 구간 {len(formats)}개 (기대 {len(expected)}개)")
        for span, (start, end, name) in zip(formats, expected):
            check(span.start == start and span.length == end - start,
                  f"{item.text()!r}: 색 구간 위치가 다르다")
            check(span.format.foreground().color().name().lower()
                  == tags.color_for(name).lower(),
                  f"{item.text()!r}: 색이 다르다")

    # --- 태그를 굵게 해도 제목이 잘리면 안 된다 --------------------------
    for row in range(view.count()):
        item = view.item(row)
        option = QStyleOptionViewItem()
        view.initViewItemOption(option)
        index = view.indexFromItem(item)
        option.index = index
        option = delegate._prepared(option, index)
        shown = "".join(delegate._title_lines(item.text(), option,
                                              delegate._wrap_width(option)))
        check(shown == item.text(), f"제목이 잘림: {item.text()!r} -> {shown!r}")

    if failures:
        print("FAIL")
        for line in failures:
            print("  -", line)
        return 1
    print("OK - 태그 색이 안정적이고 목록·헤더에 반영된다")
    return 0


def theme_palette() -> set[str]:
    return set(tags.TAG_COLORS)


if __name__ == "__main__":
    raise SystemExit(main())
