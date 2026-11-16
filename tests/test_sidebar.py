"""최근 노트 목록이 제목을 잘라 먹지 않는지 검증.

기본 델리게이트는 항목 높이를 실제 그릴 폭과 무관하게 정해서, 목록을 그리는
도중 스크롤바가 생기면 그 전에 들어간 항목만 제목이 '...' 로 잘렸다. 같은
목록 안에서 어떤 노트는 두 줄, 어떤 노트는 한 줄로 보이던 문제다.

    .venv\\Scripts\\python.exe -m tests.test_sidebar
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows"     # 글꼴이 있어야 폭을 제대로 잰다

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem  # noqa: E402

from notememo import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="notememo-sidebar-"))
config.DATA_DIR = _TMP
config.NOTES_DIR = _TMP / "notes"
config.IMAGES_DIR = _TMP / "images"
config.ATTACHMENTS_DIR = _TMP / "attachments"

from notememo import sidebar as sb  # noqa: E402
from notememo import storage  # noqa: E402
from notememo.main_window import MainWindow  # noqa: E402

failures: list[str] = []

BODY = [{"type": "text", "runs": [{"text": "본문"}]}]

# 사용자가 신고한 두 제목. 길이는 둘 다 33자인데 한쪽만 잘렸다.
T_SHORT_WIDE = "JS 예외처리(try catch , throw) /비동기처리"
T_WRAPS = "JS 변수,자료형 / 비교연산자,논리연산자 / 조건문,반복문"


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


def item_option(view, item):
    option = QStyleOptionViewItem()
    view.initViewItemOption(option)
    index = view.indexFromItem(item)
    option.index = index
    return view.itemDelegate()._prepared(option, index), index


def rendered_title(view, item) -> str:
    """델리게이트가 실제로 그리는 제목 글자들을 이어 붙인다."""
    delegate = view.itemDelegate()
    option, _ = item_option(view, item)
    lines = delegate._title_lines(item.text(), option, delegate._wrap_width(option))
    return "".join(lines)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    # 스크롤바가 생길 만큼 노트를 채운다. 사용자 환경(29개)과 같은 조건.
    storage.save_note(_dt.date(2026, 11, 13), storage.Note(T_SHORT_WIDE, BODY, []))
    storage.save_note(_dt.date(2026, 11, 9), storage.Note(T_WRAPS, BODY, []))
    for day in range(1, 28):
        storage.save_note(_dt.date(2026, 10, day),
                          storage.Note(f"10월 {day}일 노트", BODY, []))

    win = MainWindow()
    win.resize(900, 620)
    win.show()
    app.processEvents()
    win.sidebar.refresh(_dt.date(2026, 11, 13))
    app.processEvents()

    view = win.sidebar.note_list
    check(view.verticalScrollBar().isVisible(),
          "스크롤바가 없어 원래 버그 조건이 재현되지 않는다 (테스트가 무의미해짐)")

    # --- 어떤 제목도 잘리면 안 된다 ------------------------------------
    for row in range(view.count()):
        item = view.item(row)
        shown = rendered_title(view, item)
        check(shown == item.text(),
              f"제목이 잘림: {item.text()!r} -> {shown!r}")

    # --- 날짜도 함께 보여야 한다 ---------------------------------------
    first = view.item(0)
    check(first.data(sb.DATE_ROLE), "항목에 날짜 문자열이 없다")
    check(first.text() == T_SHORT_WIDE, f"첫 항목 제목이 다름: {first.text()!r}")

    # --- 높이가 실제 줄 수를 따라가야 한다 ------------------------------
    delegate = view.itemDelegate()
    for row in range(view.count()):
        item = view.item(row)
        option, index = item_option(view, item)
        lines = delegate._title_lines(item.text(), option,
                                      delegate._wrap_width(option))
        expected = delegate.sizeHint(option, index).height()
        actual = view.visualItemRect(item).height()
        check(actual == expected,
              f"{item.text()!r}: 실제 높이 {actual} != 계산 높이 {expected} "
              f"(제목 {len(lines)}줄)")

    # --- 접는 폭은 실제로 그릴 폭을 넘으면 안 된다 ----------------------
    # 이 불변식이 깨지면(예전처럼 넓은 폭으로 계산해 두고 좁게 그리면) 넘치는
    # 글자가 다음 줄로 가지 못하고 '...' 로 잘려 나간다. 버그의 핵심이다.
    for row in range(view.count()):
        item = view.item(row)
        option, _ = item_option(view, item)
        # 그릴 수 있는 폭의 진짜 기준은 뷰포트다. 델리게이트가 계산한 값에서
        # 끌어오면 둘이 같이 움직여 버려서 검사가 되지 않는다.
        paint_width = view.viewport().width() - 2 * delegate.PAD_X
        check(delegate._wrap_width(option) <= paint_width,
              f"{item.text()!r}: 접는 폭 {delegate._wrap_width(option)} 이 "
              f"실제로 그릴 폭 {paint_width} 보다 넓다")

    # --- 폭이 바뀌면 높이를 다시 계산해야 한다 --------------------------
    # (예전에는 한 번 정한 높이가 폭을 따라가지 않아 글자가 잘렸다)
    wide_heights = {}
    for row in range(view.count()):
        item = view.item(row)
        wide_heights[item.text()] = view.visualItemRect(item).height()

    # 실제 사이드바 폭(262)에서는 줄 수가 안 변하는 구간이 넓다. 확실히 한 줄이
    # 더 필요해지는 폭까지 좁혀서, 높이가 폭을 따라가는지 본다.
    win.sidebar.setFixedWidth(130)
    app.processEvents()
    win.sidebar.refresh(_dt.date(2026, 11, 13))
    app.processEvents()

    changed = 0
    for row in range(view.count()):
        item = view.item(row)
        option, index = item_option(view, item)
        expected = delegate.sizeHint(option, index).height()
        actual = view.visualItemRect(item).height()
        check(actual == expected,
              f"좁힌 뒤 {item.text()!r}: 실제 높이 {actual} != 계산 높이 {expected}")
        if actual != wide_heights.get(item.text()):
            changed += 1
    check(changed > 0,
          "사이드바를 좁혔는데 항목 높이가 하나도 안 변했다 (폭을 안 따라간다)")

    if failures:
        print("FAIL")
        for line in failures:
            print("  -", line)
        return 1
    print(f"OK - 제목이 잘리지 않고 폭을 따라간다 (항목 {view.count()}개)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
