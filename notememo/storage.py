"""노트 JSON 및 스크린샷 파일 입출력."""

from __future__ import annotations

import datetime as _dt
import json
import secrets
import shutil
from pathlib import Path
from typing import Any, NamedTuple

from . import config, theme

# 제목1/제목2 서식이 있던 시절의 크기. 옛 블록을 글자 크기 run 으로 옮길 때 쓴다.
_LEGACY_HEADING_PT = {1: 17, 2: 14}

_MAX_TITLE = 42


class Note(NamedTuple):
    """노트 한 장. 제목은 서식 없는 평문이다."""

    title: str
    blocks: list[dict[str, Any]]

    def is_empty(self) -> bool:
        return not self.title.strip() and not self.blocks


EMPTY = Note("", [])


# ── 노트 ────────────────────────────────────────────────────────────

# 목록과 검색이 모든 노트를 반복해서 읽으므로 mtime 기준으로 캐시한다.
_cache: dict[str, tuple[float, Note]] = {}


def _lift_leading_heading(blocks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """옛 형식 노트의 맨 앞 제목1 블록을 제목으로 끌어올린다.

    제목 칸이 생기기 전에는 본문 첫 줄에 제목1을 써서 제목을 대신했다.
    """
    if not blocks or blocks[0].get("type") != "heading" or blocks[0].get("level") != 1:
        return "", blocks
    title = "".join(run.get("text", "") for run in blocks[0].get("runs", [])).strip()
    if not title:
        return "", blocks
    return title, blocks[1:]


def _convert_headings(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """옛 제목1/제목2 블록을 일반 문단 + 글자 크기 run 으로 옮긴다.

    제목 서식이 없어진 뒤에도 예전 노트의 강조가 사라지지 않게 크기로 이어받는다.
    """
    converted = []
    for block in blocks:
        if block.get("type") != "heading":
            converted.append(block)
            continue
        point = _LEGACY_HEADING_PT.get(int(block.get("level", 1) or 1), theme.BODY_PT)
        moved = {k: v for k, v in block.items() if k not in ("type", "level", "runs")}
        moved["type"] = "text"
        moved["runs"] = [{**run, "sz": point} for run in block.get("runs", [])]
        converted.append(moved)
    return converted


def load_note(date: _dt.date) -> Note:
    """해당 날짜의 노트. 파일이 없거나 깨졌으면 빈 노트."""
    path = config.note_path(date)
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        _cache.pop(key, None)
        return EMPTY

    cached = _cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return EMPTY

    blocks = data.get("blocks")
    blocks = list(blocks) if isinstance(blocks, list) else []

    if "title" in data:
        title = str(data.get("title") or "")
    else:
        # "title" 키의 존재 여부로 옛 형식을 가린다. 빈 문자열이라도 키가 있으면
        # 이미 새 형식이므로, 사용자가 일부러 넣은 본문 제목1을 빼앗지 않는다.
        # 제목 끌어올리기가 제목 블록 변환보다 먼저 와야 한다.
        title, blocks = _lift_leading_heading(blocks)

    from . import serializer     # 순환 임포트를 피하려고 여기서 가져온다

    blocks = [serializer.normalize_block(b) for b in _convert_headings(blocks)]
    note = Note(title, blocks)
    _cache[key] = (mtime, note)
    return note


def save_note(date: _dt.date, note: Note) -> None:
    """노트를 저장한다. 제목과 본문이 모두 비면 파일을 만들지 않고, 기존 파일은 지운다."""
    path = config.note_path(date)
    if note.is_empty():
        path.unlink(missing_ok=True)
        _cache.pop(str(path), None)
        return

    config.ensure_dirs()
    payload = {
        "version": config.SCHEMA_VERSION,
        "date": date.strftime(config.DATE_FMT),
        "title": note.title,
        "updated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "blocks": note.blocks,
    }
    # 저장 도중 죽어도 기존 파일이 남도록 임시 파일에 쓴 뒤 교체한다.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    _cache[str(path)] = (path.stat().st_mtime, note)


def list_note_dates() -> list[_dt.date]:
    """노트가 있는 날짜, 최신순."""
    if not config.NOTES_DIR.is_dir():
        return []
    dates = [
        d for p in config.NOTES_DIR.glob("*.json")
        if (d := config.parse_date(p.stem)) is not None
    ]
    dates.sort(reverse=True)
    return dates


def blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """검색·미리보기용 평문. 이미지 run 은 글자가 없으므로 자연히 빠진다."""
    lines = []
    for block in blocks:
        text = "".join(run.get("text", "") for run in block.get("runs", []))
        if text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def title_of(date: _dt.date) -> str:
    """노트 목록에 보여줄 제목. 목록에서 넘칠 만큼 길면 자른다."""
    title = load_note(date).title.replace("\n", " ").strip()
    if len(title) <= _MAX_TITLE:
        return title
    return title[:_MAX_TITLE] + "…"


def search(query: str) -> list[_dt.date]:
    """제목이나 본문에 query가 포함된 날짜, 최신순.

    노트 수천 개까지는 전체 스캔으로 충분하고, load_note 가 mtime 캐시를 쓴다.
    """
    needle = query.strip().casefold()
    if not needle:
        return list_note_dates()

    matches = []
    for date in list_note_dates():
        note = load_note(date)
        haystack = f"{note.title}\n{blocks_to_text(note.blocks)}".casefold()
        if needle in haystack:
            matches.append(date)
    return matches


# ── 이미지 ──────────────────────────────────────────────────────────

def save_image(date: _dt.date, image) -> str | None:
    """QImage를 원본 해상도 PNG로 저장하고 파일명을 반환한다."""
    directory = config.image_dir(date)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"img_{stamp}-{secrets.token_hex(2)}.png"
    if not image.save(str(directory / name), "PNG"):
        return None
    return name


def image_path(date: _dt.date, name: str) -> Path:
    return config.image_dir(date) / Path(name).name


def adopt_image(target_date: _dt.date, name: str) -> str:
    """다른 날짜에서 붙여넣은 이미지를 현재 날짜 폴더로 복사한다.

    이미 있으면 그대로 쓰고, 원본을 어디서도 못 찾으면 이름만 돌려준다.
    """
    name = Path(name).name
    target = image_path(target_date, name)
    if target.is_file():
        return name

    for source_dir in sorted(config.IMAGES_DIR.glob("*"), reverse=True):
        source = source_dir / name
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            return name
    return name
