from __future__ import annotations

import json
import sys
import tkinter as tk
from tkinter import ttk

from .config import PROJECT_ROOT
from .mobile_bridge import BRIDGE_STATUS_PATH, REGENERATE_REQUEST_PATH


class MobileConnectionWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.status = tk.StringVar(value="მობილური ხიდის მდგომარეობა მოწმდება…")
        self.address = tk.StringVar(value="—")
        self.code = tk.StringVar(value="— — — — — —")
        self.expiry = tk.StringVar(value="")

        root.title("Gela — მობილური კავშირი")
        root.geometry("590x430")
        root.minsize(520, 390)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self._refresh()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="მობილური კავშირი", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Gela Mobile დააკავშირეთ იმავე Wi-Fi ქსელიდან.",
            foreground="#666666",
        ).pack(anchor="w", pady=(4, 20))

        status_frame = ttk.LabelFrame(outer, text=" ხიდის მდგომარეობა ", padding=14)
        status_frame.pack(fill="x")
        ttk.Label(status_frame, textvariable=self.status, font=("Segoe UI", 11, "bold")).pack(anchor="w")

        details = ttk.Frame(outer)
        details.pack(fill="x", pady=(18, 0))
        ttk.Label(details, text="PC მისამართი", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        address_row = ttk.Frame(details)
        address_row.pack(fill="x", pady=(5, 15))
        ttk.Entry(address_row, textvariable=self.address, state="readonly", font=("Consolas", 13)).pack(side="left", fill="x", expand=True)
        ttk.Button(address_row, text="კოპირება", command=lambda: self._copy(self.address.get())).pack(side="left", padx=(8, 0))

        ttk.Label(details, text="ერთჯერადი დაკავშირების კოდი", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        code_row = ttk.Frame(details)
        code_row.pack(fill="x", pady=(5, 4))
        ttk.Label(code_row, textvariable=self.code, font=("Consolas", 25, "bold"), foreground="#c8392b").pack(side="left")
        ttk.Button(code_row, text="კოდის კოპირება", command=lambda: self._copy(self.code.get().replace(" ", ""))).pack(side="right")
        ttk.Label(details, textvariable=self.expiry, foreground="#777777").pack(anchor="w")

        controls = ttk.Frame(outer)
        controls.pack(fill="x", side="bottom", pady=(20, 0))
        ttk.Button(controls, text="ახალი კოდის შექმნა", command=self._regenerate).pack(side="left")
        ttk.Button(controls, text="დახურვა", command=self.root.destroy).pack(side="right")

    def _copy(self, value: str) -> None:
        if not value or value == "—":
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)

    def _regenerate(self) -> None:
        REGENERATE_REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGENERATE_REQUEST_PATH.touch()
        self.status.set("ახალი კოდი იქმნება…")

    def _refresh(self) -> None:
        try:
            payload = json.loads(BRIDGE_STATUS_PATH.read_text(encoding="utf-8"))
            running = bool(payload.get("running"))
            error = payload.get("error")
            addresses = payload.get("addresses") or []
            code = str(payload.get("pairing_code", ""))
            remaining = int(payload.get("remaining_seconds", 0))
            used = bool(payload.get("used"))
            self.status.set("● ჩართულია და ელოდება მობილურ კავშირს" if running else f"● გამორთულია{': ' + str(error) if error else ''}")
            self.address.set(str(addresses[0]) if addresses else "მისამართი ვერ მოიძებნა")
            self.code.set(" ".join(code) if code else "— — — — — —")
            if used:
                self.expiry.set("კოდი უკვე გამოყენებულია. ახალი მოწყობილობისთვის შექმენით ახალი კოდი.")
            elif remaining:
                self.expiry.set(f"კოდი მოქმედებს კიდევ {remaining // 60}:{remaining % 60:02d} წუთი")
            else:
                self.expiry.set("კოდის ვადა გასულია. შექმენით ახალი კოდი.")
        except (OSError, ValueError, json.JSONDecodeError):
            self.status.set("მობილური ხიდის ინფორმაცია ჯერ მიუწვდომელია")
        self.root.after(1000, self._refresh)


def main() -> int:
    root = tk.Tk()
    MobileConnectionWindow(root)
    if "--smoke" in sys.argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
