"""DB schema 에서 필드 옵션 추출."""


def extract_options(db_schema: dict, field_name: str) -> list[str]:
    """select / status / multi_select 필드의 option 이름 목록.

    필드가 없거나 enum 타입이 아니면 빈 리스트.
    """
    prop = db_schema.get("properties", {}).get(field_name)
    if not prop:
        return []
    t = prop.get("type")
    if t == "select":
        return [o["name"] for o in prop["select"]["options"]]
    if t == "status":
        return [o["name"] for o in prop["status"]["options"]]
    if t == "multi_select":
        return [o["name"] for o in prop["multi_select"]["options"]]
    return []
