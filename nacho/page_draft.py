"""Notion property/block 페이로드 빌더 + 사람용 미리보기."""


def build_properties(fields_cfg: dict, data: dict) -> dict:
    """data → Notion API properties 객체. 비어있는 값은 페이로드에서 제외."""
    f = fields_cfg
    props: dict = {}

    if data.get("title"):
        props[f["title"]] = {
            "title": [{"text": {"content": data["title"]}}]
        }
    if data.get("status"):
        props[f["status"]] = {"status": {"name": data["status"]}}
    if data.get("category"):
        props[f["category"]] = {"select": {"name": data["category"]}}
    if data.get("project"):
        props[f["project"]] = {"select": {"name": data["project"]}}
    if data.get("assignee"):
        assignees = data["assignee"] if isinstance(data["assignee"], list) else [data["assignee"]]
        props[f["assignee"]] = {
            "multi_select": [{"name": a} for a in assignees if a]
        }
    if data.get("start_date"):
        props[f["start_date"]] = {"date": {"start": data["start_date"]}}
    if data.get("due_date"):
        props[f["due_date"]] = {"date": {"start": data["due_date"]}}
    if data.get("link"):
        props[f["link"]] = {"url": data["link"]}
    if data.get("session_id") and f.get("session_id"):
        props[f["session_id"]] = {
            "rich_text": [{"text": {"content": data["session_id"]}}]
        }

    return props


# Notion API 제한: text.content는 2000자까지, 한 요청의 children은 100개까지.
RICH_TEXT_MAX_CHARS = 2000
MAX_CHILDREN_PER_REQUEST = 100


def _rich_text(line: str) -> list:
    """한 줄을 2000자 이하 조각들의 rich_text 배열로."""
    return [
        {"type": "text", "text": {"content": line[i:i + RICH_TEXT_MAX_CHARS]}}
        for i in range(0, len(line), RICH_TEXT_MAX_CHARS)
    ]


def build_body_blocks(markdown: str | None) -> list:
    """간단 변환 — 줄 단위로 paragraph 블록 (v1)."""
    if not markdown:
        return []
    blocks = []
    for line in markdown.split("\n"):
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _rich_text(line)},
        })
    return blocks


def chunk_blocks(blocks: list, size: int = MAX_CHILDREN_PER_REQUEST) -> list[list]:
    """children을 요청당 한도 이하 묶음으로 나눈다."""
    return [blocks[i:i + size] for i in range(0, len(blocks), size)]


def format_preview(data: dict) -> str:
    lines = ["=" * 60]
    lines.append(f"제목     : {data.get('title', '(없음)')}")
    for label, key in [
        ("상태", "status"),
        ("분류", "category"),
        ("프로젝트", "project"),
        ("시작일", "start_date"),
        ("마감일", "due_date"),
        ("링크", "link"),
    ]:
        v = data.get(key)
        if v:
            lines.append(f"{label:<7}: {v}")
    if data.get("assignee"):
        a = data["assignee"] if isinstance(data["assignee"], list) else [data["assignee"]]
        lines.append(f"{'담당자':<7}: {', '.join(a)}")
    if data.get("session_id"):
        lines.append(f"{'세션':<7}: {data['session_id']}")
    if data.get("body"):
        lines.append("")
        lines.append("본문:")
        lines.append(data["body"])
    lines.append("=" * 60)
    return "\n".join(lines)
