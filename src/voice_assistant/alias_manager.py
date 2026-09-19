from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from .alias_store import AliasStore
from .catalog import scan_catalog
from .config import PROJECT_ROOT


GEORGIAN_LANGUAGE_ID = 0x0437


def windows_unicode_key(keycode: int) -> str | None:
    """Read the current Windows key through its Unicode API, bypassing Tk ANSI input."""
    if sys.platform != "win32" or not 0 <= keycode <= 255:
        return None
    user32 = ctypes.windll.user32
    user32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
    user32.GetKeyboardLayout.restype = ctypes.c_void_p
    user32.GetKeyboardState.argtypes = (ctypes.POINTER(ctypes.c_ubyte),)
    user32.GetKeyboardState.restype = wintypes.BOOL
    user32.MapVirtualKeyExW.argtypes = (wintypes.UINT, wintypes.UINT, ctypes.c_void_p)
    user32.MapVirtualKeyExW.restype = wintypes.UINT
    user32.ToUnicodeEx.argtypes = (
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.UINT,
        ctypes.c_void_p,
    )
    user32.ToUnicodeEx.restype = ctypes.c_int
    layout = user32.GetKeyboardLayout(0)
    if not layout or (int(layout) & 0xFFFF) != GEORGIAN_LANGUAGE_ID:
        return None
    keyboard_state = (ctypes.c_ubyte * 256)()
    if not user32.GetKeyboardState(keyboard_state):
        return None
    scan_code = user32.MapVirtualKeyExW(keycode, 0, layout)
    output = ctypes.create_unicode_buffer(8)
    count = user32.ToUnicodeEx(
        keycode,
        scan_code,
        keyboard_state,
        output,
        len(output),
        0,
        layout,
    )
    if count <= 0:
        return None
    value = output.value[:count]
    return value if any("\u10A0" <= character <= "\u10FF" for character in value) else None


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
        self.ui_font_family = self._configure_fonts()
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)

        self._build()
        self.search_var.trace_add("write", lambda *_: self._filter_apps())
        self._filter_apps()

    def _configure_fonts(self) -> str:
        """Use a Windows font with native Georgian glyph coverage in every widget."""
        families = {name.casefold(): name for name in tkfont.families(self.root)}
        family = families.get("sylfaen", families.get("segoe ui", "TkDefaultFont"))
        normal = (family, 10)
        self.root.option_add("*Font", normal)
        style = ttk.Style(self.root)
        style.configure(".", font=normal)
        return family

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
        self.apps_list = tk.Listbox(
            left,
            width=34,
            exportselection=False,
            font=(self.ui_font_family, 10),
        )
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
        self.app_title = ttk.Label(
            right,
            text="აპლიკაცია არჩეული არ არის",
            font=(self.ui_font_family, 14, "bold"),
        )
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
        aliases = tk.Listbox(frame, exportselection=False, font=(self.ui_font_family, 10))
        aliases.grid(row=0, column=0, columnspan=2, sticky="nsew")
        entry = ttk.Entry(frame)
        entry.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        entry.insert(0, hint)
        entry.bind("<FocusIn>", lambda _event: self._clear_hint(entry, hint))
        entry.bind("<FocusOut>", lambda _event: self._restore_hint(entry, hint))
        language = "ka" if column == 0 else "en"
        if language == "ka":
            entry.bind(
                "<KeyPress>",
                lambda event: self._insert_georgian_key(event, entry),
                add="+",
            )
        ttk.Button(frame, text="დამატება", command=lambda: self._add_alias(language)).grid(
            row=1, column=1, padx=(6, 0), pady=(8, 0)
        )
        ttk.Button(frame, text="არჩეულის წაშლა", command=lambda: self._remove_alias(language)).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )
        entry.bind("<Return>", lambda event: self._add_alias(language))
        return {"list": aliases, "entry": entry, "hint": hint}

    @staticmethod
    def _clear_hint(entry: ttk.Entry, hint: str) -> None:
        if entry.get() == hint:
            entry.delete(0, tk.END)

    @staticmethod
    def _restore_hint(entry: ttk.Entry, hint: str) -> None:
        if not entry.get():
            entry.insert(0, hint)

    @staticmethod
    def _insert_georgian_key(event, entry: ttk.Entry) -> str | None:
        character = windows_unicode_key(int(event.keycode))
        if character is None:
            return None
        try:
            if entry.selection_present():
                entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        entry.insert(tk.INSERT, character)
        return "break"

    @staticmethod
    def _clear_hint(entry: ttk.Entry, hint: str) -> None:
        if entry.get() == hint:
            entry.delete(0, tk.END)

    @staticmethod
    def _restore_hint(entry: ttk.Entry, hint: str) -> None:
        if not entry.get().strip():
            entry.delete(0, tk.END)
            entry.insert(0, hint)

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
