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

    # --- 서로 다른 태그는 서로 다른 색 (이 테스트의 핵심) ----------------
    # 예전에는 이름을 해시해서 색을 골라, 태그 12개가 색 6개에 몰렸다.
    names = ["js", "파이썬", "로컬ai", "git,github", "리눅스", "프롬프트",
             "html/css", "크롤링", "영상편집자동화", "안티그래비티", "제미나이", "1차프로젝트"]
    tags.prime(f"[{n}] 노트" for n in names)
    colors = [tags.color_of(n) for n in names]
    check(len(set(colors)) == len(names),
          f"태그 {len(names)}개가 색 {len(set(colors))}개를 나눠 씀 (전부 달라야 한다)")
    for name, color in zip(names, colors):
        check(color in tags.TAG_COLORS, f"{name}: 팔레트에 없는 색 {color}")

    # 팔레트를 다 쓰면 가장 적게 쓰인 색부터 다시 쓴다 (겹쳐도 고르게)
    extra = [f"여분{i}" for i in range(len(tags.TAG_COLORS) + 3)]
    tags.prime(f"[{n}] 노트" for n in extra)
    counts = {}
    for n in list(tags.assignments()):
        counts[tags.color_of(n)] = counts.get(tags.color_of(n), 0) + 1
    check(max(counts.values()) - min(counts.values()) <= 1,
          f"색 쏠림: 가장 많이 {max(counts.values())}개 / 적게 {min(counts.values())}개")

    # --- 같은 태그는 같은 색, 표기가 달라도 같은 색 ----------------------
    same = {tags.title_color(t) for t in ("[ JS ] 복습", "[JS]복습", "[js] 복습", "[ js ] 복습")}
    check(len(same) == 1, f"표기만 다른 같은 태그인데 색이 갈린다: {same}")
    check(tags.title_color("태그 없는 제목") is None, "태그가 없는데 색이 나왔다")

    # --- 한 번 정해진 색은 바뀌지 않는다 ---------------------------------
    before = tags.assignments()
    tags.save()
    tags.load()
    check(tags.assignments() == before, "저장했다 읽으면 배정이 달라진다")
    tags.prime(["[새로운과목] 오늘", "[또다른것] 복습"])
    after = tags.assignments()
    check(all(after.get(k) == v for k, v in before.items()),
          "새 태그가 생기자 기존 태그 색이 바뀌었다")

    # --- 배정 전 임시 색은 실행을 다시 해도 같아야 한다 -------------------
    # 제목을 타이핑하는 중에는 아직 배정되지 않은 태그가 잠깐 잡힌다.
    # 파이썬 hash() 는 실행마다 값이 달라지므로 쓰면 안 된다.
    script = (
        "import sys; sys.path.insert(0, r'" + str(Path(__file__).resolve().parent.parent) + "');"
        "from notememo import tags;"
        "print(','.join(tags.fallback_color(n) for n in ['js','로컬ai','python','css']))"
    )
    runs = set()
    for _ in range(3):
        out = subprocess.run([sys.executable, "-c", script], capture_output=True,
                             text=True, encoding="utf-8")
        runs.add(out.stdout.strip())
    check(len(runs) == 1,
          f"파이썬을 새로 띄울 때마다 임시 색이 달라진다 (hash() 를 쓰고 있지 않은지): {runs}")

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
    check(tags.color_of("로컬ai").lower() in sheet.lower(),
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
                  == tags.color_of(name).lower(),
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


if __name__ == "__main__":
    raise SystemExit(main())
