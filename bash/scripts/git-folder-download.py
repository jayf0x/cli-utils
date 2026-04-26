#!/usr/bin/env python3
"""
ghgrab — download a GitHub subfolder, pick exactly which files you want.

Sparse-checkout scopes the clone to the target subfolder only.
The picker then lets you choose individual files *within* that folder —
so only the subfolder is fetched from the network, and only your chosen
files land in the current directory.
"""

import argparse
import re
import shutil
import tempfile
from pathlib import Path

import git

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from rich.text import Text


# ── URL parsing ───────────────────────────────────────────────────────────────

TREE_RE = re.compile(
    r"https://github\.com/([^/]+)/([^/]+)/tree/(.+)"
)


def parse_url(url: str) -> tuple[str, str, str]:
    """
    Resolve a GitHub tree URL into (repo_url, branch, subdir).

    Works even when the branch name contains slashes: tries the longest
    left-anchored prefix of the path that matches a known remote branch.
    """
    m = TREE_RE.match(url.strip("/"))
    if not m:
        raise ValueError(
            f"Not a valid GitHub tree URL: {url!r}\n"
            "Expected: https://github.com/<owner>/<repo>/tree/<branch>[/<path>]"
        )

    owner, repo, tail = m.groups()
    parts = tail.split("/")
    repo_url = f"https://github.com/{owner}/{repo}.git"

    tmp = tempfile.mkdtemp(prefix="ghgrab-refs-")
    try:
        r = git.Repo.clone_from(repo_url, tmp, no_checkout=True, depth=1)
        branches = [ref.remote_head for ref in r.remotes.origin.refs]
    except git.GitCommandError as exc:
        raise RuntimeError(
            f"Could not reach repository {repo_url!r}.\n"
            f"Git error: {exc}"
        ) from exc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # Try longest-match branch first
    for i in range(len(parts), 0, -1):
        candidate = "/".join(parts[:i])
        if candidate in branches:
            return repo_url, candidate, "/".join(parts[i:])

    raise ValueError(
        f"Could not match any branch in {branches} from path {tail!r}.\n"
        "Double-check the URL."
    )


# ── Sparse fetch ──────────────────────────────────────────────────────────────

def sparse_fetch(repo_url: str, branch: str, subdir: str) -> tuple[Path, Path, list[Path]]:
    """
    Clone *only* `subdir` from the repo using cone-mode sparse checkout.

    Returns (tmp_root, subdir_root, [file_paths]).
    The caller is responsible for rmtree(tmp_root) when done.

    NOTE: cone-mode sparse checkout fetches exactly one directory subtree
    from the server — not the whole repository. File selection in the UI
    further narrows what gets written to disk.
    """
    tmp = Path(tempfile.mkdtemp(prefix="ghgrab-"))

    try:
        repo = git.Repo.clone_from(
            repo_url,
            str(tmp),
            depth=1,
            no_checkout=True,
        )

        git_cmd = repo.git

        # Cone mode: only the specified directory tree is transferred.
        git_cmd.sparse_checkout("set", "--cone", subdir)
        git_cmd.checkout(branch)

    except git.GitCommandError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(
            f"Sparse checkout failed for {subdir!r} on branch {branch!r}.\n"
            f"Git error: {exc}"
        ) from exc

    root = tmp / subdir
    if not root.exists():
        shutil.rmtree(tmp, ignore_errors=True)
        raise FileNotFoundError(
            f"Path {subdir!r} not found in the repository after checkout.\n"
            "Check that the path in the URL is correct."
        )

    files = sorted(p for p in root.rglob("*") if p.is_file())
    return tmp, root, files


# ── TUI Picker ────────────────────────────────────────────────────────────────

