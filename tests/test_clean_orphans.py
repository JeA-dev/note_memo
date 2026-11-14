"""고아 파일 정리 도구 검증.

지우는 도구라서 "참조된 파일은 절대 건드리지 않는다" 를 가장 중요하게 본다.

    .venv\\Scripts\\python.exe -m tests.test_clean_orphans
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from notememo import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="notememo-orphan-"))
config.DATA_DIR = _TMP
config.NOTES_DIR = _TMP / "notes"
config.IMAGES_DIR = _TMP / "images"
config.ATTACHMENTS_DIR = _TMP / "attachments"

from notememo import storage  # noqa: E402
from tools import clean_orphans  # noqa: E402

failures: list[str] = []
TODAY = _dt.date(2026, 11, 14)
OLD = _dt.date(2026, 11, 1)


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


def write_file(root: Path, date: _dt.date, name: str, *, age_minutes: int = 60) -> Path:
    folder = root / date.strftime(config.DATE_FMT)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"x" * 100)
    stamp = time.time() - age_minutes * 60
    os.utime(path, (stamp, stamp))
    return path


def main() -> int:
    config.ensure_dirs()

    # 참조되는 것 / 안 되는 것을 섞어 둔다.
    kept_image = write_file(config.IMAGES_DIR, TODAY, "img_keep.png")
    orphan_image = write_file(config.IMAGES_DIR, TODAY, "img_orphan.png")
    orphan_old = write_file(config.IMAGES_DIR, OLD, "img_old_orphan.png")
    fresh_image = write_file(config.IMAGES_DIR, TODAY, "img_fresh.png", age_minutes=1)
    kept_att = write_file(config.ATTACHMENTS_DIR, TODAY, "att_keep.pdf")
    orphan_att = write_file(config.ATTACHMENTS_DIR, TODAY, "att_orphan.pdf")

    storage.save_note(TODAY, storage.Note(
        "제목",
        [{"type": "text", "runs": [
            {"text": "본문 "}, {"image": "img_keep.png"},
        ]}],
        [{"name": "att_keep.pdf", "original_name": "keep.pdf", "size": 100, "type": "pdf"}],
    ))
    # 내용이 빈 날짜 폴더(노트를 비워 참조가 끊긴 경우)도 섞는다.
    storage.save_note(OLD, storage.Note("옛 제목", [], []))

    images_ref, att_ref, failed = clean_orphans.collect_referenced()
    check(not failed, f"정상 노트인데 읽기 실패로 잡힘: {failed}")
    check((TODAY.strftime(config.DATE_FMT), "img_keep.png") in images_ref,
          "참조된 이미지를 못 찾음")
    check((TODAY.strftime(config.DATE_FMT), "att_keep.pdf") in att_ref,
          "참조된 첨부파일을 못 찾음")

    cutoff = time.time() - clean_orphans.KEEP_RECENT_MINUTES * 60
    image_orphans = clean_orphans.find_orphans(config.IMAGES_DIR, images_ref, cutoff)
    att_orphans = clean_orphans.find_orphans(config.ATTACHMENTS_DIR, att_ref, cutoff)

    check(kept_image not in image_orphans, "참조된 이미지가 고아로 잡힘 (치명적)")
    check(kept_att not in att_orphans, "참조된 첨부파일이 고아로 잡힘 (치명적)")
    check(orphan_image in image_orphans, "고아 이미지를 못 찾음")
    check(orphan_old in image_orphans, "참조가 끊긴 옛 날짜 이미지를 못 찾음")
    check(orphan_att in att_orphans, "고아 첨부파일을 못 찾음")
    check(fresh_image not in image_orphans,
          "방금 만든 파일까지 고아로 잡음 (저장 전 스샷이 날아간다)")

    # --- 실제로 옮겨 보고, 참조된 파일이 그대로인지 확인 ---------------
    sys.argv = ["clean_orphans", "--apply"]
    code = clean_orphans.main()
    check(code == 0, f"정리 실행이 실패함: {code}")

    check(kept_image.is_file(), "참조된 이미지가 사라짐 (치명적)")
    check(kept_att.is_file(), "참조된 첨부파일이 사라짐 (치명적)")
    check(fresh_image.is_file(), "방금 만든 파일이 사라짐")
    check(not orphan_image.is_file(), "고아 이미지가 그대로 남음")
    check(not orphan_old.is_file(), "옛 고아 이미지가 그대로 남음")
    check(not orphan_att.is_file(), "고아 첨부파일이 그대로 남음")

    # 지우지 않고 휴지통으로 옮겼는지 (되살릴 수 있어야 한다)
    trash = [p for p in config.DATA_DIR.glob("_orphans_*") if p.is_dir()]
    check(len(trash) == 1, f"휴지통 폴더가 하나가 아님: {trash}")
    if trash:
        moved = [p.name for p in trash[0].rglob("*") if p.is_file()]
        check(sorted(moved) == ["att_orphan.pdf", "img_old_orphan.png", "img_orphan.png"],
              f"휴지통 내용이 다름: {sorted(moved)}")

    # 노트는 그대로여야 한다
    note = storage.load_note(TODAY)
    check(note.title == "제목", "노트 제목이 바뀜")
    check(any(r.get("image") == "img_keep.png"
              for b in note.blocks for r in b.get("runs", [])),
          "노트의 이미지 참조가 바뀜")

    # --- 깨진 노트가 있으면 아무것도 건드리지 않고 멈춰야 한다 ---------
    broken = config.note_path(_dt.date(2026, 10, 1))
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("{ 깨진 JSON", encoding="utf-8")
    survivor = write_file(config.IMAGES_DIR, TODAY, "img_after_break.png")
    sys.argv = ["clean_orphans", "--apply"]
    code = clean_orphans.main()
    check(code == 1, "깨진 노트가 있는데도 그냥 진행함")
    check(survivor.is_file(), "깨진 노트가 있는데 파일을 옮겨버림 (치명적)")

    if failures:
        print("FAIL")
        for line in failures:
            print("  -", line)
        return 1
    print(f"OK - 고아만 정확히 골라내고 참조된 파일은 보존 (임시 폴더: {_TMP})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
