"""商品清單與各商品的公槽根目錄。

- `config/products.toml`（進 Git）：商品清單與預設根目錄。
- `.local/settings.json`（不進 Git）：在畫面上改過的根目錄、上次選的商品與目的資料夾，優先於預設值。
讀寫本機設定失敗一律當作沒有記錄，不影響使用。
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
PRODUCTS_FILE = APP_ROOT / "config" / "products.toml"
LOCAL_FILE = APP_ROOT / ".local" / "settings.json"


@dataclass
class Settings:
    roots: dict[str, str] = field(default_factory=dict)  # 商品 → 根目錄
    product: str = ""
    dest: str = ""

    @property
    def products(self) -> list[str]:
        return list(self.roots)


def load(products_file: Path = PRODUCTS_FILE, local_file: Path = LOCAL_FILE) -> Settings:
    try:
        defaults = tomllib.loads(products_file.read_text(encoding="utf-8")).get("roots", {})
    except (OSError, ValueError):
        defaults = {}
    local = _read_json(local_file)
    roots = {str(k): str(v) for k, v in defaults.items()}
    saved = local.get("roots")
    if isinstance(saved, dict):
        roots.update({str(k): str(v) for k, v in saved.items() if isinstance(v, str)})
    product = local.get("product") if isinstance(local.get("product"), str) else ""
    dest = local.get("dest") if isinstance(local.get("dest"), str) else ""
    return Settings(roots, product or next(iter(roots), ""), dest)


def save(settings: Settings, local_file: Path = LOCAL_FILE) -> None:
    data = {"roots": settings.roots, "product": settings.product, "dest": settings.dest}
    try:
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
