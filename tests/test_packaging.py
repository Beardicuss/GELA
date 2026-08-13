from pathlib import Path

from voice_assistant import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_are_consistent() -> None:
    assert __version__ == "1.5.2"
    assert 'version = "1.5.2"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '#define MyAppVersion "1.5.2"' in (ROOT / "installer/Gela.iss").read_text(encoding="utf-8")


def test_installer_is_per_user_and_preserves_data_by_default() -> None:
    script = (ROOT / "installer/Gela.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in script
    assert "DefaultDirName={localappdata}\\Programs\\Gela" in script
    assert "MB_DEFBUTTON2" in script
    assert "if (CurUninstallStep = usPostUninstall) and RemovePersonalData" in script


def test_installer_upgrade_identity_is_stable() -> None:
    script = (ROOT / "installer/Gela.iss").read_text(encoding="utf-8")
    assert "AppId={{6B0B790B-621D-49B2-AF7E-A9C4256D34C8}" in script
    assert "Source: \"..\\dist\\Gela\\*\"" in script


def test_release_is_branded_for_softcurse_systems() -> None:
    installer = (ROOT / "installer/Gela.iss").read_text(encoding="utf-8")
    version_info = (ROOT / "installer/version_info.txt").read_text(encoding="utf-8")
    assert '#define MyAppPublisher "Softcurse Systems"' in installer
    assert 'AppPublisherURL={#MyAppURL}' in installer
    assert "StringStruct('CompanyName', 'Softcurse Systems')" in version_info


def test_release_cleans_generated_source_package_metadata() -> None:
    build_script = (ROOT / "scripts/build_release.ps1").read_text(encoding="utf-8")
    ignore_file = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "clean_package_metadata.ps1" in build_script
    assert "*.egg-info/" in ignore_file


def test_release_validates_and_packages_voice_manifest() -> None:
    build_script = (ROOT / "scripts/build_release.ps1").read_text(encoding="utf-8")
    spec = (ROOT / "Gela.spec").read_text(encoding="utf-8")
    assert "validate_voice.py" in build_script
    assert '"recording_manifest.csv"' in spec


def test_signed_release_requires_explicit_certificate_and_verification() -> None:
    build_script = (ROOT / "scripts/build_installer.ps1").read_text(encoding="utf-8")
    signing_script = (ROOT / "scripts/sign_artifacts.ps1").read_text(encoding="utf-8")
    assert "RequireSigning" in build_script
    assert "GELA_SIGNING_THUMBPRINT" in build_script
    assert "sign_artifacts.ps1" in build_script
    assert '"/fd", "SHA256"' in signing_script
    assert '"/td", "SHA256"' in signing_script
    assert "TimeStamperCertificate" in signing_script
    assert "Get-AuthenticodeSignature" in signing_script
