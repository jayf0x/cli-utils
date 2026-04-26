#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import tempfile
from pathlib import Path

import git

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, SelectionList


TREE_RE = re.compile(
    r"https://github\.com/([^/]+)/([^/]+)/tree/(.+)"
)


def parse_url(url):
    """
    Handles:
    https://github.com/user/repo/tree/main/path/to/folder

    Works even if branch contains slashes.
    """
    m = TREE_RE.match(url.strip("/"))
    if not m:
        raise ValueError("Bad github tree url")

    owner, repo, tail = m.groups()

    parts = tail.split("/")

    # heuristic:
    # try longest branch match from left side
    # by querying remote refs
    repo_url = f"https://github.com/{owner}/{repo}.git"

    tmp = tempfile.mkdtemp()

    try:
        r = git.Repo.clone_from(
            repo_url,
            tmp,
            no_checkout=True,
            depth=1
        )

        branches = [
            ref.remote_head
            for ref in r.remotes.origin.refs
        ]

        for i in range(len(parts),0,-1):
            candidate="/".join(parts[:i])
            if candidate in branches:
                return (
                    repo_url,
                    candidate,
                    "/".join(parts[i:])
                )

    finally:
        shutil.rmtree(tmp)

    raise Exception("Couldn't resolve branch/path")


def sparse_fetch(repo_url, branch, subdir):
    tmp=tempfile.mkdtemp(prefix="ghgrab-")

    print("Partial cloning...")

    repo = git.Repo.clone_from(
        repo_url,
        tmp,
        depth=1,
        no_checkout=True
    )

    gitcmd = repo.git

    gitcmd.sparse_checkout(
        "set",
        "--cone",
        subdir
    )

    gitcmd.checkout(branch)

    root=Path(tmp)/subdir

    files=[
        p for p in root.rglob("*")
        if p.is_file()
    ]

    return tmp, root, files


class Picker(App):

    def __init__(self, files):
        super().__init__()
        self.files=files
        self.selected=[]

    def compose(self)->ComposeResult:
        yield Header()

        opts=[]
        for i,f in enumerate(self.files):
            rel=str(f)
            kb=round(f.stat().st_size/1024,1)
            opts.append(
                (f"{rel} ({kb} KB)",i,False)
            )

        yield SelectionList(*opts)
        yield Footer()

    async def on_selection_list_selected_changed(self,event):
        self.selected=[
            self.files[i]
            for i in event.selection_list.selected
        ]

    async def on_key(self,event):
        if event.key=="enter":
            self.exit(self.selected)


def copy_selected(root, files):
    for f in files:
        rel=f.relative_to(root)
        out=Path.cwd()/rel

        out.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(f,out)
        print("Saved",rel)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("-y","--yes",
                    action="store_true")
    args=ap.parse_args()

    repo_url,branch,subdir=parse_url(
        args.url
    )
 
    tmp,root,files=sparse_fetch(
        repo_url,
        branch,
        subdir
    )

    try:
        if args.yes:
            chosen=files
        else:
            chosen=Picker(files).run()

        if chosen:
            copy_selected(root,chosen)

    finally:
        shutil.rmtree(tmp)


if __name__=="__main__":
    main()