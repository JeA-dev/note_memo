"""공백으로 수동 들여쓰기한 문단을 실제 들여쓰기(indent)로 바꾼다.

들여쓰기 기능이 없던 시절에 공백을 여러 번 쳐서 줄을 맞춘 노트를 정리한다.
공백으로 맞춘 들여쓰기는 글자 크기를 바꾸면 어긋나므로 블록 속성으로 옮기는 게 낫다.

    python -m tools.convert_space_indent            # 미리보기 (파일 안 건드림)
    python -m tools.convert_space_indent --apply    # 실제 변환 (백업 후)

앱이 켜져 있으면 자동저장이 되돌려 버리므로 반드시 끄고 실행한다.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notememo import config  # noqa: E402
from notememo import formatting as fmt  # noqa: E402

# 공백 몇 개를 한 단계로 볼지. 사용자가 불릿 글자 위치에 맞추려고 쓴 값이다.
SPACES_PER_LEVEL = 6
# 이보다 적은 선행 공백은 들여쓰기 의도가 아니라 오타로 본다
# (불릿 항목 앞의 공백 한 칸 같은 것).
MIN_SPACES = 3


def convert_block(block: dict) -> tuple[dict, int] | None:
    """바꿀 게 있으면 (새 블록, 단계) 를, 없으면 None 을 돌려준다."""
    if block.get("type") != "text":
        # 목록과 체크박스는 이미 목록 들여쓰기가 있고, 앞 공백은 대개 오타다.
        return None
    runs = block.get("runs") or []
    if not runs:
        return None

    text = runs[0].get("text", "")
    spaces = len(text) - len(text.lstrip(" "))
    if spaces < MIN_SPACES:
        return None

    level = fmt.clamp_indent(
        max(1, round(spaces / SPACES_PER_LEVEL)) + fmt.clamp_indent(block.get("indent"))
    )
    new_block = dict(block)
    new_block["runs"] = [{**runs[0], "text": text[spaces:]}, *runs[1:]]
    new_block["indent"] = level
    return new_block, level


def main() -> int:
    apply = "--apply" in sys.argv
    notes = sorted(config.NOTES_DIR.glob("*.json"))
    if not notes:
        print(f"노트가 없습니다: {config.NOTES_DIR}")
        return 1

    total = 0
    plans: list[tuple[Path, dict, int]] = []

    for path in notes:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"!! {path.name} 읽기 실패: {exc}")
            continue

        blocks = data.get("blocks") or []
        changed = 0
        new_blocks = []
        for index, block in enumerate(blocks):
            result = convert_block(block)
            if result is None:
                new_blocks.append(block)
                continue
            new_block, level = result
            changed += 1
            before = (block.get("runs") or [{}])[0].get("text", "")
            after = (new_block["runs"] or [{}])[0].get("text", "")
            print(f"  {path.stem} [{index:2d}] 공백{len(before) - len(after)}개 "
                  f"-> indent {level}   {after.strip()[:34]!r}")
            new_blocks.append(new_block)

        if changed:
            data["blocks"] = new_blocks
            plans.append((path, data, changed))
            total += changed

    if not total:
        print("바꿀 문단이 없습니다.")
        return 0

    print(f"\n총 {total}개 문단, {len(plans)}개 노트")
    if not apply:
        print("미리보기입니다. 실제로 바꾸려면 --apply 를 붙이세요.")
        return 0

    backup = config.DATA_DIR.parent / f"{config.DATA_DIR.name}_before_indent_convert"
    if backup.exists():
        shutil.rmtree(backup)
    shutil.copytree(config.DATA_DIR, backup)
    print(f"백업: {backup}")

    for path, data, changed in plans:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        print(f"저장: {path.name} ({changed}개)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
