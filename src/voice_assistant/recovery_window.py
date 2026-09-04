from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from .recovery_backup import (
    DEFAULT_BACKUP_DIRECTORY,
    RecoveryBackupError,
    create_recovery_backup,
    default_backup_path,
    read_recovery_backup,
    restore_recovery_backup,
)


def _password(root: tk.Tk, *, confirm: bool) -> str | None:
    password = simpledialog.askstring("Gela Recovery", "Recovery password:", show="*", parent=root)
    if password is None:
        return None
    if confirm:
        repeated = simpledialog.askstring("Gela Recovery", "Repeat recovery password:", show="*", parent=root)
        if repeated is None:
            return None
        if password != repeated:
            messagebox.showerror("Gela Recovery", "The passwords do not match.", parent=root)
            return None
    return password


def create_from_dialog(root: tk.Tk) -> Path | None:
    DEFAULT_BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    destination = filedialog.asksaveasfilename(
        parent=root,
        title="Save encrypted Gela recovery backup",
        initialdir=str(DEFAULT_BACKUP_DIRECTORY),
        initialfile=default_backup_path().name,
        defaultextension=".gelabackup",
        filetypes=[("Gela encrypted backup", "*.gelabackup")],
    )
    if not destination:
        return None
    password = _password(root, confirm=True)
    if password is None:
        return None
    try:
        files = create_recovery_backup(password, Path(destination))
        verified = read_recovery_backup(password, Path(destination))
        if sorted(verified) != files:
            raise RecoveryBackupError("Backup verification did not reproduce its manifest.")
    except (OSError, RecoveryBackupError) as exc:
        messagebox.showerror("Gela Recovery", str(exc), parent=root)
        return None
    messagebox.showinfo(
        "Gela Recovery",
        f"Encrypted and verified backup created:\n{destination}\n\nFiles saved: {len(files)}",
        parent=root,
    )
    return Path(destination)


def restore_from_dialog(root: tk.Tk) -> bool:
    source = filedialog.askopenfilename(
        parent=root,
        title="Open Gela recovery backup",
        initialdir=str(DEFAULT_BACKUP_DIRECTORY),
        filetypes=[("Gela encrypted backup", "*.gelabackup")],
    )
    if not source:
        return False
    password = _password(root, confirm=False)
    if password is None:
        return False
    try:
        files = read_recovery_backup(password, Path(source))
    except (OSError, RecoveryBackupError) as exc:
        messagebox.showerror("Gela Recovery", str(exc), parent=root)
        return False
    if not messagebox.askyesno(
        "Restore Gela configuration?",
        f"This verified backup contains {len(files)} files.\n\n"
        "Close Gela before restoring. Existing matching configuration files will be replaced. Continue?",
        icon="warning",
        parent=root,
    ):
        return False
    try:
        restore_recovery_backup(password, Path(source))
    except (OSError, RecoveryBackupError) as exc:
        messagebox.showerror("Gela Recovery", str(exc), parent=root)
        return False
    messagebox.showinfo("Gela Recovery", "Configuration restored. Start Gela again.", parent=root)
    return True


def main() -> int:
    root = tk.Tk()
    root.title("Gela encrypted recovery")
    root.geometry("460x230")
    root.resizable(False, False)
    tk.Label(root, text="Gela encrypted recovery", font=("Segoe UI", 17, "bold")).pack(pady=(22, 8))
    tk.Label(root, text="Back up private settings to disk D or restore a verified backup.", wraplength=410).pack(pady=(0, 18))
    tk.Button(root, text="Create encrypted backup", width=32, command=lambda: create_from_dialog(root)).pack(pady=4)
    tk.Button(root, text="Restore encrypted backup", width=32, command=lambda: restore_from_dialog(root)).pack(pady=4)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
