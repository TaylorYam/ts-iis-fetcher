"""本機記住上次選的根目錄與目的資料夾（`.local/settings.json`，不進 Git）；讀寫失敗一律當作沒有記錄，不影響使用。"""

from __future__ import annotations

import json
from pathlib import Path

LOCAL_FILE = Path(__file__).resolve().parents[2] / ".local" / "settings.json"


def load_folders(path: Path = LOCAL_FILE) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def remember(path: Path = LOCAL_FILE, **folders: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**load_folders(path), **folders}, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
