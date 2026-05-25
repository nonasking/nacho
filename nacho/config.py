"""config.yaml 로딩 + write_default (init 마법사가 사용)."""
import os
from pathlib import Path

import yaml

CONFIG_PATH = Path(
    os.environ.get("NACHO_CONFIG_PATH", Path.home() / ".config" / "nacho" / "config.yaml")
)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"설정 파일이 없습니다: {CONFIG_PATH}\n"
            "  nacho init  으로 마법사 실행하거나\n"
            "  config.example.yaml 을 ~/.config/nacho/config.yaml 로 복사."
        )
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f) or {}
    _validate(cfg)
    return cfg


def _validate(cfg: dict) -> None:
    n = cfg.get("notion") or {}
    if not n.get("database_id"):
        raise ValueError(f"{CONFIG_PATH}: notion.database_id 가 비었음")
    fields = n.get("fields") or {}
    if not fields.get("title"):
        raise ValueError(f"{CONFIG_PATH}: notion.fields.title 매핑 필요 (필수)")


def write_default(
    database_id: str,
    fields: dict,
    defaults: dict,
    status_categories: dict,
    force: bool = False,
) -> None:
    """nacho init 이 호출. dict → yaml 로 저장."""
    if CONFIG_PATH.exists() and not force:
        raise FileExistsError(f"이미 존재: {CONFIG_PATH}. force=True 로 덮어쓰기.")

    content_dict = {
        "notion": {
            "database_id": database_id,
            "fields": fields,
            "defaults": defaults,
            "status_categories": status_categories,
        },
        "auto_copy_url": True,
    }

    header = "# nacho 설정 — `nacho init` 으로 자동 생성. 수동 편집 가능.\n\n"
    body = yaml.dump(
        content_dict,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_PATH.parent, 0o700)
    CONFIG_PATH.write_text(header + body)
    os.chmod(CONFIG_PATH, 0o644)
