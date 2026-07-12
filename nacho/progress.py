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


# --- '## 진행 일지' 섹션 위치 찾기 (nacho note 삽입 지점) -------------------

HEADING_TEXT = PROGRESS_HEADING.lstrip("#").strip()  # "진행 일지"


def _block_text(block: dict) -> str:
    btype = block.get("type", "")
    rich = block.get(btype, {}).get("rich_text", [])
    return "".join(r.get("plain_text", "") for r in rich).strip()


def _is_heading(block: dict) -> bool:
    """실제 heading_* 블록, 또는 build_body_blocks 가 만드는 '#...' paragraph."""
    btype = block.get("type", "")
    if btype.startswith("heading_"):
        return True
    return btype == "paragraph" and _block_text(block).startswith("#")


def _is_progress_heading(block: dict) -> bool:
    return _is_heading(block) and _block_text(block).lstrip("#").strip() == HEADING_TEXT


def find_append_anchor(blocks: list) -> str | None:
    """'## 진행 일지' 섹션 마지막 블록의 id.

    nacho note 가 append_block_children(after=<이 id>) 로 섹션 끝에 삽입.
    섹션 헤딩이 없으면 None — 호출자가 페이지 끝 append 로 폴백.
    (blocks = 페이지 top-level children, API 응답 그대로.)
    """
    anchor = None
    for block in blocks:
        if anchor is None:
            if _is_progress_heading(block):
                anchor = block.get("id")
            continue
        if _is_heading(block):  # 다음 섹션 시작 → 여기까지가 진행 일지
            break
        anchor = block.get("id")
    return anchor
