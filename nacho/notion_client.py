"""Notion REST API v1 — 최소 호출 셋.

세션 기반 클라이언트. 네트워크 끊김만 짧은 백오프로 1회 재시도하고,
의미 있는 실패(401/403/404/429/5xx)는 상태코드별 안내 메시지를 담은
NotionApiError 로 즉시 보고 — main.py 가 traceback 없이 그대로 출력.
"""
import time

import requests

from .auth import load_token

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"
TIMEOUT = 20
RETRY_BACKOFF = 1.0


class NotionApiError(Exception):
    """사용자에게 그대로 보여줄 수 있는 Notion API 오류."""


_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({
            "Authorization": f"Bearer {load_token()}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        })
        _session = s
    return _session


def _request(method: str, path: str, *, json: dict | None = None) -> dict:
    """공통 요청 래퍼 — 연결 오류만 재시도, 4xx/5xx 는 NotionApiError."""
    url = f"{BASE_URL}/{path.lstrip('/')}"
    for attempt in (1, 2):
        try:
            r = _get_session().request(method, url, json=json, timeout=TIMEOUT)
            break
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == 2:
                raise NotionApiError(f"네트워크 오류 (재시도 실패): {exc}") from exc
            time.sleep(RETRY_BACKOFF)
    if r.status_code >= 400:
        raise NotionApiError(_format_error(r))
    return r.json()


def _format_error(resp: requests.Response) -> str:
    """상태코드 → 조치 가능한 안내 메시지 (README Troubleshooting 과 동일 톤)."""
    code = resp.status_code
    try:
        detail = resp.json().get("message", "")
    except ValueError:
        detail = (resp.text or "").strip()
    detail = (detail or "").strip()[:300]
    suffix = f" 상세: {detail}" if detail else ""

    if code == 400:
        return (
            "400 잘못된 요청 (validation error). "
            "~/.config/nacho/config.yaml 의 fields 매핑이 DB schema 와 맞는지 확인 "
            f"(nacho init --force 로 재설정 가능).{suffix}"
        )
    if code == 401:
        return "401 인증 실패 (unauthorized). 토큰 만료/오입력 — nacho init --force 로 재입력."
    if code == 403:
        return (
            "403 권한 없음. Integration capabilities "
            "(Read/Update/Insert content) 확인."
        )
    if code == 404:
        return (
            "404 찾을 수 없음 (database/page not found). "
            "Integration 이 해당 DB 에 연결됐는지 확인 (DB 페이지 ... → Connections)."
        )
    if code == 429:
        return "429 요청 한도 초과 (rate limited). 잠시 후 다시 시도."
    if 500 <= code < 600:
        return f"{code} Notion 서버 오류. 잠시 후 다시 시도.{suffix}"
    return f"{code} 예상치 못한 응답.{suffix}"


def get_database(db_id: str) -> dict:
    return _request("GET", f"databases/{db_id}")


def create_page(db_id: str, properties: dict, children: list | None = None) -> dict:
    payload: dict = {"parent": {"database_id": db_id}, "properties": properties}
    if children:
        payload["children"] = children
    return _request("POST", "pages", json=payload)


def update_page(page_id: str, properties: dict | None = None, archived: bool | None = None) -> dict:
    payload: dict = {}
    if properties:
        payload["properties"] = properties
    if archived is not None:
        payload["archived"] = archived
    return _request("PATCH", f"pages/{page_id}", json=payload)


def query_database(
    db_id: str,
    filter_: dict | None = None,
    sorts: list | None = None,
    page_size: int = 100,
    all_pages: bool = True,
) -> list:
    """필요한 만큼 페이지네이션 자동 반복."""
    payload: dict = {"page_size": page_size}
    if filter_:
        payload["filter"] = filter_
    if sorts:
        payload["sorts"] = sorts

    results = []
    cursor = None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        data = _request("POST", f"databases/{db_id}/query", json=payload)
        results.extend(data["results"])
        if not data.get("has_more") or not all_pages:
            break
        cursor = data["next_cursor"]
    return results


def get_page(page_id: str) -> dict:
    return _request("GET", f"pages/{page_id}")


def get_block_children(block_id: str) -> list:
    """블록의 children 전체 (페이지네이션 자동 반복)."""
    results = []
    cursor = None
    while True:
        path = f"blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        data = _request("GET", path)
        results.extend(data["results"])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return results


def append_block_children(block_id: str, children: list, after: str | None = None) -> dict:
    """children 추가. after 에 블록 id 를 주면 그 블록 바로 뒤에 삽입."""
    payload: dict = {"children": children}
    if after:
        payload["after"] = after
    return _request("PATCH", f"blocks/{block_id}/children", json=payload)
