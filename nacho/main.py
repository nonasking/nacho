"""nacho CLI 진입점."""
import argparse
import getpass
import json
import os
import re
import sys

from datetime import date, timedelta
from pathlib import Path

from . import notion_client as nc
from . import page_draft as pd
from . import progress as prog
from . import prompts
from .auth import CREDS_PATH
from .clipboard import copy_to_clipboard
from .config import CONFIG_PATH, load_config, write_default


# 필드 자동 매핑 사양 — (nacho 내부 키, 기대 타입, 이름 힌트 - 빈 리스트면 타입만으로 자동)
FIELD_SPEC = [
    ("title", "title", []),
    ("status", "status", []),
    ("category", "select", ["분류", "카테고리", "category", "type", "kind"]),
    ("project", "select", ["프로젝트", "project"]),
    ("assignee", "multi_select", ["담당자", "assignee", "owner"]),
    ("start_date", "date", ["시작", "start"]),
    ("due_date", "date", ["마감", "due", "deadline"]),
    ("link", "url", ["링크", "link", "url"]),
    ("session_id", "rich_text", ["session", "세션"]),
    ("status_note", "rich_text", ["현황", "status note", "summary", "note"]),
]


def cmd_new(args) -> int:
    cfg = load_config()
    n = cfg["notion"]

    # 옵션 검증용 schema 한 번 fetch
    db_schema = nc.get_database(n["database_id"])
    data = prompts.collect_new_page(cfg, args, db_schema)

    print()
    print(pd.format_preview(data))
    print()

    if not args.yes:
        ans = input("Notion 에 생성? (Y/n): ").strip().lower()
        if ans == "n":
            print("취소됨.")
            return 0

    properties = pd.build_properties(n["fields"], data)
    children = pd.build_body_blocks(data.get("body"))
    result = nc.create_page(
        n["database_id"], properties, children=children if children else None
    )

    url = result.get("url", "")
    print(f"✓ 생성됨: {url}")
    if cfg.get("auto_copy_url", True) and url:
        if copy_to_clipboard(url):
            print("  (URL 클립보드에 복사)")
    return 0


def cmd_list(args) -> int:
    cfg = load_config()
    n = cfg["notion"]
    f = n["fields"]

    filter_ = None
    status_field = f.get("status")
    if args.status and status_field:
        filter_ = {"property": status_field, "status": {"equals": args.status}}
    elif args.active and status_field:
        active_list = n.get("status_categories", {}).get("active") or []
        if active_list:
            filter_ = {
                "or": [
                    {"property": status_field, "status": {"equals": s}} for s in active_list
                ]
            }

    sorts = []
    if f.get("due_date"):
        sorts = [{"property": f["due_date"], "direction": "ascending"}]
    pages = nc.query_database(n["database_id"], filter_=filter_, sorts=sorts or None)

    if args.json:
        print(json.dumps(pages, ensure_ascii=False, indent=2))
        return 0

    if not pages:
        print("(결과 없음)")
        return 0

    for p in pages:
        props = p["properties"]
        title_field = props.get(f["title"], {}).get("title", [])
        title = title_field[0]["plain_text"] if title_field else "(제목 없음)"

        status_obj = props.get(f["status"], {}).get("status") or {}
        status = status_obj.get("name", "")

        due_obj = props.get(f["due_date"], {}).get("date") or {}
        due = due_obj.get("start", "")

        line = f"[{status:<8}] {title}"
        if due:
            line += f"  ⏳ ~{due}"
        print(line)
    return 0


def _pick_page_by_title(query: str, db_id: str, title_field: str) -> dict | None:
    """제목 부분 매칭으로 행 검색. 여러 개면 사용자에게 번호 선택."""
    filter_ = {"property": title_field, "title": {"contains": query}}
    pages = nc.query_database(db_id, filter_=filter_)
    if not pages:
        print(f"매칭 없음: '{query}'")
        return None
    if len(pages) == 1:
        return pages[0]
    print(f"{len(pages)}개 매칭:")
    for i, p in enumerate(pages, 1):
        tf = p["properties"].get(title_field, {}).get("title", [])
        title = tf[0]["plain_text"] if tf else "(제목 없음)"
        print(f"  {i}) {title}")
    try:
        idx = int(input("번호: ").strip()) - 1
    except (ValueError, KeyboardInterrupt):
        return None
    if not (0 <= idx < len(pages)):
        print("범위 밖.")
        return None
    return pages[idx]


