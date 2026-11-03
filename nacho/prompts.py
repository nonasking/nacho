"""인터랙티브 입력 — `nacho new` 마법사."""
import sys
from datetime import date, timedelta

from . import clipboard as clip
from . import progress as prog
from . import schema as sch
from . import session as ses


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else default


def _read_multiline(prompt: str) -> str:
    print(f"{prompt} (입력 끝나면 Ctrl+D):")
    return sys.stdin.read().strip()


def _parse_date(s: str) -> str:
    s = (s or "").strip().lower()
    if not s:
        return ""
    today = date.today()
    if s in ("오늘", "today"):
        return today.isoformat()
    if s in ("내일", "tomorrow"):
        return (today + timedelta(days=1)).isoformat()
    if s in ("모레",):
        return (today + timedelta(days=2)).isoformat()
    return s


def _resolve_one(label: str, val: str, options: list[str]) -> str:
    """val 을 options 안에서 찾기. 정확 매칭 → 부분 매칭 (유일) → 에러."""
    if val in options:
        return val
    matches = [o for o in options if val.lower() in o.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"{label}: '{val}' 가 여러 옵션과 매칭됨 {matches}. 더 구체적으로."
        )
    raise ValueError(f"{label}: '{val}' 는 옵션에 없음. 가능: {options}")


def _ask_enum(label: str, options: list[str], default: str = "", allow_empty: bool = True) -> str:
    """옵션 중 하나를 번호 또는 이름으로 선택. 옵션 외 자유 입력 거부."""
    if not options:
        # schema 에서 옵션 못 가져온 비상 fallback — 자유 입력 허용
        return _ask(label, default)

    while True:
        print(f"{label}:")
        for i, o in enumerate(options, 1):
            mark = " ←기본" if o == default else ""
            print(f"  {i}) {o}{mark}")
        hint = f" [Enter = {default}]" if default else " [Enter = 비움]"
        val = input(f"번호 또는 이름{hint}: ").strip()

        if not val:
            if default:
                return default
            if allow_empty:
                return ""
            print("필수 항목입니다.")
            continue

        if val.isdigit():
            i = int(val)
            if 1 <= i <= len(options):
                return options[i - 1]
            print(f"번호는 1~{len(options)} 사이.")
            continue

        try:
            return _resolve_one(label, val, options)
        except ValueError as e:
            print(str(e))


def _ask_multi_enum(label: str, options: list[str], default: str = "") -> list[str]:
    """multi_select 필드 — 쉼표로 여러 개. 옵션 외 입력 거부."""
    if not options:
        return [default] if default else []

    while True:
        print(f"{label} (multi):")
        for i, o in enumerate(options, 1):
            mark = " ←기본" if o == default else ""
            print(f"  {i}) {o}{mark}")
        hint = f" [Enter = {default}]" if default else " [Enter = 비움]"
        val = input(f"번호/이름 (쉼표로 여러 개){hint}: ").strip()

        if not val:
            return [default] if default else []

        items = [p.strip() for p in val.split(",") if p.strip()]
        result = []
        try:
            for item in items:
                if item.isdigit():
                    i = int(item)
                    if not (1 <= i <= len(options)):
                        raise ValueError(f"번호 {i} 범위 밖 (1~{len(options)})")
                    result.append(options[i - 1])
                else:
                    result.append(_resolve_one(label, item, options))
            return result
        except ValueError as e:
            print(str(e))


def _resolve_link(cli_value: str | None) -> str:
    """링크 인자 처리.

    - CLI 인자가 명시되어 있으면 그대로 (특수값 'auto' 는 클립보드 추출).
    - 없으면 prompt → 빈 입력 시 클립보드에서 URL 발견하면 사용자 확인 후 사용.
    """
    if cli_value:
        if cli_value.strip().lower() == "auto":
            url = clip.find_url_in_clipboard()
            if url:
                tag = "Jira" if clip.looks_like_jira(url) else "URL"
                print(f"  (클립보드 {tag} 자동 추출: {url})")
                return url
            return ""
        return cli_value

    typed = _ask("관련 링크 (URL)")
    if typed:
        return typed

    url = clip.find_url_in_clipboard()
    if not url:
        return ""
    tag = "Jira" if clip.looks_like_jira(url) else "URL"
    ans = input(f"  클립보드에 {tag} 발견: {url}\n  링크로 사용? (Y/n): ").strip().lower()
    return url if ans != "n" else ""


