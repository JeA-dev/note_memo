"""오프스크린 기능 테스트: 붙여넣기, 서식, 저장/복원 배선 검증.

    .venv\\Scripts\\python.exe -m tests.test_app
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QImage, QTextCursor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

from notememo import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="notememo-test-"))
config.DATA_DIR = _TMP
config.NOTES_DIR = _TMP / "notes"
config.IMAGES_DIR = _TMP / "images"

from notememo import formatting as fmt  # noqa: E402
from notememo import storage, theme  # noqa: E402
from notememo.main_window import MainWindow  # noqa: E402

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


def screenshot(width=1400, height=800) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0xFF3366AA)
    return image


def type_text(editor, text: str) -> None:
    """타이핑과 같은 경로로 글자를 넣는다.

    QTest.keyClicks 는 한글처럼 Qt::Key 로 매핑되지 않는 문자에서 죽으므로
    특수키(Space, Return)만 QTest 로 보내고 글자는 커서로 직접 넣는다.
    """
    cursor = editor.textCursor()
    cursor.insertText(text, editor.currentCharFormat())
    editor.setTextCursor(cursor)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.stylesheet())
    window = MainWindow()
    window.resize(1100, 760)
    window.show()
    QTest.qWaitForWindowExposed(window)
    app.processEvents()

    editor = window.editor
    today = _dt.date.today()
    check(editor.date == today, "시작 시 오늘 날짜가 열리지 않음")
    check(editor.content_width() > 200, f"본문 폭이 비정상: {editor.content_width()}")

    # --- 글자 크기 ------------------------------------------------
    check(fmt.current_size(editor) == theme.BODY_PT, "시작 크기가 기본값이 아님")
    window.toolbar.apply_size(18)
    check(fmt.current_size(editor) == 18, f"크기 지정 실패: {fmt.current_size(editor)}")
    type_text(editor, "큰 글씨 소제목")
    check("18" in window.toolbar.size.text(), f"툴바 크기 표시 이상: {window.toolbar.size.text()}")

    # 목록에서 한 칸 위/아래로 움직이고, 끝에서는 더 안 나간다.
    window.toolbar.apply_size(theme.SIZES[-1])
    window.toolbar.step_size(1)
    check(fmt.current_size(editor) == theme.SIZES[-1], "최대 크기를 넘어감")
    window.toolbar.step_size(-1)
    check(fmt.current_size(editor) == theme.SIZES[-2], "크기 줄이기 실패")
    window.toolbar.apply_size(theme.BODY_PT)

    # '# ' 는 이제 자동 서식이 아니라 그냥 글자로 남아야 한다.
    QTest.keyClick(editor, Qt.Key.Key_Return)
    type_text(editor, "#")
    QTest.keyClick(editor, Qt.Key.Key_Space)
    check(editor.textCursor().block().text() == "# ", "'# ' 가 아직 제목 서식으로 바뀜")
    for _ in range(2):
        QTest.keyClick(editor, Qt.Key.Key_Backspace)

    # --- 본문 + 볼드 + 형광펜 -------------------------------------
    QTest.keyClick(editor, Qt.Key.Key_Return)
    type_text(editor, "원인은 ")
    fmt.toggle_bold(editor)
    window.toolbar.apply_highlight(theme.HIGHLIGHT_COLORS[0])
    type_text(editor, "캐시 누락")
    fmt.toggle_bold(editor)
    window.toolbar.apply_highlight(theme.HIGHLIGHT_COLORS[0])
    type_text(editor, "이었다")

    # --- 자동 서식: '[] ' -> 체크박스 ------------------------------
    QTest.keyClick(editor, Qt.Key.Key_Return)
    type_text(editor, "[]")
    QTest.keyClick(editor, Qt.Key.Key_Space)
    check(fmt.read_block_type(editor.textCursor().block())[0] == fmt.TODO, "'[] ' 자동 체크박스 실패")
    type_text(editor, "롤백 점검")
    todo_block = editor.textCursor().block()

    # 체크박스 네모를 마우스로 눌러 켜고 끌 수 있어야 한다.
    text_left = editor.cursorRect(QTextCursor(todo_block)).left()
    row = editor.cursorRect(QTextCursor(todo_block)).center().y()
    check(editor._marker_rect_hit(QPoint(text_left - 10, row)), "체크박스 마커 영역을 못 맞춤")
    check(not editor._marker_rect_hit(QPoint(text_left + 40, row)), "본문 클릭이 마커로 잘못 잡힘")

    fmt.toggle_checked(todo_block)
    check(fmt.read_block_type(todo_block)[1] is True, "체크박스 토글 실패")
    editor._refresh_check_styles()
    check(len(editor.extraSelections()) == 1, "완료 항목 표시(extra selection) 없음")

    # --- 캡쳐 붙여넣기 --------------------------------------------
    QTest.keyClick(editor, Qt.Key.Key_Return)
    fmt.apply_block_type(editor.textCursor(), fmt.TEXT)
    mime = QMimeData()
    mime.setImageData(screenshot())
    editor.insertFromMimeData(mime)
    app.processEvents()

    images = editor._image_names()
    check(len(images) == 1, f"붙여넣은 이미지 개수 이상: {len(images)}")
    if images:
        saved = storage.image_path(today, images[0])
        check(saved.is_file(), f"스샷 PNG가 저장되지 않음: {saved}")
        original = QImage(str(saved))
        check(original.width() == 1400, f"원본 해상도가 보존되지 않음: {original.width()}")

    widths = []
    block = editor.document().begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            char_fmt = it.fragment().charFormat()
            if char_fmt.isImageFormat():
                widths.append(char_fmt.toImageFormat().width())
            it += 1
        block = block.next()
    check(bool(widths) and max(widths) <= editor.content_width(),
          f"이미지 표시 폭이 본문 폭 초과: {widths} > {editor.content_width()}")

    type_text(editor, "스샷 뒤 본문")

    # --- 같은 줄에 스샷 두 장 -----------------------------------------
    # (이미지를 독립 블록으로 저장해서, 다른 노트에 갔다 오면 줄이 나뉘던 회귀 경로)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    mime = QMimeData()
    mime.setImageData(screenshot(300, 120))
    editor.insertFromMimeData(mime)
    mime2 = QMimeData()
    mime2.setImageData(screenshot(320, 120))
    editor.insertFromMimeData(mime2)
    app.processEvents()

    # 붙여넣기는 각자 다른 문단에 놓는다. 사용자처럼 줄바꿈을 지워 같은 줄로 합친다.
    second = editor.document().lastBlock()
    while second.isValid() and not any(
        it.fragment().charFormat().isImageFormat() for it in _fragments(second)
    ):
        second = second.previous()
    joiner = editor.textCursor()
    joiner.setPosition(second.position())
    editor.setTextCursor(joiner)
    joiner.deletePreviousChar()
    app.processEvents()

    def side_by_side_counts():
        return [
            sum(1 for r in b.get("runs", []) if r.get("image"))
            for b in editor.blocks()
        ]

    joined = side_by_side_counts()
    check(2 in joined, f"두 스샷이 같은 문단으로 합쳐지지 않음 (전제 조건 실패): {joined}")

    # 이어지는 검사가 이미지 문단에 얹히지 않도록 깨끗한 문단으로 옮긴다.
    tail_cursor = editor.textCursor()
    tail_cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(tail_cursor)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    fmt.apply_block_type(editor.textCursor(), fmt.TEXT, keep_layout=False)
    editor.setCurrentCharFormat(fmt.char_format())

    # --- 외부 서식 텍스트는 평문으로만 -----------------------------
    html_mime = QMimeData()
    html_mime.setHtml('<b style="color:red;font-size:40px">붉은굵은글씨</b>')
    html_mime.setText("붉은굵은글씨")
    editor.insertFromMimeData(html_mime)
    tail = editor.document().lastBlock()
    check(all(
        not it.fragment().charFormat().fontWeight() > 500
        for it in _fragments(tail)
    ), "외부 HTML 서식이 그대로 들어옴")

    # --- 정렬 --------------------------------------------------------
    window.toolbar.apply_align("center")
    check(fmt.read_align(editor.textCursor().block()) == "center", "가운데 정렬 적용 실패")
    # 정렬과 글자 크기는 블록 타입을 바꿔도 살아남아야 한다
    # (블록 서식을 통째로 갈아끼우는 경로).
    window.toolbar.apply_size(16)
    type_text(editor, "정렬 유지 확인")
    window._block(fmt.BULLET)
    check(fmt.read_align(editor.textCursor().block()) == "center", "목록으로 바꾸자 정렬이 풀림")
    window._block(fmt.TODO)
    check(fmt.read_align(editor.textCursor().block()) == "center", "체크박스로 바꾸자 정렬이 풀림")
    sizes = [
        r.get("sz") for b in editor.blocks() for r in b.get("runs", [])
        if "정렬 유지" in r.get("text", "")
    ]
    check(sizes == [16], f"블록 타입을 바꾸자 글자 크기가 풀림: {sizes}")
    window._block(fmt.TODO)                      # 다시 눌러 본문으로
    window.toolbar.apply_align(fmt.LEFT)
    window.toolbar.apply_size(theme.BODY_PT)

    # --- 제목 --------------------------------------------------------
    window.header.title_input.setText("배포 장애 기록")
    window.header.titleEdited.emit()
    check(window.toolbar.save.property("dirty") == "true", "타이핑 후 저장 버튼이 활성화되지 않음")

    # --- 들여쓰기 -----------------------------------------------------
    QTest.keyClick(editor, Qt.Key.Key_Return)
    fmt.apply_block_type(editor.textCursor(), fmt.TEXT, keep_layout=False)
    type_text(editor, "들여쓴 문단")
    for _ in range(3):
        QTest.keyClick(editor, Qt.Key.Key_Tab)
    check(fmt.read_indent(editor.textCursor().block()) == 3,
          f"Tab 들여쓰기 실패: {fmt.read_indent(editor.textCursor().block())}")
    QTest.keyClick(editor, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    check(fmt.read_indent(editor.textCursor().block()) == 2, "Shift+Tab 내어쓰기 실패")
    check(editor.textCursor().block().text() == "들여쓴 문단",
          "Tab 이 글자를 건드림 (공백이 들어갔다)")

    # 목록 항목에서 Backspace 로 빠져나가면 Qt 가 들여쓰기를 넣어 위치를 유지한다.
    # 그 값을 저장하지 않아 다시 열면 줄이 왼쪽으로 튀던 회귀 경로.
    QTest.keyClick(editor, Qt.Key.Key_Return)
    fmt.apply_block_type(editor.textCursor(), fmt.TEXT, keep_layout=False)
    window._block(fmt.BULLET)
    type_text(editor, "불릿 항목")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    type_text(editor, "목록에서 빠져나온 줄")
    exited = editor.textCursor().block()
    escaped_indent = fmt.read_indent(exited)
    check(escaped_indent > 0,
          "Backspace 로 목록을 빠져나갔는데 Qt 들여쓰기가 없음 (전제 조건 실패)")
    check(any(b.get("indent") == escaped_indent for b in editor.blocks()),
          f"들여쓰기 {escaped_indent} 이 저장 블록에 없음: {editor.blocks()[-2:]}")

    # --- 역방향 선택에서도 서식 토글이 꺼져야 한다 -------------------
    # (오른쪽->왼쪽으로 끌어 선택하면 커서가 선택 앞쪽에 놓여, 선택 밖 글자의
    #  서식을 읽어 이미 켜진 서식이 꺼지지 않던 회귀 경로)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    # 앞에 평문 한 글자를 둬야 "선택 바로 앞 글자"가 서식 없는 상태가 된다.
    # 그러지 않으면 커서 기준으로 읽어도 우연히 맞아 버그가 드러나지 않는다.
    type_text(editor, "앞역방향선택")
    end = editor.textCursor().position()
    start = end - 5

    def select(a, b):
        cursor = editor.textCursor()
        cursor.setPosition(a)
        cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    def flag_of(name):
        return [r.get(name) for b in editor.blocks() for r in b.get("runs", [])
                if r.get("text") == "역방향선택" and r.get(name)]

    for label, toggle, flag in (
        ("형광펜", lambda: window.toolbar.apply_highlight(theme.HIGHLIGHT_COLORS[0]), "hl"),
        ("굵게", lambda: fmt.toggle_bold(editor), "b"),
        ("기울임", lambda: fmt.toggle_italic(editor), "i"),
        ("밑줄", lambda: fmt.toggle_underline(editor), "u"),
        ("취소선", lambda: fmt.toggle_strike(editor), "s"),
    ):
        select(start, end)          # 정방향으로 켜기
        toggle()
        check(bool(flag_of(flag)), f"{label} 적용 자체가 안 됨")

        select(end, start)          # 역방향으로 같은 범위 재선택
        check(bool(fmt.read_char_flags(fmt.selection_char_format(editor)).get(flag)),
              f"역방향 선택에서 {label} 상태를 못 읽음")
        toggle()                    # 다시 눌러 끄기
        check(not flag_of(flag), f"역방향 선택에서 {label}이 꺼지지 않음")
    select(end, end)

    # --- 제목 칸에서 서식 단축키가 포커스를 훔치지 않아야 한다 --------
    window.header.title_input.setFocus()
    app.processEvents()
    QTest.keyClick(
        window, Qt.Key.Key_L,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    app.processEvents()
    check(window.header.title_input.hasFocus(),
          "제목 칸에서 정렬 단축키를 누르자 포커스가 본문으로 넘어감")
    editor.setFocus()
    app.processEvents()

    # --- 저장 / 날짜 이동 / 복원 -----------------------------------
    window.save()
    saved = storage.load_note(today)
    saved_blocks = saved.blocks
    check(bool(saved_blocks), "저장된 블록이 없음")
    check(saved.title == "배포 장애 기록", f"제목이 저장되지 않음: {saved.title!r}")
    check(config.note_path(today).is_file(), "노트 JSON이 생성되지 않음")
    check(window.toolbar.save.property("dirty") == "false", "저장 후에도 저장 버튼이 활성 상태")
    raw = json.loads(config.note_path(today).read_text(encoding="utf-8"))
    check(raw.get("title") == "배포 장애 기록", "JSON에 title 필드가 없음")

    window.step_day(-1)
    check(editor.date == today - _dt.timedelta(days=1), "이전 날짜로 이동 실패")
    check(editor.document().isEmpty() or not editor.blocks(), "새 날짜인데 내용이 남아 있음")
    check(not config.note_path(editor.date).is_file(), "빈 노트인데 파일이 생성됨")

    window.go_today()
    restored = editor.blocks()
    check(restored == saved_blocks, "재방문 시 내용이 그대로 복원되지 않음")

    types = [b.get("type") for b in restored]
    check(fmt.TODO in types, "체크박스 블록이 복원되지 않음")
    check(any(r.get("image") for b in restored for r in b.get("runs", [])),
          "이미지 run 이 복원되지 않음")
    check(2 in side_by_side_counts(),
          f"재방문 후 같은 줄의 스샷 두 장이 줄로 나뉘었다: {side_by_side_counts()}")
    check(any(r.get("sz") == 18 for b in restored for r in b.get("runs", [])),
          "글자 크기가 복원되지 않음")
    check(any(b.get("checked") for b in restored if b.get("type") == fmt.TODO),
          "체크 상태가 복원되지 않음")
    check(any(r.get("b") and r.get("hl") for b in restored for r in b.get("runs", [])),
          "볼드+형광펜 run이 복원되지 않음")

    # --- 창 크기 변경 시 이미지 재조정 -------------------------------
    window.resize(900, 700)
    app.processEvents()
    editor._refit_images()
    app.processEvents()
    check(editor.blocks() == restored, "리사이즈가 저장 내용을 바꿈")

    check(window.header.title() == "배포 장애 기록", "재방문 시 제목이 복원되지 않음")

    # --- 사이드바는 제목만 보여준다 ----------------------------------
    window.sidebar.refresh(today)
    row = window.sidebar.note_list.item(0).text()
    check("배포 장애 기록" in row, f"목록에 제목이 없음: {row!r}")
    check("캐시 누락" not in row, f"목록에 본문이 새어 나옴: {row!r}")

    # --- 검색 (본문 + 제목) ------------------------------------------
    for query, label in (("캐시 누락", "본문"), ("배포 장애", "제목")):
        window.sidebar.search.setText(query)
        app.processEvents()
        check(window.sidebar.note_list.count() == 1,
              f"{label} 검색 결과 개수 이상: {window.sidebar.note_list.count()}")
    window.sidebar.search.clear()

    window.close()

    # --- 재시작해도 오늘 노트가 살아남아야 한다 ----------------------
    # (첫 go_to 가 빈 문서를 먼저 저장하면 기존 노트를 지워버렸던 회귀 경로)
    again = MainWindow()
    again.resize(1100, 760)
    again.show()
    app.processEvents()
    check(again.editor.date == today, "재시작 시 오늘 날짜가 열리지 않음")
    check(again.editor.blocks() == saved_blocks, "재시작 후 오늘 노트가 사라지거나 달라짐")
    check(config.note_path(today).is_file(), "재시작이 오늘 노트 파일을 지움")
    check(again.header.title() == "배포 장애 기록", "재시작 후 제목이 복원되지 않음")

    # --- 제목만 있는 노트도 파일로 남는다 ----------------------------
    title_only = today - _dt.timedelta(days=2)
    again.go_to(title_only)
    again.header.title_input.setText("제목만 적은 날")
    again.header.titleEdited.emit()
    again.save()
    check(config.note_path(title_only).is_file(), "제목만 있는 노트가 저장되지 않음")
    check(storage.load_note(title_only).title == "제목만 적은 날", "제목만 있는 노트의 제목 유실")

    # 제목까지 지우면 파일도 사라진다.
    again.header.title_input.clear()
    again.save()
    check(not config.note_path(title_only).is_file(), "제목·본문이 모두 비었는데 파일이 남음")
    again.close()

    # --- 옛 형식 마이그레이션 ----------------------------------------
    legacy_date = today - _dt.timedelta(days=5)
    _write_legacy(legacy_date, title_key=None)
    legacy = storage.load_note(legacy_date)
    check(legacy.title == "옛 노트 제목", f"첫 제목1이 제목으로 안 올라옴: {legacy.title!r}")
    check(all(b.get("type") != "heading" for b in legacy.blocks),
          f"heading 블록이 본문에 남음: {[b.get('type') for b in legacy.blocks]}")
    # 본문 제목2는 사라지지 않고 글자 크기로 이어받는다.
    h2_runs = [r for b in legacy.blocks for r in b.get("runs", []) if "소제목" in r.get("text", "")]
    check(h2_runs and h2_runs[0].get("sz") == 14,
          f"제목2가 글자 크기로 이어받지 못함: {h2_runs}")
    check(len(legacy.blocks) == 3, f"본문 블록 수 이상: {len(legacy.blocks)}")

    # "title" 키가 있으면(빈 문자열이어도) 이미 새 형식이라 제목을 가져가지 않는다.
    modern_date = today - _dt.timedelta(days=6)
    _write_legacy(modern_date, title_key="")
    modern = storage.load_note(modern_date)
    check(modern.title == "", f"새 형식 노트의 제목이 바뀜: {modern.title!r}")
    first_runs = modern.blocks[0].get("runs", [])
    check(first_runs and first_runs[0].get("text") == "옛 노트 제목",
          "새 형식 노트인데 본문 첫 줄을 제목으로 가져가 버림")
    check(first_runs and first_runs[0].get("sz") == 17,
          f"제목1이 글자 크기 17로 이어받지 못함: {first_runs}")

    # --- 글자 크기 변경 후 목록 작성 시 불릿/글자 크기 일관성 ---------
    list_date = today - _dt.timedelta(days=50)
    window.go_to(list_date)
    window.toolbar.apply_size(16)
    fmt.toggle_bold(editor)
    type_text(editor, "<파이썬>")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    window.toolbar.apply_size(11)
    fmt.toggle_bold(editor)
    window._block(fmt.BULLET)
    check(round(editor.textCursor().blockCharFormat().fontPointSize()) == 11,
          f"글자 크기 축소 후 목록 전환 시 불릿 크기가 따라오지 않음: {editor.textCursor().blockCharFormat().fontPointSize()}")
    check(fmt.current_size(editor) == 11,
          f"글자 크기 축소 후 목록 전환 시 입력 크기가 바뀜: {fmt.current_size(editor)}")
    type_text(editor, "맛보기")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    check(round(editor.textCursor().blockCharFormat().fontPointSize()) == 11,
          "목록 줄바꿈 후 불릿 크기가 달라짐")

    # 자동 서식(- + Space) 시에도 변경한 글자 크기가 유지되어야 한다
    QTest.keyClick(editor, Qt.Key.Key_Return)   # 목록 종료
    window.toolbar.apply_size(18)
    type_text(editor, "큰 제목")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    window.toolbar.apply_size(12)
    type_text(editor, "-")
    QTest.keyClick(editor, Qt.Key.Key_Space)
    check(round(editor.textCursor().blockCharFormat().fontPointSize()) == 12,
          f"자동 서식(- ) 목록 전환 시 불릿 크기가 이전 줄 크기로 되돌아감: {editor.textCursor().blockCharFormat().fontPointSize()}")
    check(fmt.current_size(editor) == 12,
          f"자동 서식(- ) 목록 전환 시 글자 크기가 이전 줄 크기로 되돌아감: {fmt.current_size(editor)}")

    # --- 구분선 서식 (툴바, 단축키, 마크다운 --- 자동변환, 저장/복원) ---
    div_date = today - _dt.timedelta(days=70)
    window.go_to(div_date)
    type_text(editor, "구역 1")
    # 툴바 버튼으로 구분선 삽입
    window.toolbar.insert_divider("dashed")
    type_text(editor, "구역 2")
    blocks = editor.blocks()
    types = [b.get("type") for b in blocks]
    check(types == [fmt.TEXT, fmt.DIVIDER, fmt.TEXT], f"툴바 구분선 삽입 실패: {types}")

    # 단축키 Ctrl+Shift+D 로 구분선 삽입
    QTest.keyClick(
        editor, Qt.Key.Key_D,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    type_text(editor, "구역 3")
    types = [b.get("type") for b in editor.blocks()]
    check(types == [fmt.TEXT, fmt.DIVIDER, fmt.TEXT, fmt.DIVIDER, fmt.TEXT],
          f"단축키 구분선 삽입 실패: {types}")

    # '---' 입력 후 Enter 로 구분선 자동 변환
    QTest.keyClick(editor, Qt.Key.Key_Return)
    type_text(editor, "---")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    type_text(editor, "구역 4")
    types = [b.get("type") for b in editor.blocks()]
    check(types[-2] == fmt.DIVIDER, f"'---' Enter 자동 구분선 변환 실패: {types}")

    # '---' 입력 후 Space 로 구분선 자동 변환
    QTest.keyClick(editor, Qt.Key.Key_Return)
    type_text(editor, "---")
    QTest.keyClick(editor, Qt.Key.Key_Space)
    type_text(editor, "구역 5")
    types = [b.get("type") for b in editor.blocks()]
    check(types[-2] == fmt.DIVIDER, f"'---' Space 자동 구분선 변환 실패: {types}")

    # 저장 및 복원 검증
    window.save()
    window.step_day(-1)
    window.go_to(div_date)
    restored_types = [b.get("type") for b in editor.blocks()]
    check(restored_types == types, f"구분선 저장 후 재방문 복원 실패: {restored_types} vs {types}")

    # Backspace 로 구분선 삭제 검증
    cur = editor.textCursor()
    cur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
    editor.setTextCursor(cur)
    before_count = len(editor.blocks())
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    after_count = len(editor.blocks())
    check(after_count == before_count - 1, f"구분선 Backspace 삭제 실패: {before_count} -> {after_count}")

    # --- 서식 지우기 버튼 삭제 및 빨간색 별표 서식 검증 ---
    check(not hasattr(window.toolbar, "clear"), "서식 지우기 버튼이 툴바에 남아 있음")
    check(hasattr(window.toolbar, "star"), "빨간 별표 버튼이 툴바에 없음")

    star_date = today - _dt.timedelta(days=80)
    window.go_to(star_date)
    # 툴바 버튼으로 빨간 별표(스케치 스타일) 삽입
    window.toolbar.insert_star("sketch", filled=False)
    type_text(editor, "중요 개념 1")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    # 단축키 Ctrl+Alt+S 로 빨간 별표 삽입
    QTest.keyClick(
        editor, Qt.Key.Key_S,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
    )
    type_text(editor, "중요 개념 2")

    star_blocks = editor.blocks()
    check(len(star_blocks) == 2, f"별표 삽입 블록 수 이상: {len(star_blocks)}")
    first_runs = star_blocks[0].get("runs", [])
    check(len(first_runs) == 2, f"별표 + 본문 런 분리 실패: {first_runs}")
    check(first_runs[0].get("star") == "sketch",
          f"첫 번째 별표 서식 이상: {first_runs[0]}")
    check(first_runs[1].get("text") == " 중요 개념 1" and "c" not in first_runs[1],
          f"별표 뒤 본문 텍스트 서식 오염: {first_runs[1]}")

    second_runs = star_blocks[1].get("runs", [])
    check(len(second_runs) == 2, f"두 번째 별표 + 본문 런 분리 실패: {second_runs}")
    check(second_runs[0].get("star") == "sketch",
          f"두 번째 별표 서식 이상: {second_runs[0]}")
    check(second_runs[1].get("text") == " 중요 개념 2",
          f"두 번째 별표 뒤 본문 텍스트 이상: {second_runs[1]}")

    # 저장 및 복원
    window.save()
    window.step_day(-1)
    window.go_to(star_date)
    restored_star_blocks = editor.blocks()
    check(restored_star_blocks == star_blocks,
          f"빨간 별표 저장/복원 실패: {restored_star_blocks} vs {star_blocks}")

    # --- 노트 삭제 기능 검증 ----------------------------------------
    # 1. 새 빈 날짜에서는 삭제 버튼이 비활성화되어 있어야 한다.
    empty_date = today - _dt.timedelta(days=99)
    window.go_to(empty_date)
    check(not window.header.delete_button.isEnabled(), "빈 날짜에서 노트 삭제 버튼이 활성화되어 있음")

    # 글자를 입력하면 삭제 버튼이 즉시 활성화된다.
    type_text(editor, "실수로 작성한 내용")
    check(window.header.delete_button.isEnabled(), "내용 입력 후 삭제 버튼이 활성화되지 않음")
    window.save()
    check(config.note_path(empty_date).is_file(), "실수 노트가 저장되지 않음")
    check(empty_date in storage.list_note_dates(), "실수 노트가 목록에 나타나지 않음")

    # 2. 실수로 생성된 노트 삭제 (현재 열린 노트 삭제)
    # 삭제 시 파일이 지워지고, 오늘 날짜로 이동해야 한다.
    window.delete_note(empty_date)
    check(not config.note_path(empty_date).is_file(), "노트 삭제 후 파일이 디스크에 남아 있음")
    check(empty_date not in storage.list_note_dates(), "노트 삭제 후 목록에 날짜가 남아 있음")
    check(editor.date == today, "과거 실수 노트 삭제 후 오늘로 돌아오지 않음")

    # 3. 사이드바를 통한 다른 노트 삭제 검증
    other_date = today - _dt.timedelta(days=98)
    storage.save_note(other_date, storage.Note("사이드바 삭제 테스트", [{"type": "text", "runs": [{"text": "내용"}]}], []))
    window.sidebar.refresh(today)
    check(other_date in storage.list_note_dates(), "테스트 노트 생성 실패")

    window.delete_note(other_date)
    check(not config.note_path(other_date).is_file(), "사이드바 노트 삭제 실패")
    check(other_date not in storage.list_note_dates(), "사이드바 삭제 후 목록 갱신 실패")
    check(editor.date == today, "사이드바의 다른 노트 삭제 시 현재 에디터 날짜가 변경됨")

    # 4. 이미지/첨부파일이 포함된 노트 삭제 시 폴더 정리 검증
    media_date = today - _dt.timedelta(days=97)
    window.go_to(media_date)
    window.editor.insert_image(screenshot(200, 200))
    window.save()
    check(config.image_dir(media_date).is_dir(), "이미지 폴더 생성 실패")
    window.delete_note(media_date)
    check(not config.image_dir(media_date).is_dir(), "노트 삭제 후 이미지 폴더가 삭제되지 않음")
    check(not config.note_path(media_date).is_file(), "미디어 노트 삭제 후 파일이 남아 있음")

    # 5. _NoteListWidget Delete 키 시그널 검증
    received_delete = []
    window.sidebar.deleteRequested.connect(received_delete.append)
    sample_date = today - _dt.timedelta(days=96)
    storage.save_note(sample_date, storage.Note("키보드 삭제 테스트", [{"type": "text", "runs": [{"text": "내용"}]}], []))
    window.sidebar.refresh(today)
    window.sidebar._select_in_list(sample_date)
    QTest.keyClick(window.sidebar.note_list, Qt.Key.Key_Delete)
    check(sample_date in received_delete, "NoteList에서 Delete 키 입력 시 deleteRequested 시그널이 발생하지 않음")
    storage.delete_note(sample_date)

    if failures:
        print("FAIL")
        for line in failures:
            print("  -", line)
        return 1
    print(f"OK - {len(restored)}개 블록, 이미지 표시폭 {max(widths):.0f}px, 데이터 {_TMP}")
    return 0


def _write_legacy(date: _dt.date, title_key: str | None) -> None:
    """제목1로 시작하는 노트 파일을 직접 써둔다. title_key=None 이면 옛 형식."""
    payload = {
        "version": 1,
        "date": date.strftime(config.DATE_FMT),
        "blocks": [
            {"type": "heading", "level": 1, "runs": [{"text": "옛 노트 제목"}]},
            {"type": "text", "runs": [{"text": "본문 한 줄"}]},
            {"type": "heading", "level": 2, "align": "center",
             "runs": [{"text": "본문 속 소제목"}]},
            {"type": "text", "runs": [{"text": "마지막 줄"}]},
        ],
    }
    if title_key is not None:
        payload["title"] = title_key
    config.ensure_dirs()
    config.note_path(date).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _fragments(block):
    it = block.begin()
    while not it.atEnd():
        yield it
        it += 1


if __name__ == "__main__":
    raise SystemExit(main())