def cmd_note(args) -> int:
    cfg = load_config()
    n = cfg["notion"]
    f = n["fields"]

    note_field = f.get("status_note")
    if not note_field:
        print("config 에 fields.status_note 매핑이 없음.")
        return 1

    page = _pick_page_by_title(args.query, n["database_id"], f["title"])
    if not page:
        return 1
    page_id = page["id"]

    entry_text = prog.format_entry_text(args.note)

    # 1) 본문 '## 진행 일지' 섹션 끝에 bullet 삽입 (섹션 없으면 페이지 맨 끝)
    anchor = prog.find_append_anchor(nc.get_block_children(page_id))
    nc.append_block_children(
        page_id,
        [{
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": entry_text}}]
            },
        }],
        after=anchor,
    )

    # 2) '현황 요약' 필드 덮어쓰기
    nc.update_page(
        page_id,
        properties={
            note_field: {"rich_text": [{"text": {"content": args.note}}]}
        },
    )

    tf = page["properties"].get(f["title"], {}).get("title", [])
    title = tf[0]["plain_text"] if tf else "(제목 없음)"
    print(f"✓ '{title}' 진행 일지에 추가:")
    print(f"  - {entry_text}")
    return 0


def cmd_brief(args) -> int:
    cfg = load_config()
    n = cfg["notion"]
    f = n["fields"]

    today = date.today()
    week_later = (today + timedelta(days=7)).isoformat()

    status_field = f.get("status")
    active_statuses = n.get("status_categories", {}).get("active") or []
    filter_ = None
    if status_field and active_statuses:
        filter_ = {
            "or": [
                {"property": status_field, "status": {"equals": s}}
                for s in active_statuses
            ]
        }
    pages = nc.query_database(n["database_id"], filter_=filter_)

    urgent = []
    in_progress = []
    waiting = []

    for p in pages:
        props = p["properties"]
        tf = props.get(f["title"], {}).get("title", [])
        title = tf[0]["plain_text"] if tf else "(제목 없음)"

        status_obj = props.get(f["status"], {}).get("status") or {}
        status = status_obj.get("name", "")

        due_obj = props.get(f["due_date"], {}).get("date") or {}
        due = due_obj.get("start", "") if due_obj else ""

        project_obj = props.get(f["project"], {}).get("select") or {}
        project = project_obj.get("name", "") if project_obj else ""

        note_field = f.get("status_note")
        note = ""
        if note_field:
            note_block = props.get(note_field, {}).get("rich_text", [])
            note = note_block[0]["plain_text"] if note_block else ""

        item = {"title": title, "status": status, "due": due, "note": note, "project": project}

        if status in ("의사결정 대기", "보류"):
            waiting.append(item)
        elif due and due <= week_later:
            urgent.append(item)
        else:
            in_progress.append(item)

    urgent.sort(key=lambda x: x["due"] or "")

    def d_day(due_str: str) -> str:
        if not due_str:
            return ""
        try:
            d = (date.fromisoformat(due_str) - today).days
        except ValueError:
            return ""
        if d > 0:
            return f" (D-{d})"
        if d == 0:
            return " (D-day)"
        return f" (D+{abs(d)})"

    lines = [f"=== {today.isoformat()} 브리핑 ==="]

    def proj_prefix(it: dict) -> str:
        return f"[{it['project']}] " if it.get("project") else ""

    if urgent:
        lines += ["", "🔥 마감 임박 (~7일)"]
        for it in urgent:
            line = f"- {proj_prefix(it)}{it['title']}{d_day(it['due'])}"
            if it["note"]:
                line += f": {it['note']}"
            lines.append(line)

    if in_progress:
        lines += ["", "📝 진행 중"]
        for it in in_progress:
            line = f"- {proj_prefix(it)}{it['title']}"
            if it["note"]:
                line += f": {it['note']}"
            if it["due"]:
                line += f"  (~{it['due']})"
            lines.append(line)

    if waiting:
        lines += ["", "⏸️ 대기 / 보류"]
        for it in waiting:
            line = f"- {proj_prefix(it)}[{it['status']}] {it['title']}"
            if it["note"]:
                line += f": {it['note']}"
            lines.append(line)

    if not (urgent or in_progress or waiting):
        lines += ["", "(활성 업무 없음)"]

    output = "\n".join(lines)

    if args.to_file:
        path = Path(args.to_file).expanduser()
        path.write_text(output + "\n")
        print(f"✓ 저장됨: {path}")
    else:
        print(output)
    return 0


