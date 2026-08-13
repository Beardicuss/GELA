from __future__ import annotations

import copy
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .alias_store import AliasStore
from .app_profiles import AppProfileStore
from .catalog import scan_catalog
from .config import PROJECT_ROOT


CLOSE_BEHAVIOR_LABELS = {
    "ავტომატური — საჭიროებისას ფონური პროცესის დასრულება": "graceful_then_force",
    "მხოლოდ უსაფრთხო დახურვა — Force-ის გარეშე": "graceful_only",
    "მხოლოდ შესაბამისი ფანჯრის დახურვა": "window_only",
}


def _clean_lines(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def save_profile_configuration(
    profile_store: AppProfileStore,
    alias_store: AliasStore,
    app_name: str,
    preferred_processes: list[str],
    window_titles: list[str],
    close_behavior: str,
    georgian_aliases: list[str],
    english_aliases: list[str],
) -> int:
    georgian_aliases = _clean_lines(georgian_aliases)
    english_aliases = _clean_lines(english_aliases)
    previous_profiles = copy.deepcopy(profile_store.data)
    previous_aliases = copy.deepcopy(alias_store.data)
    try:
        profile_store.set(
            app_name,
            _clean_lines(preferred_processes),
            _clean_lines(window_titles),
            close_behavior,
        )
        alias_store.replace(app_name, "ka", georgian_aliases)
        alias_store.replace(app_name, "en", english_aliases)
        profile_store.save()
        alias_store.save()
        entries = scan_catalog()
    except Exception:
        profile_store.data = previous_profiles
        alias_store.data = previous_aliases
        profile_store.save()
        alias_store.save()
        raise
    return len(entries)


class ProfileManagerWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.profile_store = AppProfileStore()
        self.alias_store = AliasStore()
        self.filtered_apps = list(self.profile_store.app_names)
        self.selected_app: str | None = None
        self.busy = False

        self.search = tk.StringVar()
        self.status = tk.StringVar(value="აირჩიეთ აპლიკაცია ან თამაში.")
        self.close_behavior = tk.StringVar(value=next(iter(CLOSE_BEHAVIOR_LABELS)))

        root.title("Gela — აპლიკაციის მართვის პროფილები")
        root.geometry("980x680")
        root.minsize(840, 580)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self.search.trace_add("write", lambda *_: self._filter())
        self._filter()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)
        ttk.Label(
            outer,
            text="აპლიკაციის მართვის პროფილები",
            font=("Segoe UI", 17, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        left = ttk.Frame(outer)
        left.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        left.rowconfigure(1, weight=1)
        ttk.Entry(left, textvariable=self.search, width=31).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.apps = tk.Listbox(left, width=34, exportselection=False)
        self.apps.grid(row=1, column=0, sticky="nsew")
        self.apps.bind("<<ListboxSelect>>", self._selected)

        right = ttk.Frame(outer)
        right.grid(row=1, column=1, sticky="nsew", padx=(14, 0), pady=(12, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        self.title = ttk.Label(right, text="აპლიკაცია არჩეული არ არის", font=("Segoe UI", 14, "bold"))
        self.title.grid(row=0, column=0, sticky="w", pady=(0, 8))
        notebook = ttk.Notebook(right)
        notebook.grid(row=1, column=0, sticky="nsew")

        control = ttk.Frame(notebook, padding=14)
        control.columnconfigure(0, weight=1)
        control.rowconfigure(1, weight=1)
        control.rowconfigure(3, weight=1)
        notebook.add(control, text="პროცესი და ფანჯარა")
        ttk.Label(control, text="სასურველი პროცესები — თითო ხაზზე ერთი .exe სახელი").grid(row=0, column=0, sticky="w")
        self.processes = tk.Text(control, height=6, wrap="none")
        self.processes.grid(row=1, column=0, sticky="nsew", pady=(5, 12))
        ttk.Label(control, text="ფანჯრის სათაურის დამატებითი ნაწილები — თითო ხაზზე ერთი").grid(row=2, column=0, sticky="w")
        self.titles = tk.Text(control, height=6)
        self.titles.grid(row=3, column=0, sticky="nsew", pady=(5, 12))
        ttk.Label(control, text="სრული დახურვის ქცევა").grid(row=4, column=0, sticky="w")
        ttk.Combobox(
            control,
            textvariable=self.close_behavior,
            values=list(CLOSE_BEHAVIOR_LABELS),
            state="readonly",
        ).grid(row=5, column=0, sticky="ew", pady=(5, 0))

        aliases = ttk.Frame(notebook, padding=14)
        aliases.columnconfigure(0, weight=1)
        aliases.columnconfigure(1, weight=1)
        aliases.rowconfigure(1, weight=1)
        notebook.add(aliases, text="ხმოვანი სახელები")
        ttk.Label(aliases, text="ქართული — თითო ხაზზე ერთი").grid(row=0, column=0, sticky="w")
        ttk.Label(aliases, text="English — one per line").grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.ka_aliases = tk.Text(aliases, height=16)
        self.en_aliases = tk.Text(aliases, height=16)
        self.ka_aliases.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        self.en_aliases.grid(row=1, column=1, sticky="nsew", padx=(12, 0), pady=(5, 0))

        bottom = ttk.Frame(outer)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(bottom, textvariable=self.status, wraplength=690).pack(side="left")
        ttk.Button(bottom, text="დახურვა", command=self.root.destroy).pack(side="right")
        self.save_button = ttk.Button(bottom, text="შენახვა და გამოყენება", command=self._save)
        self.save_button.pack(side="right", padx=(0, 8))

    def _filter(self) -> None:
        query = self.search.get().casefold().strip()
        self.filtered_apps = [name for name in self.profile_store.app_names if query in name.casefold()]
        self.apps.delete(0, tk.END)
        for name in self.filtered_apps:
            self.apps.insert(tk.END, name)

    def _selected(self, _event=None) -> None:
        selection = self.apps.curselection()
        if not selection:
            return
        self.selected_app = self.filtered_apps[selection[0]]
        self.title.configure(text=self.selected_app)
        profile = self.profile_store.get(self.selected_app)
        self._set_text(self.processes, profile.preferred_processes)
        self._set_text(self.titles, profile.window_titles)
        label = next(
            label for label, value in CLOSE_BEHAVIOR_LABELS.items() if value == profile.close_behavior
        )
        self.close_behavior.set(label)
        self._set_text(self.ka_aliases, self.alias_store.aliases(self.selected_app, "ka"))
        self._set_text(self.en_aliases, self.alias_store.aliases(self.selected_app, "en"))
        self.status.set("პროფილი ჩატვირთულია.")

    @staticmethod
    def _set_text(widget: tk.Text, values: list[str]) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", "\n".join(values))

    @staticmethod
    def _lines(widget: tk.Text) -> list[str]:
        return widget.get("1.0", tk.END).splitlines()

    def _save(self) -> None:
        if self.selected_app is None or self.busy:
            messagebox.showwarning("Gela", "ჯერ აირჩიეთ აპლიკაცია.")
            return
        app_name = self.selected_app
        processes = self._lines(self.processes)
        titles = self._lines(self.titles)
        ka_aliases = self._lines(self.ka_aliases)
        en_aliases = self._lines(self.en_aliases)
        behavior = CLOSE_BEHAVIOR_LABELS[self.close_behavior.get()]
        self.busy = True
        self.save_button.state(["disabled"])
        self.status.set("პროფილი, ლექსიკა და კონფლიქტები მოწმდება…")

        def work() -> None:
            try:
                count = save_profile_configuration(
                    self.profile_store,
                    self.alias_store,
                    app_name,
                    processes,
                    titles,
                    behavior,
                    ka_aliases,
                    en_aliases,
                )
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._failed(error))
            else:
                self.root.after(0, lambda: self._saved(count))

        threading.Thread(target=work, name="gela-profile-save", daemon=True).start()

    def _failed(self, exc: Exception) -> None:
        self.busy = False
        self.save_button.state(["!disabled"])
        self.status.set("პროფილი არ შენახულა.")
        messagebox.showerror("პროფილის შეცდომა", str(exc))

    def _saved(self, catalog_count: int) -> None:
        self.busy = False
        self.save_button.state(["!disabled"])
        self.status.set(f"პროფილი შენახულია. კატალოგშია {catalog_count} ჩანაწერი.")
        messagebox.showinfo("Gela", "აპლიკაციის პროფილი შენახული და გამოყენებულია.")


def main() -> int:
    root = tk.Tk()
    ProfileManagerWindow(root)
    if "--smoke" in __import__("sys").argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