def collect_new_page(cfg: dict, args, db_schema: dict) -> dict:
    """`nacho new` 입력 수집.

    기본은 인터랙티브 마법사. `--no-prompt` 면 `input()` 을 일절 띄우지 않고
    CLI 인자로 받은 값만 사용 — 안 준 항목은 빈 필드로 둔다 (제목만 필수).
    `--require-session` 이면 session_id 가 없을 때 에러 (Claude Code 경로용).
    """
    n = cfg["notion"]
    f = n["fields"]
    defaults = n.get("defaults", {})
    no_prompt = getattr(args, "no_prompt", False)

    data: dict = {}

    # 제목 (필수, 자유 입력)
    data["title"] = (args.title or "").strip() if no_prompt else (args.title or _ask("제목"))
    if not data["title"]:
        raise ValueError("제목은 필수입니다." + (" (--no-prompt 모드: --title 명시)" if no_prompt else ""))

    # 분류 / 프로젝트 / 상태 — select & status (매핑 없으면 건너뜀)
    for key, label in [
        ("category", "분류"),
        ("project", "프로젝트"),
        ("status", "상태"),
    ]:
        field_name = f.get(key)
        if not field_name:
            continue
        options = sch.extract_options(db_schema, field_name)
        cli_val = getattr(args, key)
        default = defaults.get(key, "") if key == "status" else ""
        if cli_val:
            data[key] = _resolve_one(label, cli_val, options) if options else cli_val
        elif no_prompt:
            data[key] = ""  # 안 준 인자는 빈 필드
        else:
            data[key] = _ask_enum(label, options, default=default)

    # 담당자 — multi_select (매핑 없으면 건너뜀)
    if f.get("assignee"):
        assignee_opts = sch.extract_options(db_schema, f["assignee"])
        if args.assignee:
            items = [a.strip() for a in args.assignee.split(",") if a.strip()]
            data["assignee"] = [
                _resolve_one("담당자", a, assignee_opts) if assignee_opts else a
                for a in items
            ]
        elif no_prompt:
            data["assignee"] = []  # 안 준 인자는 빈 필드
        else:
            data["assignee"] = _ask_multi_enum(
                "담당자", assignee_opts, default=defaults.get("assignee", "")
            )

    # 날짜 / 링크 (각 필드 매핑된 경우만)
    if f.get("start_date"):
        if no_prompt:
            data["start_date"] = _parse_date(args.start_date or "")
        else:
            data["start_date"] = _parse_date(args.start_date or _ask("시작일 (오늘/내일/YYYY-MM-DD)"))
    if f.get("due_date"):
        if no_prompt:
            data["due_date"] = _parse_date(args.due_date or "")
        else:
            data["due_date"] = _parse_date(args.due_date or _ask("마감일 (오늘/내일/YYYY-MM-DD)"))
    if f.get("link"):
        # no_prompt 면 명시한 인자만 사용 (클립보드 'auto' 는 허용, 빈 입력 프롬프트는 생략)
        data["link"] = _resolve_link(args.link) if (args.link or not no_prompt) else ""
    else:
        data["link"] = ""

    # 본문
    if args.body:
        data["body"] = args.body
    elif not no_prompt:
        ans = input("본문 추가? (y/N): ").strip().lower()
        if ans == "y":
            data["body"] = _read_multiline("본문 (마크다운)")

    # Session ID 자동 캡처 (CLI 인자 우선, 없으면 SessionStart hook 이 기록한 파일)
    session_id = getattr(args, "session_id", None) or ses.get_current_session_id()
    if getattr(args, "require_session", False) and not session_id:
        raise ValueError(
            "session_id 가 필수입니다 (--require-session). "
            "Claude Code 세션 밖이거나 hook 이 기록 안 됨 — --session-id 로 명시하세요."
        )
    session_section = ses.build_session_section(session_id) if session_id else ""
    if session_id:
        data["session_id"] = session_id

    # 진행 일지 초기 섹션은 무조건 본문에 추가 (이후 nacho note 가 여기 append)
    progress_section = prog.initial_section()

    parts = [s for s in (session_section, progress_section, data.get("body", "")) if s]
    data["body"] = "\n\n".join(parts) if parts else ""

    return data
