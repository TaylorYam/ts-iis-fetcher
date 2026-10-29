"""依 TDCC 到商品資料夾找檔名含「Order」的 Outlook 信件（.msg），複製到目的資料夾。

商品資料夾的找法跟 TS／IIS 一樣（見 fetch.py）。資料夾裡任何深度、副檔名 .msg 且檔名含 Order（大小寫不拘）的都算，
可以有很多封，全部複製。檔名沒有 TDCC 的，複製時前面補 `<TDCC>_`，免得不同商品的同名信件互相覆蓋；
同一檔的資料夾裡有同名信件（放在不同子資料夾）時不猜，列為缺件。
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .fetch import pick_folder, run_batch

KINDS = ("Order",)


@dataclass
class OrderLookup:
    tdcc: str
    folder: Path | None = None
    files: list[Path] = field(default_factory=list)  # 公槽上要複製的信件
    problems: list[str] = field(default_factory=list)
    copied: list[Path] = field(default_factory=list)  # 複製到目的資料夾後的檔案

    @property
    def ok(self) -> bool:
        return not self.problems and len(self.copied) == len(self.files)

    def mark(self, _kind: str = "Order") -> str:
        """結果表 Order 欄顯示的文字。"""
        return f"{len(self.copied)} 封" if self.copied else "缺"

    @property
    def status(self) -> str:
        return "完成" if self.ok else "；".join(self.problems)


def is_order_mail(path: Path) -> bool:
    return path.suffix.lower() == ".msg" and "order" in path.stem.lower()


def dest_name(tdcc: str, src: Path) -> str:
    return src.name if tdcc in src.name else f"{tdcc}_{src.name}"


def locate_orders(tdcc: str, folders: list[Path], unreadable: Sequence[Path] = ()) -> OrderLookup:
    found = OrderLookup(tdcc)
    found.folder, reason = pick_folder(folders, unreadable)
    if reason:
        found.problems.append(reason)
        return found
    hits = sorted(p for p in found.folder.rglob("*") if is_order_mail(p) and p.is_file())
    if not hits:
        found.problems.append("找不到 Order 信")
    by_name: dict[str, list[Path]] = {}
    for p in hits:
        by_name.setdefault(dest_name(tdcc, p).lower(), []).append(p)
    for same in by_name.values():
        if len(same) == 1:
            found.files.append(same[0])
        else:
            found.problems.append(f"「{same[0].name}」有 {len(same)} 封同名")
    return found


def copy_orders(found: OrderLookup, dest: Path) -> None:
    """把找到的信件複製到目的資料夾（同名覆蓋）；失敗記在 problems，不中斷整批。"""
    for src in found.files:
        target = dest / dest_name(found.tdcc, src)
        try:
            shutil.copy2(src, target)
        except OSError as e:
            found.problems.append(f"{src.name} 複製失敗：{e}")
        else:
            found.copied.append(target)


def fetch_orders(
    root: Path,
    tdccs: Iterable[str],
    dest: Path,
    on_each: Callable[[OrderLookup], None] | None = None,
) -> list[OrderLookup]:
    """依 TDCC 抓 Order 信；每處理完一檔呼叫 `on_each`（畫面用來即時更新）。"""

    def one(tdcc: str, folders: list[Path], unreadable: Sequence[Path]) -> OrderLookup:
        found = locate_orders(tdcc, folders, unreadable)
        copy_orders(found, dest)
        return found

    return run_batch(root, tdccs, dest, one, on_each)
