"""색상 팔레트, 폰트 스택, QSS 스타일시트."""

from __future__ import annotations

# 종이 질감의 웜톤 팔레트. 값은 여기 한 곳에서만 정의한다.
PALETTE = {
    "paper": "#FBF8F3",
    "sidebar": "#F2EDE4",
    "border": "#E5DCCE",
    "ink": "#33302B",
    "ink_soft": "#8A8073",
    "ink_faint": "#B3AA9C",
    "accent": "#8C6A4A",
    "accent_soft": "#EFE3D0",
    "hover": "#E9E1D4",
}

# 형광펜 3색 (라벨, hex)
HIGHLIGHTS = [
    ("노랑", "#FBEFA8"),
    ("민트", "#C9E7D8"),
    ("핑크", "#F6D0D8"),
]
HIGHLIGHT_COLORS = [c for _, c in HIGHLIGHTS]

# 폰트 스택. 윈도우 기본 탑재 폰트로 폴백하므로 별도 설치가 필요 없다.
SANS_STACK = ["Pretendard", "Malgun Gothic", "맑은 고딕", "Segoe UI"]
SERIF_STACK = ["Nanum Myeongjo", "Batang", "바탕", "Georgia"]

SANS_CSS = ", ".join(f'"{f}"' for f in SANS_STACK) + ", sans-serif"
SERIF_CSS = ", ".join(f'"{f}"' for f in SERIF_STACK) + ", serif"

BODY_PT = 11           # 본문 기본 포인트 크기
# 글자 크기 서식으로 고를 수 있는 값. 임의 크기를 허용하지 않아 문서가 정규화된다.
SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 22, 28]
LINE_HEIGHT_PCT = 170  # 비율 줄간격 (%)
DOC_MARGIN = 44        # QTextDocument 여백
# 본문이 너무 길게 늘어지지 않도록 하는 책 같은 단 폭. 툴바도 이 폭에 맞춰 끝난다.
CONTENT_WIDTH = 780


def clamp_size(point: int | float | None) -> int:
    """지원하는 크기로 맞춘다. None 이나 범위 밖이면 가장 가까운 값."""
    if not point or point <= 0:
        return BODY_PT
    return min(SIZES, key=lambda s: abs(s - point))


