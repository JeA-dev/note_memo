"""blocks -> QTextDocument -> blocks 왕복 동일성 검증.

GUI 없이 오프스크린으로 돈다:
    .venv\\Scripts\\python.exe -m tests.test_serializer
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication, QImage, QTextDocument  # noqa: E402

from notememo import formatting  # noqa: E402
from notememo import serializer  # noqa: E402
from notememo import theme  # noqa: E402
from notememo.theme import HIGHLIGHT_COLORS  # noqa: E402

MAX_WIDTH = 600

SAMPLE = [
    {"type": "text", "runs": [{"text": "오늘 배포 이슈", "sz": 18}]},
    {"type": "text", "runs": [
        {"text": "원인은 "},
        {"text": "캐시 무효화 누락", "b": True, "hl": HIGHLIGHT_COLORS[0]},
        {"text": "이었다."},
    ]},
    {"type": "text", "runs": []},                       # 빈 줄
    {"type": "text", "runs": [{"text": "할 일", "sz": 14}]},
    {"type": "todo", "checked": False, "runs": [{"text": "롤백 스크립트 점검"}]},
    {"type": "todo", "checked": True, "runs": [{"text": "핫픽스 배포", "s": True}]},
    {"type": "bullet", "runs": [{"text": "재발 방지 문서화", "i": True}]},
    {"type": "bullet", "runs": [{"text": "밑줄 항목", "u": True}]},
    {"type": "text", "align": "center", "runs": [{"image": "img_20260828-143022-a1b2.png"}]},
    {"type": "text", "runs": [
        {"text": "스샷 뒤 본문 "},
        {"text": "민트", "hl": HIGHLIGHT_COLORS[1]},
        {"text": " 그리고 "},
        {"text": "핑크 볼드", "b": True, "hl": HIGHLIGHT_COLORS[2]},
    ]},
    {"type": "text", "runs": [{"text": "모든 플래그", "b": True, "i": True, "u": True, "s": True}]},
    {"type": "text", "align": "center", "runs": [{"text": "가운데 정렬 문단"}]},
    {"type": "text", "align": "right", "runs": [{"text": "오른쪽 정렬 문단"}]},
    {"type": "text", "align": "justify", "runs": [{"text": "양쪽 정렬 문단"}]},
    {"type": "text", "align": "center", "runs": [{"text": "가운데 큰 글자", "sz": 22}]},
    {"type": "todo", "checked": False, "align": "right", "runs": [{"text": "오른쪽 체크박스"}]},
    {"type": "text", "indent": 1, "runs": [{"text": "한 단계 들여쓴 줄"}]},
    {"type": "text", "indent": 3, "align": "center", "runs": [{"text": "세 단계 + 가운데"}]},
    {"type": "bullet", "indent": 2, "runs": [{"text": "들여쓴 목록 항목"}]},
    {"type": "text", "indent": 2, "runs": [{"image": "img_20260828-143022-a1b2.png"}]},
    # 한 문단에 스샷 둘을 나란히 (저장할 때마다 줄이 나뉘던 회귀 경로)
    {"type": "text", "runs": [
        {"image": "img_20260828-143022-a1b2.png"},
        {"image": "img_20260828-143022-a1b2.png"},
    ]},
    # 글자와 이미지가 섞인 문단 - 등장 순서가 지켜져야 한다
    {"type": "text", "runs": [
        {"text": "앞글 "},
        {"image": "img_20260828-143022-a1b2.png"},
        {"text": " 뒷글", "b": True},
    ]},
]


def _image_loader(_name: str) -> QImage:
    image = QImage(1200, 700, QImage.Format.Format_RGB32)
    image.fill(0xFFCCCCCC)
    return image


def round_trip(blocks):
    doc = QTextDocument()
    serializer.blocks_to_document(doc, blocks, _image_loader, MAX_WIDTH)
    return doc, serializer.document_to_blocks(doc)


def main() -> int:
    QGuiApplication(sys.argv)
    failures: list[str] = []

    doc, once = round_trip(SAMPLE)
    expected = serializer._trim_trailing_empty([dict(b) for b in SAMPLE])
    if once != expected:
        failures.append("1차 왕복 불일치")
        for i, (got, want) in enumerate(zip(once, expected)):
            if got != want:
                failures.append(f"  [{i}] 기대={want}\n       실제={got}")
        if len(once) != len(expected):
            failures.append(f"  블록 수: 기대={len(expected)} 실제={len(once)}")

    _, twice = round_trip(once)
    if twice != once:
        failures.append("2차 왕복이 불안정 (멱등하지 않음)")

    # 이미지 표시 폭이 본문 폭을 넘지 않아야 가로 스크롤이 안 생긴다.
    block = doc.begin()
    widths = []
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            char_fmt = it.fragment().charFormat()
            if char_fmt.isImageFormat():
                widths.append(char_fmt.toImageFormat().width())
            it += 1
        block = block.next()
    if not widths:
        failures.append("이미지 프래그먼트를 찾지 못함")
    elif max(widths) > MAX_WIDTH:
        failures.append(f"이미지 표시 폭이 본문 폭 초과: {max(widths)} > {MAX_WIDTH}")

    # 빈 문서는 빈 목록이어야 저장 시 파일이 생기지 않는다.
    if serializer.document_to_blocks(QTextDocument()):
        failures.append("빈 문서가 빈 목록으로 직렬화되지 않음")

    # 큰 글자 크기만 지정하고 아무것도 안 쓴 문단은 파일이 생기지 않아야 한다.
    _, only_sized = round_trip([{"type": "text", "runs": [{"text": "", "sz": 22}]}])
    if only_sized:
        failures.append(f"빈 문단이 비지 않음: {only_sized}")

    # 지원하는 모든 글자 크기가 왕복에서 보존되는지 확인.
    for point in theme.SIZES:
        run = {"text": f"{point}pt"}
        if point != theme.BODY_PT:
            run["sz"] = point
        source = [{"type": "text", "runs": [run]}]
        _, got = round_trip(source)
        if got != source:
            failures.append(f"글자 크기 {point} 왕복 실패: {got}")

    # 기본 크기에는 sz 키가 붙지 않아야 한다.
    _, default_size = round_trip([{"type": "text", "runs": [{"text": "기본"}]}])
    if "sz" in default_size[0]["runs"][0]:
        failures.append(f"기본 크기에 sz 키가 붙음: {default_size[0]}")

    # 반대로 비어 있어도 사용자가 만든 체크박스는 남아야 한다.
    _, only_todo = round_trip([{"type": "todo", "checked": False, "runs": []}])
    if not only_todo:
        failures.append("빈 체크박스가 사라짐")

    # 기본값(왼쪽/들여쓰기 0)에는 키가 붙지 않아야 파일이 지저분해지지 않는다.
    _, plain = round_trip([{"type": "text", "runs": [{"text": "왼쪽"}]}])
    if "align" in plain[0]:
        failures.append(f"왼쪽 정렬에 align 키가 붙음: {plain[0]}")
    if "indent" in plain[0]:
        failures.append(f"들여쓰기 0에 indent 키가 붙음: {plain[0]}")

    # 들여쓰기 단계가 모두 보존되고, 상한을 넘는 값은 잘린다.
    for level in range(1, 6):
        source = [{"type": "text", "indent": level, "runs": [{"text": f"{level}단계"}]}]
        _, got = round_trip(source)
        if got != source:
            failures.append(f"들여쓰기 {level} 왕복 실패: {got}")
    _, huge = round_trip([{"type": "text", "indent": 999, "runs": [{"text": "과도"}]}])
    if huge[0].get("indent") != formatting.MAX_INDENT:
        failures.append(f"들여쓰기 상한이 안 걸림: {huge[0]}")

    # 옛 형식의 독립 이미지 블록은 이미지 run 하나를 가진 문단으로 읽힌다.
    legacy = {"type": "image", "align": "center", "indent": 2,
              "file": "img_20260828-143022-a1b2.png"}
    _, migrated = round_trip([legacy])
    if migrated != [{"type": "text", "align": "center", "indent": 2,
                     "runs": [{"image": legacy["file"]}]}]:
        failures.append(f"옛 이미지 블록 변환 실패: {migrated}")

    # 이미지만 있는 마지막 문단은 잘려나가면 안 된다.
    _, image_tail = round_trip([
        {"type": "text", "runs": [{"text": "본문"}]},
        {"type": "text", "runs": [{"image": "img_20260828-143022-a1b2.png"}]},
    ])
    if len(image_tail) != 2:
        failures.append(f"이미지만 있는 마지막 문단이 사라짐: {image_tail}")

    # 네 가지 정렬이 모두 왕복에서 보존되는지 개별 확인.
    for name in ("left", "center", "right", "justify"):
        source = [{"type": "text", "runs": [{"text": name}]}]
        if name != "left":
            source[0]["align"] = name
        _, got = round_trip(source)
        if got != source:
            failures.append(f"정렬 '{name}' 왕복 실패: {got}")

    if failures:
        print("FAIL")
        for line in failures:
            print(" ", line)
        return 1
    print(f"OK - {len(once)}개 블록 왕복 일치, 이미지 폭 {max(widths):.0f}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
