from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .catalog import CATALOG_PATH, load_catalog
from .config import PROJECT_ROOT
from .routines import Routine, load_routines, save_routines


class RoutineManagerWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.routines = load_routines()
        self.selected: int | None = None
        self.apps = [entry.name for entry in load_catalog()]
        self.name_var = tk.StringVar()
        self.ka_var = tk.StringVar()
        self.en_var = tk.StringVar()
        self.app_var = tk.StringVar(value=self.apps[0] if self.apps else "")
        self.status = tk.StringVar(value="აირჩიეთ რუტინა ან შექმენით ახალი.")

        root.title("Gela — რუტინების მართვა")
        root.geometry("900x590")
        root.minsize(760, 500)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self._refresh_list()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        left = ttk.Frame(outer)
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="რუტინები", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        self.routine_list = tk.Listbox(left, width=30, exportselection=False)
        self.routine_list.pack(fill="y", expand=True, pady=8)
        self.routine_list.bind("<<ListboxSelect>>", self._selected)
        ttk.Button(left, text="ახალი რუტინა", command=self._new).pack(fill="x")
        ttk.Button(left, text="არჩეულის წაშლა", command=self._delete).pack(fill="x", pady=(6, 0))

        right = ttk.Frame(outer)
        right.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        right.columnconfigure(1, weight=1)
        right.rowconfigure(4, weight=1)
        ttk.Label(right, text="სახელი:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(right, text="ქართული ფრაზა:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.ka_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(right, text="ინგლისური ფრაზა:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.en_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(
            right,
            text="ფრაზა თქვით უშუალოდ „გელას“ შემდეგ. საჭიროა მინიმუმ ერთი ენა.",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 10))

        apps_frame = ttk.LabelFrame(right, text="აპლიკაციები გაშვების თანმიმდევრობით", padding=10)
        apps_frame.grid(row=4, column=0, columnspan=2, sticky="nsew")
        apps_frame.columnconfigure(0, weight=1)
        apps_frame.rowconfigure(0, weight=1)
        self.step_list = tk.Listbox(apps_frame, exportselection=False)
        self.step_list.grid(row=0, column=0, columnspan=4, sticky="nsew")
        ttk.Combobox(apps_frame, textvariable=self.app_var, values=self.apps, state="readonly").grid(
            row=1, column=0, sticky="ew", pady=(8, 0)
        )
        ttk.Button(apps_frame, text="დამატება", command=self._add_app).grid(row=1, column=1, padx=(6, 0), pady=(8, 0))
        ttk.Button(apps_frame, text="ზემოთ აწევა", command=lambda: self._move(-1)).grid(row=1, column=2, padx=(6, 0), pady=(8, 0))
        ttk.Button(apps_frame, text="წაშლა", command=self._remove_app).grid(row=1, column=3, padx=(6, 0), pady=(8, 0))

        bottom = ttk.Frame(outer)
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.status).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="შენახვა და გამოყენება", command=self._save).grid(row=0, column=1)
        ttk.Button(bottom, text="დახურვა", command=self.root.destroy).grid(row=0, column=2, padx=(8, 0))

    def _refresh_list(self) -> None:
        self.routine_list.delete(0, tk.END)
        for routine in self.routines:
            self.routine_list.insert(tk.END, routine.name)

    def _selected(self, _event=None) -> None:
        selection = self.routine_list.curselection()
        if not selection:
            return
        self.selected = selection[0]
        routine = self.routines[self.selected]
        self.name_var.set(routine.name)
        self.ka_var.set(", ".join(routine.aliases.get("ka", [])))
        self.en_var.set(", ".join(routine.aliases.get("en", [])))
        self.step_list.delete(0, tk.END)
        for app in routine.apps:
            self.step_list.insert(tk.END, app)

    def _new(self) -> None:
        self.selected = None
        self.routine_list.selection_clear(0, tk.END)
        self.name_var.set("")
        self.ka_var.set("")
        self.en_var.set("")
        self.step_list.delete(0, tk.END)
        self.status.set("შეიყვანეთ სახელი, ფრაზა და აპლიკაციები, შემდეგ შეინახეთ.")

    def _delete(self) -> None:
        if self.selected is None:
            return
        del self.routines[self.selected]
        self.selected = None
        self._new()
        self._refresh_list()
        self.status.set("რუტინა მონახაზიდან წაიშალა. დააჭირეთ „შენახვა და გამოყენება“.")

    def _add_app(self) -> None:
        app = self.app_var.get()
        if app and self.step_list.size() < 10:
            self.step_list.insert(tk.END, app)

    def _remove_app(self) -> None:
        selection = self.step_list.curselection()
        if selection:
            self.step_list.delete(selection[0])

    def _move(self, offset: int) -> None:
        selection = self.step_list.curselection()
        if not selection:
            return
        index = selection[0]
        target = index + offset
        if not 0 <= target < self.step_list.size():
            return
        value = self.step_list.get(index)
        self.step_list.delete(index)
        self.step_list.insert(target, value)
        self.step_list.selection_set(target)

    @staticmethod
    def _aliases(value: str) -> list[str]:
        return list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))

    def _save(self) -> None:
        routine = Routine(
            name=self.name_var.get().strip(),
            aliases={"ka": self._aliases(self.ka_var.get()), "en": self._aliases(self.en_var.get())},
            apps=list(self.step_list.get(0, tk.END)),
        )
        try:
            updated = list(self.routines)
            if self.selected is None:
                updated.append(routine)
            else:
                updated[self.selected] = routine
            save_routines(updated)
            CATALOG_PATH.touch()
        except Exception as exc:
            messagebox.showerror("შენახვა ვერ მოხერხდა", str(exc))
            return
        self.routines = sorted(updated, key=lambda item: item.name.casefold())
        self._refresh_list()
        self.status.set("რუტინები შენახულია და Gela ხმოვან ბრძანებებს თავიდან ტვირთავს.")
        messagebox.showinfo("Gela", "რუტინები შენახული და გამოყენებულია.")


def main() -> int:
    root = tk.Tk()
    RoutineManagerWindow(root)
    if "--smoke" in __import__("sys").argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