def cmd_resume(args) -> int:
    cfg = load_config()
    n = cfg["notion"]
    f = n["fields"]

    sid_key = f.get("session_id")
    if not sid_key:
        print("config 에 fields.session_id 매핑이 없음.")
        return 1

    page = _pick_page_by_title(args.query, n["database_id"], f["title"])
    if not page:
        return 1

    sid_field = page["properties"].get(sid_key, {}).get("rich_text", [])
    if not sid_field:
        print("이 행에 session_id 가 비어있음.")
        return 1
    session_id = sid_field[0]["plain_text"]

    if args.exec:
        os.execvp("claude", ["claude", "--resume", session_id])
    else:
        print(f"claude --resume {session_id}")
    return 0


def _auto_map_fields(properties: dict) -> dict:
    """DB schema 의 properties → nacho 내부 키 자동 매핑.

    각 키마다 (기대 타입 일치 + 이름 힌트 매칭). 단일 매칭이면 자동, 여러 개면 첫 매칭.
    매칭 없으면 빈 문자열 — 해당 nacho 기능 비활성.
    """
    mapping: dict = {}
    used: set = set()

    for key, expected_type, hints in FIELD_SPEC:
        candidates = []
        for prop_name, prop in properties.items():
            if prop_name in used:
                continue
            if prop.get("type") != expected_type:
                continue
            if not hints:
                candidates.append(prop_name)
            else:
                name_lower = prop_name.lower()
                if any(h.lower() in name_lower for h in hints):
                    candidates.append(prop_name)
        if candidates:
            mapping[key] = candidates[0]
            used.add(candidates[0])
        else:
            mapping[key] = ""
    return mapping


def cmd_init(args) -> int:
    """대화형 셋업 마법사 — Notion token + DB URL + schema 자동 매핑."""
    print("=" * 60)
    print(" nacho init — Notion DB 자동화 셋업")
    print("=" * 60)
    print()

    if (CONFIG_PATH.exists() or CREDS_PATH.exists()) and not args.force:
        print("이미 셋업되어 있음:")
        if CONFIG_PATH.exists():
            print(f"  {CONFIG_PATH}")
        if CREDS_PATH.exists():
            print(f"  {CREDS_PATH}")
        print("덮어쓰려면 --force")
        return 1

    # 1. Token
    print("[1/5] Notion Integration Token")
    print("  Integration 생성: https://www.notion.so/my-integrations")
    print("  Capabilities: Read content / Update content / Insert content")
    print("  Type: Internal")
    print()
    token = getpass.getpass("Token (입력 시 화면에 안 보임): ").strip()
    if not token:
        print("Token 없음 — 중단.")
        return 1
    CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(CREDS_PATH.parent, 0o700)
    CREDS_PATH.write_text(json.dumps({"token": token}))
    os.chmod(CREDS_PATH, 0o600)
    print(f"  ✓ {CREDS_PATH}")
    print()

    # 2. DB URL → DB ID
    print("[2/5] 업무 DB URL")
    print("  노션 DB 페이지 우상단 Share → Copy link")
    print("  주의: 사용 전에 DB 의 ... → Connections 에 Integration 추가해놔야 함")
    print()
    db_id = ""
    while not db_id:
        url = input("DB URL: ").strip()
        m = re.search(r"([a-f0-9]{32})", url.replace("-", ""))
        if not m:
            print("  유효한 DB ID 못 찾음 (32자 hex). 다시 입력.")
            continue
        raw = m.group(1)
        db_id = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    print(f"  ✓ DB ID: {db_id}")
    print()

    # 3. Schema 조회
    print("[3/5] DB schema 조회")
    try:
        db = nc.get_database(db_id)
    except Exception as e:
        print(f"  실패: {e}")
        print("  Integration 이 DB 에 권한 있는지 확인 (DB 페이지 ... → Connections).")
        return 1
    title_block = db.get("title", [])
    db_title = title_block[0].get("plain_text", "(이름 없음)") if title_block else "(이름 없음)"
    print(f"  DB: {db_title}")

    properties = db.get("properties", {})

    # 4. 자동 매핑 + 사용자 확인
    print()
    print("[4/5] 필드 자동 매핑")
    mapping = _auto_map_fields(properties)
    for key, val in mapping.items():
        marker = "←" if val else "(매칭 없음)"
        print(f"  {key:12} → {val:20} {marker}")
    print()
    ans = input("이대로 저장? (Y / n 으로 yaml 직접 편집 안내): ").strip().lower()
    if ans == "n":
        print(f"  → {CONFIG_PATH} 저장 후 본인이 편집해주세요.")

    # status_categories 자동 분류 (Notion status group)
    active: list = []
    inactive: list = []
    status_field = mapping.get("status")
    if status_field:
        status_prop = properties.get(status_field, {}).get("status", {})
        groups = status_prop.get("groups", [])
        options = status_prop.get("options", [])
        opt_by_id = {o["id"]: o["name"] for o in options}
        for g in groups:
            gname = g.get("name", "").lower()
            names = [opt_by_id[oid] for oid in g.get("option_ids", []) if oid in opt_by_id]
            if "complete" in gname or "done" in gname or "완료" in gname:
                inactive.extend(names)
            else:
                active.extend(names)

    # 5. 기본값
    print()
    print("[5/5] 기본값")
    default_status = active[0] if active else ""
    if default_status:
        ans = input(f"기본 상태 [{default_status}]: ").strip()
        if ans:
            default_status = ans
    default_assignee = input("기본 담당자 (옵션, Enter=비움): ").strip()

    # 저장
    write_default(
        database_id=db_id,
        fields=mapping,
        defaults={"status": default_status, "assignee": default_assignee},
        status_categories={"active": active, "inactive": inactive},
        force=True,
    )
    print()
    print(f"  ✓ {CONFIG_PATH}")
    print()
    print("완료. 테스트:")
    print("  nacho list --active")
    print("  nacho new")
    return 0


