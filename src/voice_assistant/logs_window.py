from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from .config import PROJECT_ROOT
from .worker import LOG_PATH


def filter_log(text: str, level: str, search: str) -> str:
    lines = text.splitlines()
    if level != "ყველა":
        lines = [line for line in lines if f" {level} " in line]
    query = search.casefold().strip()
    if query:
        lines = [line for line in lines if query in line.casefold()]
    return "\n".join(lines[-5000:])


class LogsWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.level = tk.StringVar(value="ყველა")
        self.search = tk.StringVar()
        self.auto_refresh = tk.BooleanVar(value=True)
        self.status = tk.StringVar()
        self.last_signature: tuple[int, int] | None = None
        root.title("Gela — სისტემური ჟურნალი")
        root.geometry("980x650")
        root.minsize(720, 460)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self.search.trace_add("write", lambda *_: self.refresh(force=True))
        self.refresh(force=True)
        self._tick()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Label(toolbar, text="დონე:").pack(side="left")
        levels = ttk.Combobox(toolbar, textvariable=self.level, values=("ყველა", "INFO", "WARNING", "ERROR", "CRITICAL"), state="readonly", width=11)
        levels.pack(side="left", padx=(6, 14))
        levels.bind("<<ComboboxSelected>>", lambda event: self.refresh(force=True))
        ttk.Label(toolbar, text="ძიება:").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.search).pack(side="left", fill="x", expand=True, padx=(6, 14))
        ttk.Checkbutton(toolbar, text="ავტომატური განახლება", variable=self.auto_refresh).pack(side="left")
        ttk.Button(toolbar, text="განახლება", command=lambda: self.refresh(force=True)).pack(side="left", padx=(8, 0))

        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True)
        self.text = tk.Text(content, wrap="none", font=("Cascadia Mono", 10), state="disabled")
        yscroll = ttk.Scrollbar(content, orient="vertical", command=self.text.yview)
        xscroll = ttk.Scrollbar(content, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        ttk.Button(bottom, text="ჟურნალის საქაღალდე", command=lambda: os.startfile(LOG_PATH.parent)).pack(side="right")
        ttk.Button(bottom, text="ნედლი ფაილი Notepad-ში", command=self._open_raw).pack(side="right", padx=(0, 8))
        ttk.Button(bottom, text="დახურვა", command=self.root.destroy).pack(side="right", padx=(0, 8))

    def _open_raw(self) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.touch(exist_ok=True)
        subprocess.Popen(["notepad.exe", str(LOG_PATH)], close_fds=True)

    def refresh(self, force: bool = False) -> None:
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.touch(exist_ok=True)
            stat = LOG_PATH.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if not force and signature == self.last_signature:
                return
            raw = LOG_PATH.read_text(encoding="utf-8", errors="replace")
            shown = filter_log(raw, self.level.get(), self.search.get())
            self.text.configure(state="normal")
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", shown)
            self.text.configure(state="disabled")
            self.text.see(tk.END)
            self.last_signature = signature
            self.status.set(f"ნაჩვენებია {len(shown.splitlines())} ხაზი • ფაილის ზომა {stat.st_size / 1024:.1f} KB")
        except Exception as exc:
            self.status.set(f"ჟურნალი ვერ ჩაიტვირთა: {exc}")

    def _tick(self) -> None:
        if self.auto_refresh.get():
            self.refresh()
        self.root.after(1500, self._tick)


def main() -> int:
    root = tk.Tk()
    LogsWindow(root)
    if "--smoke" in sys.argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
