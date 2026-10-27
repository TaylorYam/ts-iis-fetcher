"""公槽 TS／IIS 抓取視窗：貼上 TDCC → 在根目錄底下找商品資料夾 → 複製到目的資料夾。"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import settings
from .fetch import KINDS, Lookup, fetch, parse_tdccs

TITLE = "公槽 TS／IIS 抓取"
FONT = ("Microsoft JhengHei UI", 10)


class FolderBar:
    """一列「標題｜路徑（唯讀）｜變更…」：跟 FCN Workflow 的根目錄一樣只能用按鈕改，避免打錯；選了就記住。"""

    def __init__(self, parent: tk.Misc, row: int, label: str, key: str, dialog_title: str, missing: str) -> None:
        self.key, self.dialog_title = key, dialog_title
        self.var = tk.StringVar(value=settings.load_folders().get(key, ""))
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(parent, textvariable=self.var, state="readonly").grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="變更…", command=self.change).grid(row=row, column=2, padx=8, pady=4)
        warning = ttk.Label(parent, text=missing, foreground="#B00020")

        def show_missing(*_args: object) -> None:
            if self.var.get().strip():
                warning.grid_remove()
            else:
                warning.grid(row=row, column=3, sticky="w", padx=(0, 8))

        self.var.trace_add("write", show_missing)
        show_missing()

    def change(self) -> None:
        chosen = filedialog.askdirectory(title=self.dialog_title, initialdir=self.var.get() or None, mustexist=True)
        if chosen:  # 按取消不動
            self.var.set(str(Path(chosen)))
            settings.remember(**{self.key: self.var.get()})

    def path(self) -> Path | None:
        text = self.var.get().strip()
        return Path(text) if text else None


class App:
    def __init__(self, win: tk.Tk) -> None:
        self.win = win
        self.events: queue.Queue = queue.Queue()
        self.results: list[Lookup] = []
        self.running = False

        win.title(TITLE)
        win.geometry("1000x620")
        win.option_add("*Font", FONT)
        ttk.Style().configure("Treeview", rowheight=24)
        win.columnconfigure(1, weight=1)
        win.rowconfigure(3, weight=1)

        self.root = FolderBar(win, 0, "根目錄", "root", "選擇商品資料夾所在的根目錄", "尚未設定")
        self.dest = FolderBar(win, 1, "複製到", "dest", "選擇要複製到哪個資料夾", "尚未設定")

        ttk.Label(win, text="TDCC（從庫存表整欄貼上即可，一行一個、空白或逗號分隔都可以）").grid(
            row=2, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 2)
        )
        body = ttk.Frame(win)
        body.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=8)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self.text = tk.Text(body, width=18, undo=True)
        self.text.grid(row=0, column=0, sticky="ns")
        self.text.bind("<<Modified>>", self._on_text)

        cols = ("tdcc", *KINDS, "status")
        self.table = ttk.Treeview(body, columns=cols, show="headings")
        for col, title, width in zip(cols, ("TDCC", "TS", "IIS", "狀態"), (130, 60, 60, 500)):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, anchor="w" if col in ("tdcc", "status") else "center")
        self.table.tag_configure("bad", foreground="#B00020")
        self.table.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        bar = ttk.Scrollbar(body, orient="vertical", command=self.table.yview)
        bar.grid(row=0, column=2, sticky="ns")
        self.table.configure(yscrollcommand=bar.set)

        foot = ttk.Frame(win)
        foot.grid(row=4, column=0, columnspan=4, sticky="ew", padx=8, pady=10)
        foot.columnconfigure(3, weight=1)
        self.start = ttk.Button(foot, text="開始抓取", command=self._start)
        self.start.grid(row=0, column=0)
        ttk.Button(foot, text="複製缺件的 TDCC", command=self._copy_missing).grid(row=0, column=1, padx=8)
        ttk.Button(foot, text="開啟目的資料夾", command=self._open_dest).grid(row=0, column=2)
        self.note = tk.StringVar(value="已辨識 0 檔")
        ttk.Label(foot, textvariable=self.note).grid(row=0, column=3, sticky="e")

    def _on_text(self, _event: object) -> None:
        if self.text.edit_modified():
            self.note.set(f"已辨識 {len(parse_tdccs(self.text.get('1.0', 'end')))} 檔")
            self.text.edit_modified(False)

    def _start(self) -> None:
        if self.running:
            return
        tdccs = parse_tdccs(self.text.get("1.0", "end"))
        root, dest = self.root.path(), self.dest.path()
        if root is None:
            return messagebox.showerror(TITLE, "請先按根目錄旁的「變更…」設定根目錄。")
        if dest is None:
            return messagebox.showerror(TITLE, "請先按「複製到」旁的「變更…」選擇目的資料夾。")
        if not tdccs:
            return messagebox.showerror(TITLE, "貼上的內容裡找不到 12 位數字的 TDCC。")
        if dest.resolve().is_relative_to(root.resolve()):
            return messagebox.showerror(TITLE, "目的資料夾不能在根目錄底下（會被當成商品資料夾搜尋）。")
        self.table.delete(*self.table.get_children())
        self.results = []
        self.running = True
        self.start.state(["disabled"])
        total = len(tdccs)
        self.note.set(f"搜尋根目錄中…（共 {total} 檔）")

        def work() -> None:
            try:
                fetch(root, tdccs, dest, on_each=lambda f: self.events.put(("one", f, total)))
            except OSError as e:
                self.events.put(("error", e, total))
            self.events.put(("done", None, total))

        threading.Thread(target=work, daemon=True).start()
        self.win.after(100, self._poll)

    def _poll(self) -> None:
        while True:
            try:
                kind, item, total = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "one":
                self.results.append(item)
                self.table.insert(
                    "", "end",
                    values=(item.tdcc, *(item.mark(k) for k in KINDS), item.status),
                    tags=() if item.ok else ("bad",),
                )
                self.note.set(f"複製中… {len(self.results)}／{total}")
            elif kind == "error":
                messagebox.showerror(TITLE, str(item))
            else:
                self.running = False
                self.start.state(["!disabled"])
                bad = sum(not r.ok for r in self.results)
                self.note.set(f"完成 {len(self.results) - bad}／{total}，缺件 {bad}")
                return
        self.win.after(100, self._poll)

    def _copy_missing(self) -> None:
        missing = [r.tdcc for r in self.results if not r.ok]
        self.win.clipboard_clear()
        self.win.clipboard_append("\n".join(missing))
        self.note.set(f"已複製 {len(missing)} 個缺件 TDCC")

    def _open_dest(self) -> None:
        dest = self.dest.path()
        if dest and dest.is_dir():
            os.startfile(dest)  # noqa: S606 — Windows 開資料夾


def main() -> None:
    win = tk.Tk()
    App(win)
    win.mainloop()
