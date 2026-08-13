from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .alias_store import AliasStore
from .catalog import scan_catalog
from .config import PROJECT_ROOT


class AliasManagerWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.store = AliasStore()
        self.filtered_apps = list(self.store.app_names)
        self.selected_app: str | None = None
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="აირჩიეთ აპლიკაცია.")

        root.title("Gela — ხმოვანი სახელების მართვა")
        root.geometry("900x580")
        root.minsize(760, 480)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)

        self._build()
        self.search_var.trace_add("write", lambda *_: self._filter_apps())
        self._filter_apps()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text="აპლიკაციის ძიება:").grid(row=0, column=0, sticky="w")
        search = ttk.Entry(outer, textvariable=self.search_var)
        search.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        left = ttk.Frame(outer)
        left.grid(row=1, column=0, sticky="nsew", pady=10)
        left.rowconfigure(0, weight=1)
        self.apps_list = tk.Listbox(left, width=34, exportselection=False)
        apps_scroll = ttk.Scrollbar(left, orient="vertical", command=self.apps_list.yview)
        self.apps_list.configure(yscrollcommand=apps_scroll.set)
        self.apps_list.grid(row=0, column=0, sticky="nsew")
        apps_scroll.grid(row=0, column=1, sticky="ns")
        self.apps_list.bind("<<ListboxSelect>>", self._app_selected)

        right = ttk.Frame(outer)
        right.grid(row=1, column=1, sticky="nsew", padx=(14, 0), pady=10)
        right.columnconfigure(0, weight=1)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(1, weight=1)
        self.app_title = ttk.Label(right, text="აპლიკაცია არჩეული არ არის", font=("Segoe UI", 14, "bold"))
        self.app_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.language_widgets = {
            "ka": self._language_panel(right, 0, "ქართული სახელები", "მაგალითი: ქრომი"),
            "en": self._language_panel(right, 1, "ინგლისური სახელები", "მაგალითი: chrome"),
        }

        bottom = ttk.Frame(outer)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="შენახვა და გამოყენება", command=self._save).grid(row=0, column=1)
        ttk.Button(bottom, text="დახურვა", command=self.root.destroy).grid(row=0, column=2, padx=(8, 0))

    def _language_panel(self, parent, column: int, title: str, hint: str) -> dict[str, object]:
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.grid(row=1, column=column, sticky="nsew", padx=(0, 5) if column == 0 else (5, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        aliases = tk.Listbox(frame, exportselection=False)
        aliases.grid(row=0, column=0, columnspan=2, sticky="nsew")
        entry = ttk.Entry(frame)
        entry.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        entry.insert(0, hint)
        language = "ka" if column == 0 else "en"
        ttk.Button(frame, text="დამატება", command=lambda: self._add_alias(language)).grid(
            row=1, column=1, padx=(6, 0), pady=(8, 0)
        )
        ttk.Button(frame, text="არჩეულის წაშლა", command=lambda: self._remove_alias(language)).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )
        entry.bind("<Return>", lambda event: self._add_alias(language))
        return {"list": aliases, "entry": entry, "hint": hint}

    def _filter_apps(self) -> None:
        query = self.search_var.get().casefold().strip()
        self.filtered_apps = [name for name in self.store.app_names if query in name.casefold()]
        self.apps_list.delete(0, tk.END)
        for name in self.filtered_apps:
            self.apps_list.insert(tk.END, name)

    def _app_selected(self, _event=None) -> None:
        selection = self.apps_list.curselection()
        if not selection:
            return
        self.selected_app = self.filtered_apps[selection[0]]
        self.app_title.configure(text=self.selected_app)
        self._refresh_aliases()

    def _refresh_aliases(self) -> None:
        if self.selected_app is None:
            return
        for language, widgets in self.language_widgets.items():
            listbox: tk.Listbox = widgets["list"]  # type: ignore[assignment]
            listbox.delete(0, tk.END)
            for alias in self.store.aliases(self.selected_app, language):
                listbox.insert(tk.END, alias)

    def _add_alias(self, language: str) -> None:
        if self.selected_app is None:
            messagebox.showwarning("Gela", "ჯერ აირჩიეთ აპლიკაცია.")
            return
        widgets = self.language_widgets[language]
        entry: ttk.Entry = widgets["entry"]  # type: ignore[assignment]
        alias = entry.get().strip()
        if not alias or alias == widgets["hint"]:
            return
        try:
            self.store.add(self.selected_app, language, alias)
        except ValueError as exc:
            messagebox.showerror("სახელების კონფლიქტი", str(exc))
            self.status_var.set("ხმოვანი სახელი არ დაემატა.")
            return
        entry.delete(0, tk.END)
        self._refresh_aliases()
        self.status_var.set("სახელი დაემატა. დააჭირეთ „შენახვა და გამოყენება“.")

    def _remove_alias(self, language: str) -> None:
        if self.selected_app is None:
            return
        listbox: tk.Listbox = self.language_widgets[language]["list"]  # type: ignore[assignment]
        selection = listbox.curselection()
        if not selection:
            return
        alias = listbox.get(selection[0])
        self.store.remove(self.selected_app, language, alias)
        self._refresh_aliases()
        self.status_var.set("სახელი წაიშალა. დააჭირეთ „შენახვა და გამოყენება“.")

    def _save(self) -> None:
        try:
            self.store.save()
            entries = scan_catalog()
        except Exception as exc:
            messagebox.showerror("შენახვა ვერ მოხერხდა", str(exc))
            return
        self.status_var.set(f"შენახულია. კატალოგშია {len(entries)} ჩანაწერი.")
        messagebox.showinfo("Gela", "ხმოვანი სახელები შენახული და გამოყენებულია.")


def main() -> int:
    root = tk.Tk()
    window = AliasManagerWindow(root)
    if "--smoke" in sys.argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
