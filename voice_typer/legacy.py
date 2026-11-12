"""One-time cleanup of the "power sharing" feature, removed in 0.9.3.

Before 0.9.3 a PC could share its AI power with others (a small HTTPS server on port 8765) or
use another PC's. That feature is gone: the app no longer opens any network port nor contacts
another computer. On the first start after the update, this removes what it left behind:
- its settings (the app already ignores them; they are also deleted from settings.json),
- its files: TLS certificate and key, per-device statistics,
- any Windows Firewall rule allowing Voice Typer.exe (Windows creates one when the user accepted
  the "allow on the network" prompt). Deleting a firewall rule needs administrator rights, so if
  some remain the window offers to remove them (Windows then asks for permission).
"""

import json
import subprocess
import sys
from pathlib import Path

from voice_typer import config as config_mod

OLD_KEYS = ("remote_mode", "host_port", "host_key", "remote_url", "remote_key", "remote_fingerprint",
            "host_allow_internet", "client_id")
OLD_FILES = ("host_certificate.pem", "host_certificate_key.pem", "server_devices.json")
MARKER_NAME = "power_sharing_removed"
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


def _settings_dir() -> Path:
    return config_mod.SETTINGS_DIR


def remove_files() -> list[str]:
    removed = []
    for name in OLD_FILES:
        f = _settings_dir() / name
        try:
            if f.exists():
                f.unlink()
                removed.append(name)
        except OSError:
            pass
    return removed


def purge_settings() -> list[str]:
    """Delete the old sharing keys from settings.json (access key, pinned host…)."""
    path = config_mod.SETTINGS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    found = [k for k in OLD_KEYS if k in data]
    if found:
        for k in found:
            data.pop(k)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    return found


def _programs() -> list[str]:
    """Executables a firewall rule could name: only the installed app (never a shared python.exe)."""
    return [sys.executable] if getattr(sys, "frozen", False) else []


def _powershell(script: str, timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, timeout=timeout, creationflags=_NO_WINDOW)


def _quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _rules_script(programs: list[str]) -> str:
    progs = ",".join(_quote(p.lower()) for p in programs)
    return (f"$p = @({progs}); Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue | "
            "Where-Object { $p -contains [Environment]::ExpandEnvironmentVariables($_.Program).ToLower() } | "
            "Get-NetFirewallRule -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }")


def firewall_rules(programs: list[str] | None = None) -> list[str]:
    programs = _programs() if programs is None else programs
    if not programs:
        return []
    try:
        out = _powershell(_rules_script(programs)).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _remove_script(names: list[str]) -> str:
    return f"Remove-NetFirewallRule -Name @({','.join(_quote(n) for n in names)}) -ErrorAction SilentlyContinue"


def remove_rules(names: list[str]) -> list[str]:
    """Try without elevation (works if the app runs as administrator); returns the rules left."""
    if not names:
        return []
    try:
        _powershell(_remove_script(names))
    except (OSError, subprocess.SubprocessError):
        pass
    return firewall_rules()


def remove_rules_elevated(names: list[str]) -> bool:
    """Ask Windows for administrator rights (UAC prompt) to delete the rules. True if launched."""
    import ctypes

    if not names:
        return True
    args = f'-NoProfile -WindowStyle Hidden -Command "{_remove_script(names)}"'
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell", args, None, 0) > 32


def remove_power_sharing(force: bool = False) -> dict:
    """Run once per PC, at startup before anything saves the settings (files + settings.json),
    then `cleanup_firewall()` in the background. Returns what was cleaned."""
    marker = _settings_dir() / MARKER_NAME
    if marker.exists() and not force:
        return {"done_before": True, "files": [], "settings": []}
    result = {"done_before": False, "files": remove_files(), "settings": purge_settings()}
    try:
        _settings_dir().mkdir(parents=True, exist_ok=True)
        marker.write_text("Voice Typer 0.9.3: power sharing removed.\n", encoding="utf-8")
    except OSError:
        pass
    return result


def cleanup_firewall() -> list[str]:
    """Slow (a few seconds): call from a background thread. Returns the rules that remain."""
    return remove_rules(firewall_rules())
