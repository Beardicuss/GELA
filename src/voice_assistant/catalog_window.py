from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .config import PROJECT_ROOT
from .voice_readiness import STATUS_LABELS, VoiceReadiness, analyze_voice_readiness, readiness_counts


FILTER_LABELS = {
    "ყველა სტატუსი": None,
    "ქართული + English": "both_ready",
    "ქართული მზადაა": "ka_ready",
    "English მზადაა": "en_ready",
    "არასწორი ხმოვანი სახელი": "invalid",
    "ხმოვანი სახელი არ აქვს": "unconfigured",
}


class CatalogWindow:
    def __init__(self, root: tk.Tk, *, analyze: bool = True) -> None:
        self.root = root
        self.records: list[VoiceReadiness] = []
        self.search = tk.StringVar()
        self.status_filter = tk.StringVar(value=next(iter(FILTER_LABELS)))
        self.summary = tk.StringVar(value="ხმოვანი მზადყოფნა მოწმდება…")

        root.title("Gela — აპლიკაციების ხმოვანი მზადყოფნა")
        root.geometry("1120x700")
        root.minsize(860, 540)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self.search.trace_add("write", lambda *_: self._render())
        self.status_filter.trace_add("write", lambda *_: self._render())
        if analyze:
            self._refresh()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text="აპლიკაციების ხმოვანი მზადყოფნა",
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Omnilingual ASR ბრძანებებს თავისუფალი ლექსიკით ამოიცნობს. "
                "აქ ნაჩვენებია აპლიკაციებისთვის მინიჭებული ქართული და ინგლისური ხმოვანი სახელები."
            ),
            wraplength=1050,
        ).pack(anchor="w", pady=(4, 12))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 10))
        ttk.Label(controls, text="ძიება").pack(side="left")
        ttk.Entry(controls, textvariable=self.search, width=34).pack(side="left", padx=(8, 14))
        ttk.Label(controls, text="სტატუსი").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.status_filter,
            values=list(FILTER_LABELS),
            state="readonly",
            width=30,
        ).pack(side="left", padx=(8, 0))
        self.refresh_button = ttk.Button(controls, text="ხელახლა შემოწმება", command=self._refresh)
        self.refresh_button.pack(side="right")

        ttk.Label(outer, textvariable=self.summary, font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 8)
        )
        table_frame = ttk.Frame(outer)
        table_frame.pack(fill="both", expand=True)
        columns = ("app", "status", "ka", "en", "issues")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings")
        headings = {
            "app": "აპლიკაცია ან თამაში",
            "status": "მზადყოფნა",
            "ka": "ქართული სახელები",
            "en": "English aliases",
            "issues": "არასწორი სახელები",
        }
        widths = {"app": 260, "status": 170, "ka": 220, "en": 180, "issues": 180}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], minwidth=110, stretch=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.tag_configure("both_ready", foreground="#146C2E")
        self.table.tag_configure("ka_ready", foreground="#146C2E")
        self.table.tag_configure("en_ready", foreground="#1558A6")
        self.table.tag_configure("invalid", foreground="#B3261E")
        self.table.tag_configure("unconfigured", foreground="#666666")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Label(
            bottom,
            text="ხმოვანი სახელის დამატება ან გასწორება შესაძლებელია „აპლიკაციების მართვის პროფილებიდან“.",
        ).pack(side="left")
        ttk.Button(bottom, text="დახურვა", command=self.root.destroy).pack(side="right")

    def _refresh(self) -> None:
        self.refresh_button.state(["disabled"])
        self.summary.set("ქართული და ინგლისური ხმოვანი სახელები მოწმდება…")

        def work() -> None:
            try:
                records = analyze_voice_readiness()
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._failed(error))
            else:
                self.root.after(0, lambda: self._loaded(records))

        threading.Thread(target=work, name="gela-catalog-readiness", daemon=True).start()

    def _loaded(self, records: list[VoiceReadiness]) -> None:
        self.records = records
        self.refresh_button.state(["!disabled"])
        counts = readiness_counts(records)
        self.summary.set(
            f"სულ {len(records)} • ორივე ენა {counts['both_ready']} • ქართული {counts['ka_ready']} • "
            f"English {counts['en_ready']} • არასწორი {counts['invalid']} • მოუმზადებელი {counts['unconfigured']}"
        )
        self._render()

    def _failed(self, exc: Exception) -> None:
        self.refresh_button.state(["!disabled"])
        self.summary.set(f"მზადყოფნის შემოწმება ვერ დასრულდა: {exc}")

    def _render(self) -> None:
        if not hasattr(self, "table"):
            return
        query = self.search.get().casefold().strip()
        selected_status = FILTER_LABELS.get(self.status_filter.get())
        self.table.delete(*self.table.get_children())
        for record in self.records:
            if query and query not in record.app_name.casefold():
                continue
            if selected_status and record.status != selected_status:
                continue
            self.table.insert(
                "",
                "end",
                values=(
                    record.app_name,
                    STATUS_LABELS[record.status],
                    ", ".join(record.valid_ka_aliases) or "—",
                    ", ".join(record.valid_en_aliases) or "—",
                    ", ".join(record.invalid_aliases) or "—",
                ),
                tags=(record.status,),
            )


def main() -> int:
    import sys

    root = tk.Tk()
    smoke = "--smoke" in sys.argv
    CatalogWindow(root, analyze=not smoke)
    if smoke:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