def stylesheet() -> str:
    p = PALETTE
    return f"""
* {{ font-family: {SANS_CSS}; }}

QWidget#Root, QMainWindow {{ background: {p['paper']}; }}

/* ── 사이드바 ───────────────────────────────── */
QWidget#Sidebar {{
    background: {p['sidebar']};
    border-right: 1px solid {p['border']};
}}
QLineEdit#Search {{
    background: {p['paper']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 7px 10px;
    color: {p['ink']};
    font-size: 12px;
}}
QLineEdit#Search:focus {{ border: 1px solid {p['accent']}; }}

QLabel#SectionLabel {{
    color: {p['ink_soft']};
    font-size: 11px;
    font-weight: 600;
    padding: 2px 4px;
}}

QListWidget#NoteList {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget#NoteList::item {{
    color: {p['ink']};
    padding: 7px 9px;
    border-radius: 7px;
    margin: 1px 2px;
}}
QListWidget#NoteList::item:hover {{ background: {p['hover']}; }}
QListWidget#NoteList::item:selected {{
    background: {p['accent_soft']};
    color: {p['ink']};
}}

/* ── 캘린더 ─────────────────────────────────── */
QCalendarWidget {{ background: transparent; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: transparent;
    border-bottom: 1px solid {p['border']};
}}
QCalendarWidget QToolButton {{
    background: transparent;
    color: {p['ink']};
    font-size: 12px;
    font-weight: 600;
    border: none;
    padding: 4px 8px;
    border-radius: 6px;
}}
QCalendarWidget QToolButton:hover {{ background: {p['hover']}; }}
QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QSpinBox {{
    background: {p['paper']};
    color: {p['ink']};
    border: 1px solid {p['border']};
}}
/* 뷰의 배경은 transparent 로 두면 검게 칠해지므로 색을 명시한다. */
QCalendarWidget QAbstractItemView {{
    background: {p['sidebar']};
    alternate-background-color: {p['sidebar']};
    outline: none;
    color: {p['ink']};
    selection-background-color: {p['accent']};
    selection-color: #FFFFFF;
    font-size: 12px;
}}
QCalendarWidget QAbstractItemView:!focus {{
    selection-background-color: {p['accent']};
    selection-color: #FFFFFF;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {p['ink_faint']}; }}
QCalendarWidget QWidget {{ alternate-background-color: {p['sidebar']}; }}

/* ── 날짜 / 제목 섹션 ───────────────────────── */
QWidget#NoteHeader {{
    background: transparent;
    border-bottom: 1px solid {p['border']};
}}
QLabel#DateLabel {{
    font-size: 13px;
    color: {p['ink_soft']};
    padding: 0 2px;
}}
QLineEdit#TitleInput {{
    font-family: {SERIF_CSS};
    font-size: 24px;
    color: {p['ink']};
    background: transparent;
    border: none;
    padding: 0 0 2px 0;
    selection-background-color: {p['accent_soft']};
    selection-color: {p['ink']};
}}
QLineEdit#TitleInput[empty="true"] {{ color: {p['ink_faint']}; }}
QWidget#Toolbar {{
    background: transparent;
    border-bottom: 1px solid {p['border']};
}}
/* 서식 버튼은 크기를 통일해서 한 줄이 고르게 보이도록 한다. */
QToolButton#FmtButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    color: {p['ink_soft']};
    padding: 0 7px;
    font-size: 12px;
    min-width: 16px;
    min-height: 26px;
}}
QToolButton#FmtButton:hover {{ background: {p['hover']}; color: {p['ink']}; }}
QToolButton#FmtButton:checked {{ background: {p['accent_soft']}; color: {p['accent']}; }}
QToolButton#FmtButton:pressed {{ background: {p['accent_soft']}; }}
QToolButton#FmtButton::menu-indicator {{ image: none; }}
QFrame#Sep {{ background: {p['border']}; max-width: 1px; }}

/* 저장 버튼. 저장할 게 있으면 진해져서 버튼만 봐도 미저장 상태를 알 수 있다. */
QToolButton#SaveButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    color: {p['ink_faint']};
    padding: 4px 10px;
    font-size: 12px;
}}
QToolButton#SaveButton:hover {{ background: {p['hover']}; color: {p['ink']}; }}
QToolButton#SaveButton[dirty="true"] {{
    background: {p['accent_soft']};
    border: 1px solid {p['border']};
    color: {p['accent']};
    font-weight: 600;
}}
QToolButton#SaveButton[dirty="true"]:hover {{ background: {p['hover']}; }}

/* ── 에디터 ─────────────────────────────────── */
QTextEdit#Editor {{
    background: {p['paper']};
    border: none;
    color: {p['ink']};
    selection-background-color: {p['accent_soft']};
    selection-color: {p['ink']};
}}

/* ── 상태 바 ────────────────────────────────── */
QLabel#StatusLabel {{ color: {p['ink_faint']}; font-size: 11px; }}
QPushButton#TodayButton {{
    background: transparent;
    border: 1px solid {p['border']};
    border-radius: 12px;
    color: {p['ink_soft']};
    padding: 4px 14px;
    font-size: 11px;
}}
QPushButton#TodayButton:hover {{ background: {p['hover']}; color: {p['ink']}; }}

/* ── 스크롤바 ───────────────────────────────── */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {p['border']}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {p['ink_faint']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0px; }}

QSplitter::handle {{ background: {p['border']}; width: 1px; }}

QMenu {{
    background: {p['paper']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 16px; border-radius: 5px; color: {p['ink']}; }}
QMenu::item:selected {{ background: {p['accent_soft']}; }}
"""
