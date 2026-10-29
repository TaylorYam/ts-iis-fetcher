"""依 TDCC 到公槽根目錄找說明書（_TS）與投資人須知（_IIS），複製到目的資料夾。

跟 FCN Workflow「準備」找商品資料夾的做法一樣：根目錄底下任何深度、名稱剛好等於 TDCC 的資料夾（只走一次樹），
找到多個同名資料夾就不猜。資料夾裡的檔名剛好是 `<TDCC>_TS.pdf`／`<TDCC>_IIS.pdf`；第一層沒有時往下層找，找到多份就不猜。
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")
KINDS = ("TS", "IIS")
_CODE = re.compile(r"(?<!\d)\d{11,12}(?!\d)")


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


def find_product_folders(root: Path, wanted: set[str]) -> tuple[dict[str, list[Path]], list[Path]]:
    """根目錄底下任何深度、名稱剛好等於 TDCC 的資料夾（只走一次樹），以及讀不到的資料夾。"""
    found: dict[str, list[Path]] = {}
    unreadable: list[Path] = []
    if not wanted:
        return found, unreadable
    for dirpath, dirnames, _ in os.walk(root, onerror=lambda e: unreadable.append(Path(e.filename))):
        dirnames.sort()
        for name in dirnames:
            if name in wanted:
                found.setdefault(name, []).append(Path(dirpath) / name)
    return found, unreadable


def pick_folder(folders: list[Path], unreadable: Sequence[Path] = ()) -> tuple[Path | None, str | None]:
    """唯一的商品資料夾；找不到或有多個同名資料夾時不猜，回傳原因。"""
    if not folders:
        reason = "找不到商品資料夾"
        if unreadable:
            reason += f"（搜尋時有 {len(unreadable)} 個資料夾讀不到，例如 {unreadable[0]}）"
        return None, reason
    if len(folders) > 1:
        return None, f"找到 {len(folders)} 個同名商品資料夾：" + "、".join(str(f) for f in folders)
    return folders[0], None


def locate(tdcc: str, folders: list[Path], unreadable: Sequence[Path] = ()) -> Lookup:
    found = Lookup(tdcc)
    found.folder, reason = pick_folder(folders, unreadable)
    if reason:
        found.problems.append(reason)
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
    """依 TDCC 抓 TS／IIS；每處理完一檔呼叫 `on_each`（畫面用來即時更新）。"""

    def one(tdcc: str, folders: list[Path], unreadable: Sequence[Path]) -> Lookup:
        found = locate(tdcc, folders, unreadable)
        copy_into(found, dest)
        return found

    return run_batch(root, tdccs, dest, one, on_each)


def run_batch(
    root: Path,
    tdccs: Iterable[str],
    dest: Path,
    one: Callable[[str, list[Path], Sequence[Path]], T],
    on_each: Callable[[T], None] | None = None,
) -> list[T]:
    """先走一次根目錄找商品資料夾，再逐檔交給 `one`（找檔＋複製）；每處理完一檔呼叫 `on_each`。"""
    codes = list(tdccs)
    if not root.is_dir():
        raise OSError(f"根目錄不存在或讀不到：{root}")
    folders, unreadable = find_product_folders(root, set(codes))
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    for tdcc in codes:
        found = one(tdcc, folders.get(tdcc, []), unreadable)
        results.append(found)
        if on_each:
            on_each(found)
    return results
