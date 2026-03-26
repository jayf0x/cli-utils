#!/usr/bin/env python3
"""
find_component.py

Find all <Component ... /> instances (self-closing or not) in source files.

Usage:
  python find_component.py UiAvatar
  python find_component.py UserIcon --ext .jsx
"""

import os, re
import fnmatch
import argparse
from pathlib import Path
from typing import List, Iterable, Tuple
from subprocess import run

# Default blacklist directories
DEFAULT_BLACKLIST = [
    "node_modules",
    "dist",
    "build",
    ".git",
    ".*",          # hidden files/dirs
    ".venv",
    "__pycache__",
    "helm",
]


def build_component_regex(component: str) -> re.Pattern:
    """
    Regex that matches either:
      - <Component ... />  (self-closing)
      - <Component ...> ... </Component>  (with children)
    Uses non-greedy matching to capture attributes.
    """
    name = re.escape(component)
    return re.compile(
        rf"<{name}\b.*?(?:\/>|>.*?<\/{name}>)",
        re.DOTALL,
    )


def load_gitignore_patterns(root: Path) -> List[str]:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return []
    patterns = []
    for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("!"):
            continue
        if s.endswith("/"):
            s += "*"
        patterns.append(s)
    return patterns


def matches_any_pattern(relpath: str, patterns: Iterable[str]) -> bool:
    norm = relpath.replace(os.sep, "/")
    parts = norm.split("/")
    for pat in patterns:
        if fnmatch.fnmatch(norm, pat) or any(fnmatch.fnmatch(p, pat) for p in parts):
            return True
    return False


def gather_files(root: Path, ext: str, blacklist: List[str]) -> Iterable[Path]:
    root_str = str(root)
    for dirpath, dirnames, filenames in os.walk(root_str):
        for d in list(dirnames):
            rel = os.path.relpath(os.path.join(dirpath, d), start=root_str)
            if matches_any_pattern(rel, blacklist):
                dirnames.remove(d)
        for fname in filenames:
            if fname.endswith(ext):
                yield Path(dirpath) / fname


def find_instances(path: Path, pattern: re.Pattern) -> List[Tuple[str, int]]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    matches = []
    for m in pattern.finditer(content):
        snippet = m.group(0)
        line_no = content.count("\n", 0, m.start()) + 1
        matches.append((snippet, line_no))
    return matches



def main():
    root = Path.cwd()

    ap = argparse.ArgumentParser(description="Find JSX/TSX component instances in source files.")
    ap.add_argument("component", help="Component name to search for (e.g. UiAvatar)")
    ap.add_argument("--ext", default=".tsx", help="File extension to search (default: .tsx)")
    ap.add_argument("--out", default=root, help="Output dir (default: is the current dir)")
    args = ap.parse_args()

    if not args.out or not args.ext or not args.component:
        ap.error("Missing params")
        return
    
    if not args.ext.startswith("."):
        args.ext = "." + args.ext

    blacklist = DEFAULT_BLACKLIST + load_gitignore_patterns(root)
    regex = build_component_regex(args.component)

    results: List[Tuple[str, str, int]] = []
    for fpath in gather_files(root, args.ext, blacklist):
        rel = os.path.relpath(fpath, start=root)
        for snippet, line in find_instances(fpath, regex):
            results.append((snippet, rel, line))

    if not len(results):
        print(f"Exit. Could not find any instances.")
        return

    print(f"✅ Found {len(results)} instances\n")

    out_lines: List[str] = []
    for snippet, relpath, line_no in results:
        out_lines.append(f"// {relpath}:{line_no}")
        out_lines.append(snippet)
        out_lines.append("")

    output_text = "\n".join(out_lines)

    out_path = os.path.expanduser(f"{args.out}/grep-component-results-{args.component}.ts")
    Path(out_path).write_text(output_text, encoding="utf-8")

    # try formatting doc 
    try: 
        run(["yarn", "prettier", "--write", out_path ])
    except Exception as e: 
        print('[i] Failed to format output file')


if __name__ == "__main__":
    main()
