"""현재 Claude Code session id 캡처 + Session 본문 섹션 빌더."""
from datetime import datetime
from pathlib import Path

SESSION_FILE = Path.home() / ".cache" / "nacho" / "current-session"


def get_current_session_id() -> str | None:
    """SessionStart hook 이 기록한 파일에서 읽기. 없으면 None."""
    if not SESSION_FILE.exists():
        return None
    val = SESSION_FILE.read_text().strip()
    return val or None


def build_session_section(session_id: str) -> str:
    """본문에 prepend 할 Session 섹션 markdown."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"## Session\n"
        f"- ID: `{session_id}`\n"
        f"- 재개: `claude --resume {session_id}`\n"
        f"- 시작: {now}\n"
    )
