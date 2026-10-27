"""公槽 TS／IIS 抓取視窗：貼上 TDCC → 依商品的根目錄找檔 → 複製到目的資料夾。"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import settings as store
from .fetch import KINDS, Lookup, fetch, parse_tdccs

FONT = ("Microsoft JhengHei UI", 10)


class App:
    def __init__(self, win: tk.Tk) -> None:
        self.win = win
        self.cfg = store.load()
        self.events: queue.Queue = queue.Queue()
        self.results: list[Lookup] = []
        self.running = False
        self.shown = ""  # 根目錄欄位目前顯示的是哪個商品

        win.title("公槽 TS／IIS 抓取")
        win.geometry("1000x620")
        win.option_add("*Font", FONT)
        ttk.Style().configure("Treeview", rowheight=24)
        win.columnconfigure(1, weight=1)
        win.rowconfigure(4, weight=1)

        ttk.Label(win, text="商品").grid(row=0, column=0, sticky="w", padx=8, pady=(10, 4))
        self.product = tk.StringVar(value=self.cfg.product)
        self.box = ttk.Combobox(win, textvariable=self.product, values=self.cfg.products, width=14)
        self.box.grid(row=0, column=1, sticky="w", pady=(10, 4))
        self.box.bind("<<ComboboxSelected>>", lambda _e: self._show_root())
        self.box.bind("<FocusOut>", lambda _e: self._show_root())

        ttk.Label(win, text="公槽根目錄").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.root_dir = tk.StringVar()
        ttk.Entry(win, textvariable=self.root_dir).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(win, text="選擇…", command=self._pick_root).grid(row=1, column=2, padx=8, pady=4)

        ttk.Label(win, text="複製到").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self.dest = tk.StringVar(value=self.cfg.dest)
        ttk.Entry(win, textvariable=self.dest).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Button(win, text="選擇…", command=self._pick_dest).grid(row=2, column=2, padx=8, pady=4)

        ttk.Label(win, text="TDCC（從庫存表整欄貼上即可，一行一個、空白或逗號分隔都可以）").grid(
            row=3, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 2)
        )
        body = ttk.Frame(win)
        body.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=8)
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
        foot.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=10)
        foot.columnconfigure(3, weight=1)
        self.start = ttk.Button(foot, text="開始抓取", command=self._start)
        self.start.grid(row=0, column=0)
        ttk.Button(foot, text="複製缺件的 TDCC", command=self._copy_missing).grid(row=0, column=1, padx=8)
        ttk.Button(foot, text="開啟目的資料夾", command=self._open_dest).grid(row=0, column=2)
        self.note = tk.StringVar(value="已辨識 0 檔")
        ttk.Label(foot, textvariable=self.note).grid(row=0, column=3, sticky="e")

        self._show_root()
        win.protocol("WM_DELETE_WINDOW", self._close)

    def _show_root(self) -> None:
        """換商品時先記下前一個商品畫面上的根目錄，再顯示新商品的。"""
        if self.shown:
            self.cfg.roots[self.shown] = self.root_dir.get().strip()
        self.shown = self.product.get().strip()
        self.root_dir.set(self.cfg.roots.get(self.shown, ""))

    def _remember(self) -> None:
        name = self.product.get().strip()
        if name:
            self.cfg.roots[name] = self.root_dir.get().strip()
            self.cfg.product = name
        self.cfg.dest = self.dest.get().strip()
        store.save(self.cfg)
        self.box.configure(values=self.cfg.products)  # 輸入的新商品加進下拉選單

    def _pick_root(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.root_dir.get() or None, title="選擇公槽根目錄")
        if folder:
            self.root_dir.set(str(Path(folder)))

    def _pick_dest(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.dest.get() or None, title="選擇要複製到哪個資料夾")
        if folder:
            self.dest.set(str(Path(folder)))

    def _on_text(self, _event: object) -> None:
        if self.text.edit_modified():
            self.note.set(f"已辨識 {len(parse_tdccs(self.text.get('1.0', 'end')))} 檔")
            self.text.edit_modified(False)

    def _start(self) -> None:
        if self.running:
            return
        tdccs = parse_tdccs(self.text.get("1.0", "end"))
        root, dest = self.root_dir.get().strip(), self.dest.get().strip()
        if not self.product.get().strip():
            return messagebox.showwarning("缺商品", "請先選商品（或輸入新商品名稱）。")
        if not tdccs:
            return messagebox.showwarning("沒有 TDCC", "貼上的內容裡找不到 12 位數字的 TDCC。")
        if not root or not Path(root).is_dir():
            return messagebox.showwarning("根目錄", "公槽根目錄不存在或讀不到，請重新選擇。")
        if not dest:
            return messagebox.showwarning("目的資料夾", "請選擇要複製到哪個資料夾。")
        if Path(dest).resolve() == Path(root).resolve():
            return messagebox.showwarning("目的資料夾", "目的資料夾不能是公槽根目錄。")
        self._remember()
        self.table.delete(*self.table.get_children())
        self.results = []
        self.running = True
        self.start.state(["disabled"])
        self.note.set(f"抓取中… 0／{len(tdccs)}")
        total = len(tdccs)

        def work() -> None:
            try:
                fetch(Path(root), tdccs, Path(dest), on_each=lambda f: self.events.put(("one", f, total)))
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
                self.note.set(f"抓取中… {len(self.results)}／{total}")
            elif kind == "error":
                messagebox.showerror("讀不到公槽", f"讀取根目錄失敗：{item}")
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
        dest = self.dest.get().strip()
        if dest and Path(dest).is_dir():
            os.startfile(dest)  # noqa: S606 — Windows 開資料夾

    def _close(self) -> None:
        self._remember()
        self.win.destroy()


def main() -> None:
    win = tk.Tk()
    App(win)
    win.mainloop()
