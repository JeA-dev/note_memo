"""제목 안의 `[태그]` 를 찾아 색을 정한다.

`[ JS ] 예외처리` 처럼 제목에 대괄호로 과목을 적는 습관에 맞춰 그 부분만 자동으로
색을 입힌다. 사용자가 고르거나 노트에 저장하는 값은 없다.

색은 **배정**한다. 예전에는 태그 이름을 해시해서 색을 골랐는데, 해시는 서로 다른
태그가 같은 색을 받는 것을 막지 못한다(실제로 태그 12개가 색 6개에 몰렸다).
그래서 쓰고 있는 태그 목록을 보고 서로 겹치지 않게 하나씩 나눠 준 뒤,
그 배정을 `tag_colors.json` 에 적어 둔다. 한 번 정해진 색은 바뀌지 않는다.
"""

from __future__ import annotations

import json
import re
import zlib
from typing import Iterable

from . import config

# 종이색(#FBF8F3)·사이드바(#F2EDE4)·선택된 행(#EFE3D0) 어디에서도 읽히도록
# 가장 어두운 배경 기준 명암비 4.5 이상, 서로 CIE76 색차 25 이상인 색을 골랐다.
# (tools 없이 손으로 고르면 비슷한 색이 섞여 들어가므로 계산해서 뽑은 값이다.)
TAG_COLORS = [
    "#1B1BA7",   # 파랑
    "#137213",   # 초록
    "#A71B2E",   # 빨강
    "#1E698F",   # 청록
    "#691C5E",   # 자주
    "#7E5D1B",   # 황토
    "#255F48",   # 짙은 초록
    "#184295",   # 남색
    "#A71BA7",   # 보라
    "#5F2925",   # 밤색
    "#A71B5C",   # 자홍
    "#A74A1B",   # 주황
    "#4D6321",   # 올리브
    "#25355F",   # 쪽빛
]

COLORS_FILE = "tag_colors.json"

# 대괄호 한 덩어리. 안에 또 대괄호가 오는 경우는 태그로 보지 않는다.
# 맨 앞뿐 아니라 제목 중간의 태그도 찾는다
# (`[ JS ] 이벤트 / [로컬AI] LM Studio 설치` 처럼 두 과목을 한 노트에 적는 경우).
_TAG_RE = re.compile(r"\[([^\[\]]{1,24})\]")

_assigned: dict[str, str] = {}


def normalize(name: str) -> str:
    """`[ JS ]` 와 `[js]` 를 같은 태그로 본다."""
    return re.sub(r"\s+", "", name).casefold()


def tag_spans(title: str) -> list[tuple[int, int, str]]:
    """제목 안 모든 태그의 (시작, 끝, 정규화된 이름) 목록. 대괄호를 포함한다."""
    spans = []
    for match in _TAG_RE.finditer(title or ""):
        name = normalize(match.group(1))
        if name:
            spans.append((match.start(), match.end(), name))
    return spans


# --- 색 배정 -------------------------------------------------------

def _path():
    return config.DATA_DIR / COLORS_FILE


def load() -> None:
    """저장해 둔 배정을 읽는다. 파일이 없거나 깨졌으면 빈 상태로 시작한다."""
    _assigned.clear()
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(data, dict):
        for name, color in data.items():
            if isinstance(name, str) and color in TAG_COLORS:
                _assigned[name] = color


def save() -> None:
    try:
        config.ensure_dirs()
        _path().write_text(
            json.dumps(_assigned, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass            # 색 배정을 못 적어도 앱이 멈출 일은 아니다


def _next_color() -> str:
    """아직 안 쓴 색을 준다. 다 썼으면 가장 적게 쓰인 색을 다시 쓴다."""
    used = list(_assigned.values())
    counts = {color: used.count(color) for color in TAG_COLORS}
    return min(TAG_COLORS, key=lambda c: (counts[c], TAG_COLORS.index(c)))


def fallback_color(name: str) -> str:
    """아직 배정되지 않은 태그에 임시로 보여줄 색.

    제목을 타이핑하는 중에는 `[파]` 처럼 완성되지 않은 태그가 잠깐 잡힌다.
    그런 것까지 배정해 두면 색이 낭비되므로, 저장되기 전에는 계산한 색만 보여준다.
    파이썬 hash() 는 실행마다 값이 달라지므로 쓰지 않는다.
    """
    return TAG_COLORS[zlib.crc32(name.encode("utf-8")) % len(TAG_COLORS)]


def prime(titles: Iterable[str]) -> bool:
    """저장된 노트 제목들을 훑어 태그에 색을 배정한다. 바뀌었으면 True.

    오래된 노트부터 순서대로 넘겨야 색이 안정적이다. 새 태그는 뒤에 붙으므로
    이미 쓰던 태그의 색은 그대로 남는다.
    """
    changed = False
    for title in titles:
        for _, _, name in tag_spans(title):
            if name not in _assigned:
                _assigned[name] = _next_color()
                changed = True
    if changed:
        save()
    return changed


def color_of(name: str) -> str:
    """태그 이름에 대응하는 색."""
    return _assigned.get(name) or fallback_color(name)


def title_color(title: str) -> str | None:
    """제목 전체에 입힐 색. 태그가 여럿이면 맨 앞 것을 따른다. 없으면 None."""
    spans = tag_spans(title)
    return color_of(spans[0][2]) if spans else None


def assignments() -> dict[str, str]:
    """지금 배정 상태 (검사·디버그용)."""
    return dict(_assigned)
