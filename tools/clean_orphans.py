"""어느 노트에서도 참조하지 않는 이미지·첨부파일을 찾아 정리한다.

노트에서 스샷을 지워도 PNG 원본은 남는다 (실수로 지웠을 때 되살릴 수 있게).
그렇게 쌓인 파일과, 노트를 통째로 비워서 참조가 끊긴 파일을 모아 치운다.

    python -m tools.clean_orphans              # 미리보기 (파일을 건드리지 않는다)
    python -m tools.clean_orphans --apply      # 휴지통 폴더로 옮긴다

지우지 않고 **옮기기만** 한다. 확인한 뒤 휴지통 폴더를 직접 지우면 공간이 확보된다.
앱이 켜져 있으면 끄고 실행하는 편이 안전하다. 방금 붙여 아직 저장되지 않은 스샷이
고아로 잡히지 않도록, 최근에 만들어진 파일은 기본적으로 건드리지 않는다.
"""

from __future__ import annotations

import datetime as _dt
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notememo import config  # noqa: E402
from notememo import storage  # noqa: E402

# 이 시간 안에 만들어진 파일은 아직 저장 전일 수 있으므로 놔둔다.
KEEP_RECENT_MINUTES = 10


def collect_referenced() -> tuple[set[tuple[str, str]], set[tuple[str, str]], list[str]]:
    """모든 노트가 참조하는 (날짜폴더, 파일명) 집합. 읽기 실패한 노트도 함께 돌려준다."""
    images: set[tuple[str, str]] = set()
    attachments: set[tuple[str, str]] = set()
    failed: list[str] = []

    for date in storage.list_note_dates():
        folder = date.strftime(config.DATE_FMT)
        try:
            note = storage.load_note(date)
        except Exception as exc:                      # noqa: BLE001
            failed.append(f"{folder}: {exc}")
            continue
        if not note.blocks and not note.title and not note.attachments:
            # 파일은 있는데 내용이 전혀 안 읽혔다면 참조를 신뢰할 수 없다.
            if config.note_path(date).stat().st_size > 2:
                failed.append(f"{folder}: 내용을 읽지 못했다")
                continue
        for block in note.blocks:
            for run in block.get("runs", []):
                name = run.get("image")
                if name:
                    images.add((folder, Path(name).name))
        for item in note.attachments:
            name = item.get("name")
            if name:
                attachments.add((folder, Path(name).name))
    return images, attachments, failed


def find_orphans(root: Path, referenced: set[tuple[str, str]], cutoff: float) -> list[Path]:
    """참조되지 않고 충분히 오래된 파일."""
    if not root.is_dir():
        return []
    orphans = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if (path.parent.name, path.name) in referenced:
            continue
        if path.stat().st_mtime > cutoff:
            continue                                   # 방금 만든 파일은 놔둔다
        orphans.append(path)
    return orphans


def report(label: str, root: Path, orphans: list[Path]) -> int:
    total = sum(1 for p in root.rglob("*") if p.is_file()) if root.is_dir() else 0
    size = sum(p.stat().st_size for p in orphans)
    print(f"\n[{label}] 디스크 {total}개 중 고아 {len(orphans)}개 · {storage.format_size(size)}")

    by_folder: dict[str, list[Path]] = {}
    for path in orphans:
        by_folder.setdefault(path.parent.name, []).append(path)
    for folder in sorted(by_folder):
        group = by_folder[folder]
        bytes_ = sum(p.stat().st_size for p in group)
        print(f"   {folder}  {len(group):4d}개  {storage.format_size(bytes_)}")
    return size


def main() -> int:
    apply = "--apply" in sys.argv
    cutoff = time.time() - KEEP_RECENT_MINUTES * 60

    images_ref, attachments_ref, failed = collect_referenced()
    if failed:
        print("노트를 읽지 못해 중단합니다. 그 노트가 쓰는 파일을 고아로 잘못 지울 수 있습니다.")
        for line in failed:
            print(f"   {line}")
        return 1

    targets = [
        ("이미지", config.IMAGES_DIR, images_ref),
        ("첨부파일", config.ATTACHMENTS_DIR, attachments_ref),
    ]
    found: list[tuple[str, Path, list[Path]]] = []
    total_size = 0
    for label, root, referenced in targets:
        orphans = find_orphans(root, referenced, cutoff)
        total_size += report(label, root, orphans)
        if orphans:
            found.append((label, root, orphans))

    count = sum(len(o) for _, _, o in found)
    if not count:
        print("\n정리할 고아 파일이 없습니다.")
        return 0

    print(f"\n합계 {count}개 · {storage.format_size(total_size)}")
    if not apply:
        print(f"미리보기입니다. 실제로 옮기려면 --apply 를 붙이세요.")
        print(f"(최근 {KEEP_RECENT_MINUTES}분 안에 만들어진 파일은 제외했습니다)")
        return 0

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    trash = config.DATA_DIR / f"_orphans_{stamp}"
    moved = 0
    for label, root, orphans in found:
        for path in orphans:
            target = trash / root.name / path.parent.name / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(path), str(target))
                moved += 1
            except OSError as exc:                     # noqa: PERF203
                print(f"!! 옮기지 못함 {path.name}: {exc}")

    print(f"\n{moved}개를 옮겼습니다: {trash}")
    print("노트를 열어 이상 없는지 확인한 뒤, 이 폴더를 지우면 공간이 확보됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
