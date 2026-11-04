"""저장 경로와 날짜 포맷 유틸."""

from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path

APP_NAME = "NoteMemo"
SCHEMA_VERSION = 1

DATE_FMT = "%Y-%m-%d"
_WEEKDAY_KO = ("월", "화", "수", "목", "금", "토", "일")


def resource_path(relative: str) -> Path:
    """번들에 들어간 리소스 경로.

    PyInstaller 로 묶어 실행하면 리소스가 임시 폴더(`sys._MEIPASS`)에 풀린다.
    소스로 실행할 때는 프로젝트 폴더를 기준으로 찾는다.
    """
    bundled = getattr(sys, "_MEIPASS", None)
    root = Path(bundled) if bundled else Path(__file__).resolve().parent.parent
    return root / relative


def _documents_dir() -> Path:
    """윈도우 문서 폴더. OneDrive 리다이렉트나 미존재 시 홈으로 폴백."""
    for candidate in (
        os.environ.get("OneDrive"),
        os.environ.get("USERPROFILE"),
        str(Path.home()),
    ):
        if not candidate:
            continue
        docs = Path(candidate) / "Documents"
        if docs.is_dir():
            return docs
    return Path.home()


DATA_DIR = _documents_dir() / APP_NAME
NOTES_DIR = DATA_DIR / "notes"
IMAGES_DIR = DATA_DIR / "images"
ATTACHMENTS_DIR = DATA_DIR / "attachments"


def attachment_base_dir() -> Path:
    # 테스트 등에서 DATA_DIR 이 동적으로 변경된 경우 반영
    if ATTACHMENTS_DIR.parent != DATA_DIR:
        return DATA_DIR / "attachments"
    return ATTACHMENTS_DIR


def ensure_dirs() -> None:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    attachment_base_dir().mkdir(parents=True, exist_ok=True)


def note_path(date: _dt.date) -> Path:
    return NOTES_DIR / f"{date.strftime(DATE_FMT)}.json"


def image_dir(date: _dt.date) -> Path:
    return IMAGES_DIR / date.strftime(DATE_FMT)


def attachment_dir(date: _dt.date) -> Path:
    return attachment_base_dir() / date.strftime(DATE_FMT)


def parse_date(text: str) -> _dt.date | None:
    try:
        return _dt.datetime.strptime(text, DATE_FMT).date()
    except ValueError:
        return None


def format_full(date: _dt.date) -> str:
    """2026년 8월 28일 (금)"""
    return f"{date.year}년 {date.month}월 {date.day}일 ({_WEEKDAY_KO[date.weekday()]})"


def format_short(date: _dt.date) -> str:
    """8/28 (금)"""
    return f"{date.month}/{date.day} ({_WEEKDAY_KO[date.weekday()]})"
