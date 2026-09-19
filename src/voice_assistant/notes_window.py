from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import Callable

from .alias_manager import windows_unicode_key
from .config import PROJECT_ROOT
from .dictation_corrections_panel import DictationCorrectionsPanel
from .notes import DRAFT_PATH, desktop_path, read_state, request_dictation_stop
from .notes_theme import CRIMSON, CRIMSON_BORDER, CRIMSON_DIM, CRIMSON_SOFT, SURFACE, SURFACE_DEEP, TEXT, configure_cardinal_theme
from .single_instance import SingleInstanceLock
from .storage import atomic_write_text

STATUS_READY = "მზადაა"
STATUS_LISTENING = "გისმენთ"
STATUS_WRITING = "ვწერ..."
STATUS_STOPPED = "შეჩერებულია"


class NotesWindow:
    """Cardinal-styled UTF-8 notes editor for Gela dictation."""

    def __init__(self, root: tk.Tk, on_stop: Callable[[], None] | None = None) -> None:
        self.root = root
        self.on_stop = on_stop
        self.status_var = tk.StringVar(value=STATUS_READY)
        self.language_var = tk.StringVar(value="ენა: ავტომატური")
        self.save_var = tk.StringVar(value="ავტომატური ასლი დაცულია")
        self.filename_var = tk.StringVar(value="უსახელო ჩანაწერი")
        self.dictation_active = False
        self.current_path: Path | None = None
        self.dirty = False
        self._state_revision = -1
        self._draft_snapshot = ""
        self._loading_draft = False
        self._font_scale = 1.0
        self._font_resize_job: str | None = None

        root.title("Gela Notes — ჩანაწერი")
        root.geometry("900x650")
        root.minsize(560, 400)
        root.protocol("WM_DELETE_WINDOW", self._close_requested)
        self.ui_font_family = self._configure_fonts()
        self.cardinal_style = configure_cardinal_theme(root, self.ui_font_family)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self.root.bind("<Configure>", self._schedule_font_resize, add=True)
        self.root.after_idle(self._apply_responsive_fonts)
        self._bind_shortcuts()
        self._load_draft()
        self.root.after(250, self._poll_session)

    def _configure_fonts(self) -> str:
        families = {name.casefold(): name for name in tkfont.families(self.root)}
        family = families.get("sylfaen", families.get("segoe ui", "TkDefaultFont"))
        self.root.option_add("*Font", (family, 10))
        return family

    def _schedule_font_resize(self, event) -> None:
        if event.widget is not self.root:
            return
        if self._font_resize_job is not None:
            self.root.after_cancel(self._font_resize_job)
        self._font_resize_job = self.root.after(80, self._apply_responsive_fonts)

    def _apply_responsive_fonts(self) -> None:
        self._font_resize_job = None
        width = self.root.winfo_width()
        scale = 1.35 if width >= 1800 else 1.18 if width >= 1250 else 1.0
        if scale == self._font_scale and hasattr(self, "editor"):
            return
        self._font_scale = scale
        self.cardinal_style = configure_cardinal_theme(self.root, self.ui_font_family, scale)
        self.editor.configure(font=(self.ui_font_family, round(12 * scale)))
        self.document_label.configure(font=(self.ui_font_family, round(10 * scale), "bold"))
        self.corrections_panel.apply_font_scale(scale)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=(20, 16), style="Cardinal.TFrame")
        outer.pack(fill="both", expand=True)
        horizontal_padding = 0
        top_padding = 0
        header = ttk.Frame(outer, style="Cardinal.TFrame")
        header.pack(fill="x", padx=horizontal_padding, pady=(top_padding, 0))
        title_group = ttk.Frame(header, style="Cardinal.TFrame")
        title_group.pack(side="left", fill="x", expand=True)
        ttk.Label(title_group, text="◆  GELA / SECURE NOTES", style="Cardinal.Kicker.TLabel").pack(anchor="w")
        ttk.Label(title_group, text="Gela Notes", style="Cardinal.Title.TLabel").pack(anchor="w", pady=(3, 0))
        ttk.Label(header, textvariable=self.status_var, style="Cardinal.Status.TLabel").pack(side="right", anchor="n", pady=(4, 0))
        tk.Frame(outer, height=1, background=CRIMSON_DIM).pack(fill="x", padx=horizontal_padding, pady=(13, 10))

        toolbar = ttk.Frame(outer, style="Cardinal.TFrame")
        toolbar.pack(fill="x", padx=horizontal_padding, pady=(0, 8))
        actions = (("ახალი", self.new_document), ("გახსნა", self.open_document), ("შენახვა", self.save_document), ("შენახვა როგორც", self.save_document_as), ("ასლი", self.copy_text), ("↶", self.undo), ("↷", self.redo))
        for index, (label, command) in enumerate(actions):
            ttk.Button(toolbar, text=label, command=command, style="Cardinal.TButton").pack(side="left", padx=(0 if index == 0 else 5, 0))

        document_strip = ttk.Frame(outer, padding=(12, 7), style="Cardinal.Panel.TFrame")
        document_strip.pack(fill="x", padx=horizontal_padding)
        ttk.Label(document_strip, text="01  ACTIVE DOCUMENT", style="Cardinal.PanelMuted.TLabel").pack(side="left")
        self.document_label = ttk.Label(document_strip, textvariable=self.filename_var, style="Cardinal.Panel.TLabel", font=(self.ui_font_family, 10, "bold"))
        self.document_label.pack(side="right")

        self.tabs = ttk.Notebook(outer, style="Cardinal.TNotebook")
        self.tabs.pack(fill="both", expand=True, padx=horizontal_padding, pady=(0, top_padding))
        notes_tab = ttk.Frame(self.tabs, padding=10, style="Cardinal.Panel.TFrame")
        self.tabs.add(notes_tab, text="ჩანაწერი")
        editor_frame = ttk.Frame(notes_tab, style="Cardinal.Panel.TFrame")
        editor_frame.pack(fill="both", expand=True)
        self.editor = tk.Text(editor_frame, wrap="word", undo=True, maxundo=-1, font=(self.ui_font_family, 12), padx=16, pady=15, background=SURFACE_DEEP, foreground=TEXT, insertbackground=CRIMSON_SOFT, selectbackground=CRIMSON_DIM, selectforeground=TEXT, relief="flat", borderwidth=1, highlightthickness=1, highlightbackground=CRIMSON_BORDER, highlightcolor=CRIMSON)
        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=self.editor.yview, style="Cardinal.Vertical.TScrollbar")
        self.editor.configure(yscrollcommand=scrollbar.set)
        self.editor.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.editor.bind("<KeyPress>", self._insert_georgian_key, add=True)
        self.editor.bind("<<Modified>>", self._editor_modified)
        self.editor.bind("<Button-3>", self._show_editor_menu)

        footer = ttk.Frame(notes_tab, style="Cardinal.Panel.TFrame")
        footer.pack(fill="x", pady=(9, 0))
        ttk.Label(footer, textvariable=self.language_var, style="Cardinal.PanelMuted.TLabel").pack(side="left")
        ttk.Label(footer, text="  /  ", style="Cardinal.PanelMuted.TLabel").pack(side="left")
        ttk.Label(footer, textvariable=self.save_var, style="Cardinal.PanelMuted.TLabel").pack(side="left")
        self.stop_button = ttk.Button(footer, text="წერის შეწყვეტა", command=self._stop_requested, style="Cardinal.Primary.TButton")

        self.corrections_panel = DictationCorrectionsPanel(self.tabs, self.ui_font_family)
        self.tabs.add(self.corrections_panel, text="შესწორებები")
        self.editor_menu = tk.Menu(self.root, tearoff=False, font=(self.ui_font_family, 10), background=SURFACE, foreground=TEXT, activebackground=CRIMSON_DIM, activeforeground=TEXT, borderwidth=1)
        self.editor_menu.add_command(label="ამოჭრა", command=lambda: self.editor.event_generate("<<Cut>>"))
        self.editor_menu.add_command(label="ასლი", command=self.copy_text)
        self.editor_menu.add_command(label="ჩასმა", command=lambda: self.editor.event_generate("<<Paste>>"))
        self.editor_menu.add_separator()
        self.editor_menu.add_command(label="შესწორების დამატება", command=self._add_selected_correction)
        self.editor.focus_set()

    def _bind_shortcuts(self) -> None:
        bindings = {"<Control-n>": self.new_document, "<Control-o>": self.open_document, "<Control-s>": self.save_document, "<Control-Shift-S>": self.save_document_as, "<Control-z>": self.undo, "<Control-y>": self.redo}
        for sequence, command in bindings.items():
            self.root.bind(sequence, lambda _event, action=command: self._shortcut(action))

    @staticmethod
    def _shortcut(action: Callable[[], object]) -> str:
        action()
        return "break"

    def _insert_georgian_key(self, event) -> str | None:
        character = windows_unicode_key(int(event.keycode))
        if character is None:
            return None
        try:
            self.editor.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        self.editor.insert(tk.INSERT, character)
        return "break"

    def set_dictation_active(self, active: bool) -> None:
        self.dictation_active = active
        if active:
            self.status_var.set(STATUS_LISTENING)
            self.stop_button.pack(side="right")
        else:
            self.status_var.set(STATUS_STOPPED)
            self.stop_button.pack_forget()

    def set_writing(self) -> None:
        if self.dictation_active:
            self.status_var.set(STATUS_WRITING)

    def append_transcript(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self.editor.index("end-1c") != "1.0" and not self.editor.get("end-2c", "end-1c").isspace():
            self.editor.insert(tk.END, " ")
        self.editor.insert(tk.END, text)
        self.editor.see(tk.END)

    def new_document(self) -> None:
        if not self._confirm_discard():
            return
        self.current_path = None
        self._replace_editor("")
        atomic_write_text(DRAFT_PATH, "")
        self._draft_snapshot = ""
        self._set_dirty(False)

    def open_document(self) -> None:
        if not self._confirm_discard():
            return
        selected = filedialog.askopenfilename(parent=self.root, title="ჩანაწერის გახსნა", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        if not selected:
            return
        path = Path(selected)
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("გახსნა ვერ მოხერხდა", str(exc), parent=self.root)
            return
        self.current_path = path
        self._replace_editor(content)
        atomic_write_text(DRAFT_PATH, content)
        self._draft_snapshot = content
        self._set_dirty(False)

    def save_document(self) -> bool:
        return self._save_to(self.current_path or (desktop_path() / "gela.txt"))

    def save_document_as(self) -> bool:
        initial = self.current_path or (desktop_path() / "gela.txt")
        selected = filedialog.asksaveasfilename(parent=self.root, title="ჩანაწერის შენახვა", initialdir=str(initial.parent), initialfile=initial.name, defaultextension=".txt", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        return bool(selected) and self._save_to(Path(selected))

    def _save_to(self, path: Path) -> bool:
        try:
            atomic_write_text(path, self.editor.get("1.0", "end-1c"))
        except OSError as exc:
            messagebox.showerror("შენახვა ვერ მოხერხდა", str(exc), parent=self.root)
            return False
        self.current_path = path
        self._set_dirty(False)
        self.save_var.set("შენახულია")
        return True

    def copy_text(self) -> None:
        try:
            content = self.editor.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            content = self.editor.get("1.0", "end-1c")
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)

    def undo(self) -> None:
        try:
            self.editor.edit_undo()
        except tk.TclError:
            pass

    def redo(self) -> None:
        try:
            self.editor.edit_redo()
        except tk.TclError:
            pass

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("შეუნახავი ცვლილებები", "გსურთ ცვლილებების შენახვა?", parent=self.root)
        if answer is None:
            return False
        return self.save_document() if answer else True

    def _close_requested(self) -> None:
        if self._confirm_discard():
            self.root.destroy()

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        name = self.current_path.name if self.current_path else "უსახელო ჩანაწერი"
        self.filename_var.set(f"{name}{'  •' if dirty else ''}")
        if dirty:
            self.save_var.set("შეუნახავი ცვლილებები / ავტომატური ასლი დაცულია")
        self.root.title(f"Gela Notes — {name}{' *' if dirty else ''}")

    def _replace_editor(self, content: str) -> None:
        self._loading_draft = True
        try:
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
            self.editor.edit_reset()
            self.editor.edit_modified(False)
        finally:
            self._loading_draft = False

    def _stop_requested(self) -> None:
        if self.on_stop is not None:
            self.on_stop()
        else:
            request_dictation_stop()

    def _show_editor_menu(self, event) -> str:
        try:
            selected = bool(self.editor.get(tk.SEL_FIRST, tk.SEL_LAST).strip())
        except tk.TclError:
            selected = False
        for index in (0, 1, 4):
            self.editor_menu.entryconfigure(index, state="normal" if selected else "disabled")
        self.editor_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _add_selected_correction(self) -> None:
        try:
            selected = self.editor.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
        except tk.TclError:
            return
        if selected:
            self.corrections_panel.prefill(selected)
            self.tabs.select(self.corrections_panel)

    def _load_draft(self) -> None:
        try:
            content = DRAFT_PATH.read_text(encoding="utf-8")
        except OSError:
            content = ""
        self._replace_editor(content)
        self._draft_snapshot = content
        self._set_dirty(bool(content))

    def _editor_modified(self, _event=None) -> None:
        if self._loading_draft or not self.editor.edit_modified():
            return
        content = self.editor.get("1.0", "end-1c")
        atomic_write_text(DRAFT_PATH, content)
        self._draft_snapshot = content
        self._set_dirty(True)
        self.editor.edit_modified(False)

    def _poll_session(self) -> None:
        state = read_state()
        revision = int(state.get("revision", 0))
        if revision != self._state_revision:
            self._state_revision = revision
            active = bool(state.get("active", False))
            self.set_dictation_active(active)
            status = str(state.get("status", ""))
            self.language_var.set(f"ენა: {state.get('language', 'ავტომატური')}")
            if status == "writing":
                self.set_writing()
            elif status == "ready":
                self.status_var.set(STATUS_READY)
        try:
            content = DRAFT_PATH.read_text(encoding="utf-8")
        except OSError:
            content = self._draft_snapshot
        if content != self._draft_snapshot:
            cursor = self.editor.index(tk.INSERT)
            self._replace_editor(content)
            self._draft_snapshot = content
            self._set_dirty(True)
            try:
                self.editor.mark_set(tk.INSERT, cursor)
            except tk.TclError:
                self.editor.mark_set(tk.INSERT, tk.END)
            self.editor.see(tk.END)
        self.root.after(250, self._poll_session)


def main() -> int:
    instance_lock = SingleInstanceLock("Local\\GelaNotesWindow")
    if not instance_lock.acquire():
        return 0
    root = tk.Tk()
    try:
        NotesWindow(root)
        if "--smoke" in sys.argv:
            for geometry in ("560x400", "1100x760"):
                root.geometry(geometry)
                root.update_idletasks()
            root.destroy()
            return 0
        root.mainloop()
        return 0
    finally:
        instance_lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