class FileTable(ScrollView):
    """
    Keyboard-navigable file picker with checkbox-style rows.

    Keys
    ────
    ↑ / ↓ / j / k   move cursor
    Space            toggle selection on focused row
    Enter            confirm (only when ≥ 1 item selected; bell + error otherwise)
    a                select all
    n                deselect all
    """

    DEFAULT_CSS = """
    FileTable {
        height: 1fr;
        border: solid $primary;
    }
    """

    cursor: reactive[int] = reactive(0)
    checked: reactive[frozenset] = reactive(frozenset)

    def __init__(self, files: list[Path], root: Path, **kwargs):
        super().__init__(**kwargs)
        self.files = files
        self.root = root
        # Tell ScrollView how tall the virtual content is (1 row per file)
        from textual.geometry import Size
        self.virtual_size = Size(0, len(files))

    def on_mount(self) -> None:
        self.checked = frozenset()
        self.can_focus = True
        self.focus()

    # ── rendering ─────────────────────────────────────────────────────────────

    def render_line(self, y: int):
        from textual.strip import Strip
        from rich.segment import Segment
        from rich.style import Style

        scroll_y = self.scroll_offset.y
        row = scroll_y + y
        if row >= len(self.files):
            return Strip.blank(self.size.width)

        f = self.files[row]
        rel = str(f.relative_to(self.root))
        try:
            kb = f.stat().st_size / 1024
            size_str = f"{kb:>7.1f} KB"
        except OSError:
            size_str = "   ?.? KB"

        is_checked = row in self.checked
        is_focused = row == self.cursor

        checkbox = "[✓]" if is_checked else "[ ]"

        if is_focused and is_checked:
            base  = Style(color="black", bgcolor="bright_cyan", bold=True)
            chk   = Style(color="black", bgcolor="bright_cyan", bold=True)
        elif is_focused:
            base  = Style(color="black", bgcolor="bright_white")
            chk   = Style(color="black", bgcolor="bright_white")
        elif is_checked:
            base  = Style(color="bright_cyan")
            chk   = Style(color="bright_cyan", bold=True)
        else:
            base  = Style(color="white")
            chk   = Style(color="bright_black")

        name_width = max(0, self.size.width - len(checkbox) - len(size_str) - 4)
        prefix = f" {checkbox}  "
        body   = f"{rel:<{name_width}}{size_str} "

        return Strip(
            [Segment(prefix, chk), Segment(body, base)],
            self.size.width,
        )

    # ── key handling ──────────────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        if event.key in ("up", "k"):
            self._move(-1); event.stop()
        elif event.key in ("down", "j"):
            self._move(1); event.stop()
        elif event.key == "space":
            self._toggle(self.cursor); event.stop()
        elif event.key == "enter":
            if not self.checked:
                self.app.bell()
                self.app.query_one("#status", Static).update(
                    Text(" ⚠  No files selected — use Space to select, or 'a' for all", style="bold red")
                )
            else:
                self.app.exit(result=[self.files[i] for i in sorted(self.checked)])
            event.stop()
        elif event.key == "a":
            self.checked = frozenset(range(len(self.files)))
            self._clear_status(); self.refresh(); event.stop()
        elif event.key == "n":
            self.checked = frozenset()
            self._clear_status(); self.refresh(); event.stop()

    def _move(self, delta: int) -> None:
        self.cursor = max(0, min(len(self.files) - 1, self.cursor + delta))
        self._scroll_to_cursor()
        self.refresh()

    def _toggle(self, idx: int) -> None:
        c = set(self.checked)
        c.discard(idx) if idx in c else c.add(idx)
        self.checked = frozenset(c)
        self._clear_status()
        self.refresh()

    def _scroll_to_cursor(self) -> None:
        top    = self.scroll_offset.y
        bottom = top + self.size.height - 1
        if self.cursor < top:
            self.scroll_to(y=self.cursor, animate=False)
        elif self.cursor > bottom:
            self.scroll_to(y=self.cursor - self.size.height + 1, animate=False)

    def _clear_status(self) -> None:
        n = len(self.checked)
        msg = f" {n} file(s) selected" if n else ""
        self.app.query_one("#status", Static).update(Text(msg, style="dim"))


class Picker(App[list[Path]]):
    """Full-screen file picker."""

    BINDINGS = [
        Binding("q", "quit_none", "Quit without downloading", show=True),
    ]

    CSS = """
    #header-info {
        height: 3;
        padding: 0 1;
        color: $text-muted;
    }
    #status {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    """

    def __init__(self, files: list[Path], root: Path, subdir: str):
        super().__init__()
        self.files  = files
        self.root   = root
        self.subdir = subdir

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(
            f" Sparse-fetched [bold]{self.subdir or '(root)'}[/bold] — "
            f"[dim]{len(self.files)} file(s) available[/dim]\n"
            f" [dim]Space[/dim] toggle  [dim]a[/dim] all  [dim]n[/dim] none  "
            f"[dim]↑↓ / jk[/dim] navigate  [dim]Enter[/dim] download  [dim]q[/dim] quit",
            id="header-info",
        )
        yield FileTable(self.files, self.root)
        yield Static("", id="status")
        yield Footer()

    def action_quit_none(self) -> None:
        self.exit(result=[])


# ── File copy ─────────────────────────────────────────────────────────────────

def copy_selected(root: Path, files: list[Path]) -> None:
    for f in files:
        rel = f.relative_to(root)
        out = Path.cwd() / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        print(f"  ✓  {rel}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Download a GitHub subfolder using sparse checkout.\n"
            "Only the target directory is fetched; the picker lets you\n"
            "choose individual files within it."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "url",
        help="GitHub tree URL, e.g. https://github.com/org/repo/tree/main/src/utils",
    )
    ap.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip picker — download every file in the subfolder",
    )
    args = ap.parse_args()

    # ── resolve URL ──────────────────────────────────────────────────────────
    try:
        repo_url, branch, subdir = parse_url(args.url)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}")
        raise SystemExit(1)

    if not subdir:
        print(
            "warning: URL points to the repository root, not a subfolder.\n"
            "         Sparse checkout will include all top-level files.\n"
        )

    print(f"  repo   : {repo_url}")
    print(f"  branch : {branch}")
    print(f"  path   : /{subdir or '(root)'}")
    print()

    # ── sparse fetch ─────────────────────────────────────────────────────────
    print("Fetching file tree (sparse checkout — subfolder only)…")
    try:
        tmp, root, files = sparse_fetch(repo_url, branch, subdir)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"error: {exc}")
        raise SystemExit(1)

    if not files:
        shutil.rmtree(tmp, ignore_errors=True)
        print("No files found at that path.")
        raise SystemExit(0)

    print(f"  {len(files)} file(s) available in /{subdir or '(root)'}")
    print()

    # ── pick & copy ──────────────────────────────────────────────────────────
    try:
        if args.yes:
            chosen = files
        else:
            chosen = Picker(files, root, subdir).run()

        if not chosen:
            print("Nothing selected — exiting without writing any files.")
            return

        print(f"Copying {len(chosen)} file(s) to {Path.cwd()} …")
        copy_selected(root, chosen)
        print(f"\nDone. {len(chosen)} file(s) saved.")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()