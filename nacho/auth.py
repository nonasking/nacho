"""credentials.json 에서 Notion integration token 로딩."""
import json
from pathlib import Path

CREDS_PATH = Path.home() / ".config" / "nacho" / "credentials.json"


def load_token() -> str:
    if not CREDS_PATH.exists():
        raise FileNotFoundError(
            f"credentials 없음: {CREDS_PATH}\n"
            "  mkdir -p ~/.config/nacho && chmod 700 ~/.config/nacho\n"
            "  echo '{\"token\": \"YOUR_TOKEN\"}' > ~/.config/nacho/credentials.json\n"
            "  chmod 600 ~/.config/nacho/credentials.json"
        )
    with open(CREDS_PATH) as f:
        data = json.load(f)
    token = data.get("token")
    if not token:
        raise ValueError(f"{CREDS_PATH} 에 'token' 키가 없음")
    return token
