"""진행 일지 (status note) 섹션 헬퍼.

각 업무 DB 행의 본문에 '## 진행 일지' 섹션을 두고,
nacho note 호출 시 그 아래에 `- YYYY-MM-DD HH:MM: 메모` 형식 bullet 추가.
동시에 노션 DB 행의 '현황 요약' 필드에는 가장 최근 메모 한 줄을 덮어쓰기.
"""
from datetime import datetime

PROGRESS_HEADING = "## 진행 일지"


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def initial_section() -> str:
    """`nacho new` 시 본문에 prepend 할 초기 진행 일지 섹션."""
    return f"{PROGRESS_HEADING}\n- {now_stamp()}: (생성됨)"


def format_entry_text(text: str) -> str:
    """note 한 줄을 '2026-05-26 09:30: 내용' 형식으로 (앞 '- ' 없이)."""
    return f"{now_stamp()}: {text}"
