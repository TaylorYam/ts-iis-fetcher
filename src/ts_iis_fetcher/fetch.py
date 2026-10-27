"""依 TDCC 到公槽根目錄找說明書（_TS）與投資人須知（_IIS），複製到目的資料夾。

公槽的擺法：`<根目錄>\\<TDCC>\\<TDCC>_TS.pdf`、`<TDCC>_IIS.pdf`。
- 資料夾名稱剛好是 TDCC 優先；沒有時接受「以 TDCC 開頭」的資料夾（例：`029199990001 某某`），多個就不猜。
- 檔名剛好是 `<TDCC>_TS.pdf`／`<TDCC>_IIS.pdf`；資料夾第一層沒有時往下層找，找到多份就不猜。
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("TS", "IIS")
_CODE = re.compile(r"(?<!\d)\d{11,12}(?!\d)")
_FOLDER = re.compile(r"\d{12}(?!\d)")


def parse_tdccs(text: str) -> list[str]:
    """從貼上的文字取出 TDCC（12 位數字），保留順序、去重。

    11 位數字補回前導零：Excel 數字格式的儲存格複製出來會掉開頭的 0（例：029… → 29…）。
    """
    codes: list[str] = []
    for m in _CODE.finditer(text):
        code = m.group().zfill(12)
        if code not in codes:
            codes.append(code)
    return codes


@dataclass
class Lookup:
    tdcc: str
    folder: Path | None = None
    files: dict[str, Path] = field(default_factory=dict)  # 種類（TS／IIS）→ 公槽上的檔案
    problems: list[str] = field(default_factory=list)
    copied: list[str] = field(default_factory=list)  # 已複製的種類

    @property
    def ok(self) -> bool:
        return not self.problems and len(self.copied) == len(KINDS)

    def mark(self, kind: str) -> str:
        """結果表 TS／IIS 欄顯示的文字。"""
        if kind in self.copied:
            return "✓"
        if kind in self.files:
            return "未複製"
        return "缺"

    @property
    def status(self) -> str:
        return "完成" if self.ok else "；".join(self.problems)


def folders_by_code(root: Path) -> dict[str, list[Path]]:
    """根目錄第一層、名稱以 12 位數字開頭的資料夾 → 依那 12 碼分組（只列一次根目錄，公槽上比逐檔查快）。"""
    found: dict[str, list[Path]] = {}
    with os.scandir(root) as entries:
        for entry in entries:
            m = _FOLDER.match(entry.name)
            if m and entry.is_dir():
                found.setdefault(m.group(), []).append(Path(entry.path))
    return found


def locate(tdcc: str, folders: dict[str, list[Path]]) -> Lookup:
    found = Lookup(tdcc)
    candidates = folders.get(tdcc, [])
    exact = [p for p in candidates if p.name == tdcc]
    if exact:
        found.folder = exact[0]
    elif len(candidates) == 1:
        found.folder = candidates[0]
    elif candidates:
        found.problems.append("有多個資料夾：" + "、".join(p.name for p in candidates))
        return found
    else:
        found.problems.append("根目錄沒有這個 TDCC 資料夾")
        return found
    for kind in KINDS:
        hits = _find_file(found.folder, f"{tdcc}_{kind}.pdf")
        if len(hits) == 1:
            found.files[kind] = hits[0]
        elif hits:
            found.problems.append(f"{kind} 有 {len(hits)} 份")
        else:
            found.problems.append(f"找不到 {kind}")
    return found


def _find_file(folder: Path, name: str) -> list[Path]:
    direct = folder / name
    if direct.is_file():
        return [direct]
    wanted = name.lower()
    return sorted(p for p in folder.rglob("*") if p.name.lower() == wanted and p.is_file())


def copy_into(found: Lookup, dest: Path) -> None:
    """把找到的檔案複製到目的資料夾（同名覆蓋）；失敗記在 problems，不中斷整批。"""
    for kind, src in found.files.items():
        try:
            shutil.copy2(src, dest / src.name)
        except OSError as e:
            found.problems.append(f"{kind} 複製失敗：{e}")
        else:
            found.copied.append(kind)


def fetch(
    root: Path,
    tdccs: Iterable[str],
    dest: Path,
    on_each: Callable[[Lookup], None] | None = None,
) -> list[Lookup]:
    """逐檔找、逐檔複製；每處理完一檔呼叫 `on_each`（畫面用來即時更新）。根目錄讀不到時直接拋 OSError。"""
    folders = folders_by_code(root)
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    for tdcc in tdccs:
        found = locate(tdcc, folders)
        copy_into(found, dest)
        results.append(found)
        if on_each:
            on_each(found)
    return results
