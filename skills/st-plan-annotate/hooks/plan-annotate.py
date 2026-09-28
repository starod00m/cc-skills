#!/usr/bin/env python3
"""plan-annotate.py - opens plan file in $EDITOR via tmux horizontal split.

file mode:
    plan-annotate.py <plan-file>

opens a copy of the plan file in $EDITOR in a tmux split-window -h (horizontal split).
waits for the editor to close, then writes the unified diff to a temp file and
prints the path to that file on stdout.
if no changes were made, prints nothing.

claude reads the path, then reads the diff file via Read tool to get changes,
applies changes to the plan file, and calls again - looping until no changes.

requirements:
    - a running tmux server with an attached client
    - $EDITOR set (defaults to micro)
"""

import datetime
import difflib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def get_diff(original: str, edited: str) -> str:
    """get unified diff between original and edited content.

    :param original: original file content
    :param edited: edited file content
    :return: unified diff string, empty if no changes
    """
    orig_lines = original.splitlines(keepends=True)
    edit_lines = edited.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, edit_lines, fromfile="original", tofile="annotated", n=2)
    return "".join(diff)


def resolve_split_target() -> str | None:
    """find the pane the user is looking at, to split the editor off it.

    the skill often runs from a Claude Code session detached from its terminal
    (e.g. a background job): the tmux server is up, but
    $TMUX/$TMUX_PANE were never inherited. splitting without an explicit target
    then lands in whatever session tmux considers current — usually one the
    user is not watching — so fall back to the active pane of the most recently
    active attached client.

    :return: tmux target pane, or None if no attached client was found
    """
    if os.environ.get("TMUX") is not None and os.environ.get("TMUX_PANE") is not None:
        return os.environ["TMUX_PANE"]

    clients = subprocess.run(
        ["tmux", "list-clients", "-F", "#{client_activity} #{client_name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    parsed = [line.split(" ", 1) for line in clients.stdout.splitlines() if " " in line]
    if not parsed:
        return None
    client = max(parsed, key=lambda entry: int(entry[0]) if entry[0].isdigit() else 0)[1]

    pane = subprocess.run(
        ["tmux", "display-message", "-p", "-c", client, "#{pane_id}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return pane.stdout.strip() or None


def open_editor(filepath: Path) -> int:
    """open file in $EDITOR via tmux split-window -h, blocking until editor closes.

    uses tmux wait-for to block until the editor pane exits — no polling loop.

    :param filepath: path to the file to open in editor
    :return: 0 on success, 1 if the editor pane could not be opened
    """
    if shutil.which("tmux") is None:
        print("error: tmux not found in PATH", file=sys.stderr)
        return 1

    target = resolve_split_target()
    if target is None:
        print(
            "error: no tmux pane to split into — the tmux server is not running "
            "or no client is attached to it",
            file=sys.stderr,
        )
        return 1

    editor = os.environ.get("EDITOR", "micro")
    # a missing editor dies inside the split pane, which closes at once and
    # signals the token — an empty diff indistinguishable from "no edits"
    if shutil.which(editor) is None:
        print(f"error: editor {editor!r} not found in PATH (set $EDITOR)", file=sys.stderr)
        return 1

    token = f"plan-done-{uuid.uuid4().hex}"

    wrapper = f'{shlex.quote(editor)} {shlex.quote(str(filepath))}; tmux wait-for -S {shlex.quote(token)}'

    split = subprocess.run(
        ["tmux", "split-window", "-h", "-l", "50%", "-t", target, "sh", "-c", wrapper],
        capture_output=True,
        text=True,
        check=False,
    )
    # bailing out here matters: with no editor pane nothing ever signals the
    # token, and `wait-for` below would hang for the rest of the session
    if split.returncode != 0:
        print(f"error: tmux split-window failed: {split.stderr.strip()}", file=sys.stderr)
        return 1

    # blocks until the editor pane sends the signal via wait-for -S
    subprocess.run(
        ["tmux", "wait-for", token],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    return 0


def archive_diff(plan_file: Path, diff: str) -> None:
    """save a copy of the diff next to the plan file under .history/.

    best-effort: if the plan is outside a writable directory or the archive
    write fails, silently skip — the primary diff is already in /tmp and has
    been handed to the caller.

    :param plan_file: path to the plan file being annotated
    :param diff: unified diff text to archive
    """
    try:
        history_dir = plan_file.parent / ".history"
        history_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_path = history_dir / f"{ts}-{plan_file.stem}.patch"
        archive_path.write_text(diff)
    except OSError:
        pass


def run_file_mode(plan_file: Path) -> None:
    """open plan copy in editor, write diff to a temp file, print its path to stdout.

    if no changes were made, prints nothing.

    :param plan_file: path to the plan file to annotate
    """
    if not plan_file.exists():
        print(f"error: file not found: {plan_file}", file=sys.stderr)
        sys.exit(1)

    plan_content = plan_file.read_text()

    tmp_dir = tempfile.gettempdir()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", prefix="plan-review-", delete=False, dir=tmp_dir) as tmp:
        tmp.write(plan_content)
        tmp_path = Path(tmp.name)

    try:
        if open_editor(tmp_path) != 0:
            sys.exit(1)

        edited_content = tmp_path.read_text()
        diff = get_diff(plan_content, edited_content)

        if diff:
            fd, diff_path_str = tempfile.mkstemp(prefix="plan-diff-", suffix=".patch", dir=tmp_dir)
            diff_path = Path(diff_path_str)
            try:
                os.write(fd, diff.encode())
            finally:
                os.close(fd)
            archive_diff(plan_file, diff)
            # print path so agent reads via Read tool — never loses the diff
            print(diff_path)
            sys.stdout.flush()
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> None:
    """entry point."""
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <plan-file>", file=sys.stderr)
        sys.exit(1)

    run_file_mode(Path(sys.argv[1]))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\r\033[K", end="")
        sys.exit(130)
