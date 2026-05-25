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


def build_body_blocks(markdown: str | None) -> list:
    """간단 변환 — 줄 단위로 paragraph 블록 (v1)."""
    if not markdown:
        return []
    blocks = []
    for line in markdown.split("\n"):
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": line}}] if line else []
            },
        })
    return blocks


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