def run() -> None:
    parser = argparse.ArgumentParser(prog="nacho", description="Notion DB 자동화 도구")
    sub = parser.add_subparsers(dest="cmd")

    p_new = sub.add_parser("new", help="새 행 생성")
    p_new.add_argument("--title")
    p_new.add_argument("--category")
    p_new.add_argument("--project")
    p_new.add_argument("--status")
    p_new.add_argument("--assignee")
    p_new.add_argument("--start-date", dest="start_date")
    p_new.add_argument("--due-date", dest="due_date")
    p_new.add_argument(
        "--link",
        help="URL. 'auto' 로 주면 시스템 클립보드에서 자동 추출 (Jira URL 우선)",
    )
    p_new.add_argument("--body")
    p_new.add_argument("--session-id", dest="session_id",
                       help="Claude 세션 ID (지정 안 하면 SessionStart hook 파일에서 자동)")
    p_new.add_argument("--yes", "-y", action="store_true")
    p_new.set_defaults(func=cmd_new)

    p_list = sub.add_parser("list", help="행 조회")
    p_list.add_argument("--status", help="특정 상태만 (예: '진행 중')")
    p_list.add_argument(
        "--active",
        action="store_true",
        help="활성 상태(시작 전/진행 중/의사결정 대기/배포 대기) 만",
    )
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_init = sub.add_parser("init", help="설정 마법사")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_resume = sub.add_parser(
        "resume",
        help="노션 행에서 session_id 꺼내 claude --resume 명령 출력/실행",
    )
    p_resume.add_argument("query", help="제목 검색어 (부분 매칭)")
    p_resume.add_argument(
        "--exec", action="store_true",
        help="명령 출력만 하지 말고 직접 claude --resume 실행",
    )
    p_resume.set_defaults(func=cmd_resume)

    p_note = sub.add_parser(
        "note",
        help="업무 진행 일지에 한 줄 추가 + 현황 요약 필드 갱신",
    )
    p_note.add_argument("query", help="업무 제목 검색어 (부분 매칭)")
    p_note.add_argument("note", help="기록할 메모 한 줄")
    p_note.set_defaults(func=cmd_note)

    p_brief = sub.add_parser(
        "brief",
        help="활성 업무 브리핑 (마감 임박 / 진행 중 / 대기)",
    )
    p_brief.add_argument(
        "--to-file",
        help="파일로 저장 (예: ~/Desktop/today-brief.md). 미지정 시 stdout",
    )
    p_brief.set_defaults(func=cmd_brief)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return
    try:
        rc = args.func(args) or 0
    except nc.NotionApiError as e:
        print(f"오류: {e}", file=sys.stderr)
        rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    run()
