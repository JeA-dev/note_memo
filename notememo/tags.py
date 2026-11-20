"""제목 맨 앞의 `[태그]` 를 찾아 색을 정한다.

`[ JS ] 예외처리` 처럼 제목 앞에 대괄호로 과목을 적는 습관에 맞춰, 그 부분만
자동으로 색을 입힌다. 고르거나 저장하는 값이 없으므로 노트 형식은 그대로다.

같은 태그는 언제나 같은 색이어야 하므로 파이썬 `hash()` 를 쓰면 안 된다.
문자열 해시에는 실행마다 바뀌는 소금이 들어가서 앱을 켤 때마다 색이 달라진다.
"""

from __future__ import annotations

import re
import zlib

# 종이색(#FBF8F3)과 사이드바(#F2EDE4) 위에서 모두 읽히는 색으로 고른다.
TAG_COLORS = [
    "#2F6FB5",   # 파랑
    "#2E7D52",   # 초록
    "#B45309",   # 주황
    "#7C3AED",   # 보라
    "#0F766E",   # 청록
    "#BE3455",   # 자홍
    "#3F51A8",   # 남색
    "#6B7A1F",   # 올리브
]

# 대괄호 한 덩어리. 안에 또 대괄호가 오는 경우는 태그로 보지 않는다.
# 맨 앞뿐 아니라 제목 중간의 태그도 찾는다
# (`[ JS ] 이벤트 / [로컬AI] LM Studio 설치` 처럼 두 과목을 한 노트에 적는 경우).
_TAG_RE = re.compile(r"\[([^\[\]]{1,24})\]")


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


def color_for(name: str) -> str:
    """태그 이름에 대응하는 색. 실행을 다시 해도 같은 색이 나온다."""
    index = zlib.crc32(name.encode("utf-8")) % len(TAG_COLORS)
    return TAG_COLORS[index]


def title_color(title: str) -> str | None:
    """제목 전체에 입힐 색. 태그가 여럿이면 맨 앞 것을 따른다. 없으면 None."""
    spans = tag_spans(title)
    return color_for(spans[0][2]) if spans else None
