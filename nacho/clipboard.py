"""클립보드 헬퍼 — macOS pbpaste·pbcopy / Linux xclip|xsel.

읽기 용도: tako 가 새 Jira 티켓 만들면 URL 을 시스템 클립보드에 자동 복사한다.
nacho 는 그 직후 호출되면 클립보드에서 그 URL 을 읽어 노션 행의 `링크` 필드에 자동 연결.
쓰기 용도: nacho new 가 생성한 노션 행 URL 을 클립보드에 복사.
"""
import re
import subprocess
import sys

# 일반 URL
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
# Atlassian Cloud Jira 티켓 URL (https://*.atlassian.net/browse/KEY-123)
JIRA_URL_PATTERN = re.compile(r"https?://[^/]+\.atlassian\.net/browse/[A-Z][A-Z0-9_]*-\d+")


def read_clipboard() -> str:
    """현재 시스템 클립보드 텍스트. 도구 없거나 실패면 빈 문자열."""
    try:
        if sys.platform == "darwin":
            r = subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=2, check=False
            )
            return r.stdout if r.returncode == 0 else ""
        # Linux: xclip → xsel 순서로 시도
        for cmd in (
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "-b"],
        ):
            try:
                r = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=2, check=False
                )
                if r.returncode == 0:
                    return r.stdout
            except FileNotFoundError:
                continue
        return ""
    except (subprocess.SubprocessError, OSError):
        return ""


def copy_to_clipboard(text: str) -> bool:
    """텍스트를 시스템 클립보드에 복사. 성공하면 True, 도구 없거나 실패면 False."""
    if sys.platform == "darwin":
        commands = (["pbcopy"],)
    else:
        # Linux: xclip → xsel 순서로 시도
        commands = (["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"])
    for cmd in commands:
        try:
            r = subprocess.run(cmd, input=text.encode(), timeout=2, check=False)
            if r.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            continue
    return False


def find_url_in_clipboard() -> str | None:
    """클립보드에서 URL 추출. Jira URL 우선, 없으면 첫 일반 URL. 없으면 None."""
    text = read_clipboard().strip()
    if not text:
        return None
    m = JIRA_URL_PATTERN.search(text)
    if m:
        return m.group(0)
    m = URL_PATTERN.search(text)
    if m:
        return m.group(0)
    return None


def looks_like_jira(url: str) -> bool:
    return bool(JIRA_URL_PATTERN.search(url))
