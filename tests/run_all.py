"""테스트를 한 번에 돌리고 검사 건수를 센다.

    .venv\\Scripts\\python.exe -m tests.run_all

각 테스트는 따로 프로세스를 띄워 돌린다. 테스트마다 임시 저장 폴더와 Qt 플랫폼을
다르게 잡기 때문에, 한 프로세스에서 모아 돌리면 서로의 설정을 덮어쓴다.

검사 건수는 각 테스트의 `check()` 를 가로채서 센다. README 의 테스트 배지에 적는
숫자가 여기서 나온다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MODULES = [
    "test_serializer",
    "test_app",
    "test_attachment",
    "test_clean_orphans",
    "test_divider",
    "test_sidebar",
    "test_paste",
    "test_tags",
]

# 모듈을 불러온 뒤 check() 를 세는 껍데기로 바꾸고 main() 을 부른다.
_RUNNER = """
import sys
import tests.{name} as m
count = [0]
original = getattr(m, "check", None)
if callable(original):
    def counting(condition, label):
        count[0] += 1
        return original(condition, label)
    m.check = counting
code = m.main()
print("__CHECKS__", count[0])
sys.exit(code)
"""


def main() -> int:
    total_checks = 0
    failed = []
    for name in MODULES:
        result = subprocess.run(
            [sys.executable, "-c", _RUNNER.format(name=name)],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        checks = 0
        lines = []
        for line in (result.stdout or "").splitlines():
            if line.startswith("__CHECKS__"):
                checks = int(line.split()[1])
            else:
                lines.append(line)
        total_checks += checks
        mark = "PASS" if result.returncode == 0 else "FAIL"
        print(f"{name:<20} {mark}  검사 {checks:3d}건")
        if result.returncode != 0:
            failed.append(name)
            for line in lines[-12:]:
                print("     ", line)
            if result.stderr:
                print("     ", result.stderr.strip().splitlines()[-1])

    print()
    if failed:
        print(f"FAIL - {len(failed)}개 실패: {', '.join(failed)}")
        return 1
    print(f"OK - {len(MODULES)}개 테스트 · 검사 {total_checks}건 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
