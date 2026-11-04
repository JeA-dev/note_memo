"""파일 첨부 기능 오프스크린 테스트.

    .venv\\Scripts\\python.exe -m tests.test_attachment
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from notememo import config

_TMP = Path(tempfile.mkdtemp(prefix="notememo-test-attach-"))
config.DATA_DIR = _TMP
config.NOTES_DIR = _TMP / "notes"
config.IMAGES_DIR = _TMP / "images"
config.ATTACHMENTS_DIR = _TMP / "attachments"

from notememo import storage, theme  # noqa: E402
from notememo.main_window import MainWindow  # noqa: E402

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.stylesheet())

    today = _dt.date.today()

    # --- 1. 유틸리티 함수 검증 ----------------------------------------
    check(storage.format_size(0) == "0 B", "format_size 0 B 실패")
    check(storage.format_size(512) == "512 B", "format_size 512 B 실패")
    check(storage.format_size(1024) == "1.0 KB", "format_size 1.0 KB 실패")
    check(storage.format_size(1024 * 1024 * 2) == "2.0 MB", "format_size 2.0 MB 실패")

    check(storage.get_file_type("doc.pdf") == "pdf", "PDF 타입 판정 실패")
    check(storage.get_file_type("image.PNG") == "image", "이미지 타입 판정 실패")
    check(storage.get_file_type("clip.mp4") == "video", "동영상 타입 판정 실패")
    check(storage.get_file_type("archive.zip") == "file", "기타 파일 타입 판정 실패")

    # --- 2. 임시 파일 생성 및 storage.save_attachment 테스트 ----------
    sample_pdf = _TMP / "test_document.pdf"
    sample_pdf.write_bytes(b"%PDF-1.4 sample content")

    sample_mp4 = _TMP / "sample_video.mp4"
    sample_mp4.write_bytes(b"dummy mp4 video stream data")

    sample_img = _TMP / "sample_photo.png"
    qimg = QImage(100, 100, QImage.Format.Format_RGB32)
    qimg.fill(0xFF00FF00)
    qimg.save(str(sample_img), "PNG")

    att_pdf = storage.save_attachment(today, sample_pdf)
    check(att_pdf is not None, "PDF 저장 실패")
    check(att_pdf.get("type") == "pdf", "PDF 메타데이터 타입 이상")
    check(att_pdf.get("original_name") == "test_document.pdf", "PDF 원본 이름 이상")
    check(storage.attachment_path(today, att_pdf["name"]).is_file(), "PDF 디스크 파일 부재")

    att_mp4 = storage.save_attachment(today, sample_mp4)
    check(att_mp4 is not None, "동영상 저장 실패")
    check(att_mp4.get("type") == "video", "동영상 메타데이터 타입 이상")

    att_img = storage.save_attachment(today, sample_img)
    check(att_img is not None, "이미지 저장 실패")
    check(att_img.get("type") == "image", "이미지 메타데이터 타입 이상")

    # --- 3. Note 저장/로드 및 검색 연동 --------------------------------
    note = storage.Note("첨부 테스트", [], [att_pdf, att_mp4, att_img])
    check(not note.is_empty(), "첨부파일이 있는 노트가 is_empty 로 판정됨")
    storage.save_note(today, note)

    loaded = storage.load_note(today)
    check(len(loaded.attachments) == 3, f"로드된 첨부파일 수 불일치: {len(loaded.attachments)}")
    check(loaded.attachments[0]["original_name"] == "test_document.pdf", "첨부파일 내용 불일치")

    # 검색 검증: 첨부파일명으로 검색
    search_res = storage.search("test_document")
    check(today in search_res, "첨부파일명 검색 실패")

    # --- 4. MainWindow 및 UI 위젯 연동 검증 ---------------------------
    window = MainWindow()
    window.show()
    app.processEvents()

    # 툴바에 첨부 버튼 존재 여부 확인
    check(hasattr(window.toolbar, "attach"), "툴바에 attach 버튼이 없음")
    check(window.toolbar.attach.text() == "첨부", f"attach 버튼 텍스트 이상: {window.toolbar.attach.text()}")
    check(window.attachment_bar is not None, "MainWindow에 attachment_bar 가 없음")

    # 첨부파일 바가 현재 3개 파일로 표시되는지 확인
    check(window.attachment_bar.isVisible(), "첨부파일이 있는데 attachment_bar 가 보이지 않음")

    # 이미지 파일이 본문에도 삽입되는지 테스트
    initial_blocks = len(window.editor.blocks())
    window.add_attachment_files([str(sample_img)])
    app.processEvents()
    check(len(window.editor.blocks()) >= initial_blocks, "이미지 첨부 후 본문 삽입 실패")
    check(len(window._attachments) == 4, f"첨부파일 목록 갱신 실패: {len(window._attachments)}")

    # 5개 이상 첨부 시 자동 줄바꿈(짤림 방지) 및 전체 목록 팝업 검증
    window.add_attachment_files([str(sample_pdf), str(sample_mp4)])
    app.processEvents()
    check(len(window._attachments) == 6, f"6개 첨부파일 추가 실패: {len(window._attachments)}")
    check(window.attachment_bar. container.flow.count() == 6, "플로우 레이아웃 내 칩 개수 불일치")
    check("6개" in window.attachment_bar.summary_tab.text(), f"요약 탭 텍스트 불일치: {window.attachment_bar.summary_tab.text()}")

    # 모든 칩이 컨테이너 오른쪽 끝을 넘어 짤리지 않고 배치되는지 확인
    container_w = window.attachment_bar.container.width()
    flow = window.attachment_bar.container.flow
    ys = set()
    for i in range(flow.count()):
        geom = flow.itemAt(i).geometry()
        ys.add(geom.y())
        check(geom.right() <= container_w + 2, f"{i}번째 칩이 오른쪽으로 짤림: {geom.right()} > {container_w}")
    check(len(ys) >= 2, f"칩이 6개인데 다음 줄로 줄바꿈되지 않음: ys={ys}")

    # 마우스 오버 팝업 표시 및 전체 리스트 행 개수 확인
    window.attachment_bar.show_popup()
    app.processEvents()
    check(window.attachment_bar.popup.isVisible(), "전체 목록 팝업이 표시되지 않음")
    check(window.attachment_bar.popup._list_layout.count() == 6, "전체 목록 팝업 행 개수 불일치")
    window.attachment_bar.popup.hide()

    # 파일 삭제 동작 검증
    name_to_del = att_pdf["name"]
    storage.delete_attachment_file(today, name_to_del)
    check(not storage.attachment_path(today, name_to_del).is_file(), "첨부파일 디스크 삭제 실패")

    window.close()

    if failures:
        print(f"FAILED ({len(failures)} failures):")
        for f in failures:
            print("  -", f)
        return 1

    print(f"OK - 모든 첨부파일 기능 정상 검증 (경로: {_TMP})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
