"""Shared helpers for :add-app and :sync-shortcut (desktop launchers + dock pins)."""

import ast
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

HOME = Path.home()
APPS_DIR = HOME / "Applications"
ICON_DIR = HOME / ".local/share/icons/hicolor/256x256/apps"
ICON_DIR_SVG = HOME / ".local/share/icons/hicolor/scalable/apps"
DESKTOP_DIR = HOME / ".local/share/applications"
SYSTEM_DESKTOP_DIR = Path("/usr/share/applications")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_desktop_kv(path: Path) -> dict:
    """First-seen key=value pairs under [Desktop Entry], tolerant of malformed files."""
    kv = {}
    in_section = False
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("["):
            in_section = line == "[Desktop Entry]"
            continue
        if not in_section or "=" not in line or line.startswith("#"):
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k not in kv:
            kv[k] = v.strip()
    return kv


def enforce_desktop_fields(text: str, overrides: dict) -> str:
    """Rewrite/insert key=value lines, used to pin down Exec/Icon after AI or
    bundled .desktop content is used verbatim."""
    seen = set()
    out = []
    for line in text.splitlines():
        key = line.split("=", 1)[0] if "=" in line and not line.startswith("[") else None
        if key in overrides:
            out.append(f"{key}={overrides[key]}")
            seen.add(key)
        else:
            out.append(line)
    for k, v in overrides.items():
        if k not in seen:
            out.append(f"{k}={v}")
    return "\n".join(out) + "\n"


def write_desktop_file(app_id: str, name: str, exec_line: str, icon_field: str,
                        comment: str = "", categories: str = "Utility;",
                        path: Optional[Path] = None, terminal: bool = False) -> Path:
    lines = [
        "[Desktop Entry]",
        f"Name={name}",
        f"Comment={comment}",
        f"Exec={exec_line}",
    ]
    if path is not None:
        lines.append(f"Path={path}")
    lines += [
        f"Icon={icon_field}",
        f"Categories={categories}",
        f"Terminal={'true' if terminal else 'false'}",
        "Type=Application",
    ]

    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    dest = DESKTOP_DIR / f"{app_id}.desktop"
    dest.write_text("\n".join(lines) + "\n")
    dest.chmod(dest.stat().st_mode | 0o111)
    return dest


def install_icon_from_path(app_id: str, icon_src: Optional[Path]) -> Optional[str]:
    """Copies/converts an icon file into the icon theme dirs. Returns the Icon=
    field value to use, or None if no usable icon was found."""
    if not icon_src or not icon_src.exists():
        return None

    if icon_src.suffix.lower() == ".svg":
        ICON_DIR_SVG.mkdir(parents=True, exist_ok=True)
        shutil.copy(icon_src, ICON_DIR_SVG / f"{app_id}.svg")
        return app_id

    try:
        from PIL import Image
        im = Image.open(icon_src).convert("RGBA")
        ICON_DIR.mkdir(parents=True, exist_ok=True)
        im.save(ICON_DIR / f"{app_id}.png")
        return app_id
    except Exception:
        return None


def update_caches():
    subprocess.run(["update-desktop-database", str(DESKTOP_DIR)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["gtk-update-icon-cache", str(HOME / ".local/share/icons/hicolor")],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _dock_supported() -> bool:
    return "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "") and shutil.which("gsettings") is not None


def _get_favorites() -> list:
    out = subprocess.run(["gsettings", "get", "org.gnome.shell", "favorite-apps"],
                          capture_output=True, text=True).stdout.strip()
    return ast.literal_eval(out)


def _set_favorites(items: list):
    subprocess.run(["gsettings", "set", "org.gnome.shell", "favorite-apps", repr(items)])


def pin_to_dock(desktop_id: str, prog: str = "add-app"):
    if not _dock_supported():
        print(f"{prog}: not GNOME (or gsettings missing) — skipping dock pin. "
              f"Pin '{desktop_id}' manually if you want it in the dock.")
        return
    current = _get_favorites()
    if desktop_id in current:
        return
    current.append(desktop_id)
    _set_favorites(current)
    print(f"{prog}: pinned '{desktop_id}' to the dock")


def unpin_from_dock(desktop_id: str):
    if not _dock_supported():
        return
    current = _get_favorites()
    if desktop_id not in current:
        return
    _set_favorites([a for a in current if a != desktop_id])


def find_desktop_candidates(query: str) -> list:
    """Desktop files (user + system) whose filename or Name= contains query
    (case-insensitive substring)."""
    query = query.lower()
    results = []
    seen = set()
    for d in (DESKTOP_DIR, SYSTEM_DESKTOP_DIR):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.desktop")):
            stem = f.stem.lower()
            name = parse_desktop_kv(f).get("Name", "").lower()
            if query in stem or query in name:
                rp = str(f.resolve())
                if rp not in seen:
                    seen.add(rp)
                    results.append(f)
    return results


def ask_claude(prompt: str) -> Optional[str]:
    """Best-effort fallback to `claude -p` for cases plain heuristics can't resolve."""
    if not shutil.which("claude"):
        return None
    try:
        result = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    out = result.stdout.strip()
    return out if out.startswith("[Desktop Entry]") else None
