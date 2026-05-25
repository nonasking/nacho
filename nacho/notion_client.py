"""Notion REST API v1 — 최소 호출 셋."""
import requests
from .auth import load_token

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {load_token()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def get_database(db_id: str) -> dict:
    r = requests.get(f"{BASE_URL}/databases/{db_id}", headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


def create_page(db_id: str, properties: dict, children: list | None = None) -> dict:
    payload: dict = {"parent": {"database_id": db_id}, "properties": properties}
    if children:
        payload["children"] = children
    r = requests.post(f"{BASE_URL}/pages", headers=_headers(), json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def update_page(page_id: str, properties: dict | None = None, archived: bool | None = None) -> dict:
    payload: dict = {}
    if properties:
        payload["properties"] = properties
    if archived is not None:
        payload["archived"] = archived
    r = requests.patch(f"{BASE_URL}/pages/{page_id}", headers=_headers(), json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


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
        r = requests.post(
            f"{BASE_URL}/databases/{db_id}/query",
            headers=_headers(),
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        results.extend(data["results"])
        if not data.get("has_more") or not all_pages:
            break
        cursor = data["next_cursor"]
    return results


def get_page(page_id: str) -> dict:
    r = requests.get(f"{BASE_URL}/pages/{page_id}", headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


def get_block_children(block_id: str) -> list:
    r = requests.get(
        f"{BASE_URL}/blocks/{block_id}/children?page_size=100",
        headers=_headers(),
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["results"]


def append_block_children(block_id: str, children: list) -> dict:
    r = requests.patch(
        f"{BASE_URL}/blocks/{block_id}/children",
        headers=_headers(),
        json={"children": children},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()
