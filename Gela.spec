from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs


root = Path(SPECPATH)
vosk_package = root / ".venv" / "Lib" / "site-packages" / "vosk"
vosk_binaries = [(str(dll), "vosk") for dll in vosk_package.glob("*.dll")]
sherpa_binaries = collect_dynamic_libs("sherpa_onnx")
data_items = [
    (str(root / "config"), "config"),
    (str(root / "models"), "models"),
    (str(root / "audio" / "voice" / "processed"), "audio/voice/processed"),
    (str(root / "audio" / "voice" / "recording_manifest.csv"), "audio/voice"),
    (str(root / "assets" / "icons"), "assets/icons"),
    (str(root / "INSTALL.txt"), "."),
    (str(root / "COMMANDS.md"), "."),
]

a = Analysis(
    [str(root / "src" / "gela_entry.py")],
    pathex=[str(root / "src")],
    binaries=[*vosk_binaries, *sherpa_binaries],
    datas=data_items,
    hiddenimports=[
        "voice_assistant.alias_manager",
        "voice_assistant.diagnostics",
        "voice_assistant.calibration",
        "voice_assistant.routine_manager",
        "voice_assistant.answer_window",
        "voice_assistant.settings_window",
        "voice_assistant.logs_window",
        "voice_assistant.recognition_test_window",
        "voice_assistant.profile_manager",
        "voice_assistant.catalog_window",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Gela",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(root / "assets" / "icons" / "gela_tray.ico"),
    version=str(root / "installer" / "version_info.txt"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Gela",
)
