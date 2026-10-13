#!/usr/bin/env python3
"""Abi Toads wallpaper tooling.

A small, stdlib-only CLI for managing the Steam Workshop -> GitHub release
pipeline for Abi Toads animated wallpapers.

Subcommands:
    fetch    <user> <id>...   download item(s), hash, name, record in manifest
    publish  [--download [user]]  download manifest items, upload missing assets
    verify                    re-hash locally-downloaded files against manifest

Design / model (see README, CONTRIBUTING):
    * workshop.json maps a clean, filename-safe NAME -> {id, sha256}.
    * NAME is the identity: it is the manifest key, the release asset name
      ("<Name>.mp4"), and the on-disk name. Names are WRITE-ONCE / immutable.
    * When a wallpaper's content changes, it is recorded under a NEW name
      (collision -> append V2, V3, ...); the old entry is frozen forever.
    * The original Workshop filename is NOT stored -- it is read from each
      item's project.json when needed. No URL is stored; consumers build it.

The videos come from Wallpaper Engine (paid app, Steam Guard), so `fetch`
is interactive and local. `publish` can run anywhere with a usable Steam
session (e.g. a self-hosted CI runner); with --download it downloads from
Steam first, using the username passed to --download or, if omitted,
$STEAM_USER. Before uploading, publish re-hashes each local file
against the committed sha256 and aborts on any mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import NoReturn

# workshop and repo ids
APP_ID = "431960"
REPO = "rhedgeco/abitoads"
RELEASE_TAG = "wallpapers"

# asset paths
MANIFEST = Path("workshop.json")
STEAM_WORK = Path(".steam-fetch")
CONTENT_DIR = STEAM_WORK / "out" / "steamapps" / "workshop" / "content" / APP_ID

# video filename validator
VALID_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


# --------------------------------------------------------------------------
# console styling (stdlib-only; auto-disables when not a TTY or NO_COLOR set)
# --------------------------------------------------------------------------


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stderr.isatty()


USE_COLOR = _color_enabled()


class Style(str, Enum):
    """ANSI SGR codes, used with paint()."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"


class Glyph(str, Enum):
    """Unicode decorations for console output."""

    BAR = "\u2500"
    PIPE = "\u2502"
    STEP = "\u203a"
    OK = "\u2714"
    WARNING = "\u26a0"
    ERROR = "\u2717"
    ARROW = "\u2192"
    DASH = "\u2014"
    ELLIPSIS = "\u2026"

    def __str__(self) -> str:
        return self.value


def paint(text: str, *styles: Style) -> str:
    """Wrap text in the given ANSI styles (a no-op when color is disabled)."""
    if not USE_COLOR or not styles:
        return text
    prefix = "".join(style.value for style in styles)
    return f"{prefix}{text}{Style.RESET.value}"


def header(title: str) -> None:
    """A titled section separator."""
    rule = str(Glyph.BAR) * max(4, len(title) + 2)
    print()
    print(paint(f"{Glyph.PIPE} {title}", Style.CYAN, Style.BOLD))
    print(paint(rule, Style.CYAN, Style.DIM))


def step(message: str) -> None:
    print(f"{paint(str(Glyph.STEP), Style.CYAN)} {message}")


def ok(message: str) -> None:
    print(f"{paint(str(Glyph.OK), Style.GREEN)} {message}")


def warn(message: str) -> None:
    print(f"{paint(str(Glyph.WARNING), Style.YELLOW)} {message}", file=sys.stderr)


def info(message: str) -> None:
    print(f"  {paint(message, Style.DIM)}")


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def die(message: str) -> NoReturn:
    print(f"{paint(f'{Glyph.ERROR} error:', Style.RED)} {message}", file=sys.stderr)
    sys.exit(1)


def is_on_path(command: str) -> bool:
    return shutil.which(command) is not None


def ensure_github_auth() -> None:
    """Fail early with a friendly message if gh has no usable credentials."""
    if not is_on_path("gh"):
        die("gh is required but not found on PATH; enter the devenv shell first.")
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        die(
            "gh is not authenticated.\n"
            "       run 'gh auth login' or set $GH_TOKEN to a GitHub token."
        )


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"appId": APP_ID, "wallpapers": {}}
    with MANIFEST.open() as manifest_file:
        data = json.load(manifest_file)
    data.setdefault("appId", APP_ID)
    data.setdefault("wallpapers", {})
    return data


def save_manifest(data: dict) -> None:
    # Sort wallpapers by name so diffs stay stable.
    data["wallpapers"] = dict(sorted(data["wallpapers"].items()))
    temp_path = MANIFEST.with_suffix(".json.tmp")
    with temp_path.open("w") as temp_file:
        json.dump(data, temp_file, indent=2)
        temp_file.write("\n")
    temp_path.replace(MANIFEST)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as video_file:
        for chunk in iter(lambda: video_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def item_directory(workshop_id: str) -> Path:
    return CONTENT_DIR / workshop_id


def read_project(workshop_id: str) -> dict | None:
    project_path = item_directory(workshop_id) / "project.json"
    if not project_path.exists():
        return None
    try:
        with project_path.open() as project_file:
            return json.load(project_file)
    except (OSError, json.JSONDecodeError):
        return None


def item_video_path(workshop_id: str) -> Path | None:
    """Locate the downloaded video for an item via its project.json 'file'."""
    project = read_project(workshop_id)
    if not project:
        return None
    filename = project.get("file")
    if not filename:
        return None
    video_path = item_directory(workshop_id) / filename
    return video_path if video_path.is_file() else None


# --------------------------------------------------------------------------
# steam
# --------------------------------------------------------------------------


def resolve_steam_user(override: str | None = None) -> str:
    if override:
        return override
    env = os.environ.get("STEAM_USER")
    if env:
        return env
    die("no Steam username: pass it to --download or set $STEAM_USER")


def steam_download(user: str, ids: list[str]) -> None:
    """Download workshop items via steamcmd (interactive login).

    steamcmd is provided by the devenv (it wraps steam-run internally), so we
    just invoke it from PATH. Downloads land under STEAM_WORK via
    +force_install_dir so the rest of the tooling can find them.
    """
    if not is_on_path("steamcmd"):
        die("steamcmd not found on PATH; enter the devenv shell first.")

    output_dir = STEAM_WORK / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    command = ["steamcmd", "+force_install_dir", str(output_dir), "+login", user]
    for workshop_id in ids:
        command += ["+workshop_download_item", APP_ID, workshop_id]
    command += ["+quit"]

    header("Steam download")
    step(f"Logging in as {paint(user, Style.BOLD)}")
    info("you may be prompted for your password and Steam Guard code")
    step(f"Downloading {paint(str(len(ids)), Style.BOLD)} item(s){Glyph.ELLIPSIS}")
    print()

    subprocess.run(command, check=True)


# --------------------------------------------------------------------------
# naming
# --------------------------------------------------------------------------


def is_valid_name(name: str) -> bool:
    return bool(VALID_NAME_PATTERN.match(name))


def suggest_name(title: str) -> str:
    """Derive an editable default name from a Workshop title."""
    stripped = re.sub(r"\s*by Abi Toads", "", title, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*Abi Toads", "", stripped, flags=re.IGNORECASE)
    words = re.split(r"[^A-Za-z0-9]+", stripped)
    return "".join(word[:1].upper() + word[1:].lower() for word in words if word)


def free_name(base: str, wallpapers: dict) -> str:
    """First non-colliding variant: base, then baseV2, baseV3, ..."""
    if base not in wallpapers:
        return base
    version = 2
    while f"{base}V{version}" in wallpapers:
        version += 1
    return f"{base}V{version}"


def prompt_name(suggestion: str, wallpapers: dict) -> str:
    while True:
        hint = f" {paint(f'[{suggestion}]', Style.DIM)}" if suggestion else ""
        prompt = f"    {paint('Name', Style.CYAN)}{hint}: "
        try:
            with open("/dev/tty") as terminal:
                sys.stderr.write(prompt)
                sys.stderr.flush()
                name = terminal.readline().strip()
        except OSError:
            die("no TTY available to prompt for a name.")
        name = name or suggestion
        if not name:
            warn("a name is required.")
            continue
        if not is_valid_name(name):
            warn("invalid: letters, digits, - or _, starting with a letter.")
            continue
        if name in wallpapers:
            warn(f"'{name}' is already used; pick another.")
            continue
        return name


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------


def cmd_fetch(args: argparse.Namespace) -> int:
    user = args.user
    ids = args.ids

    steam_download(user, ids)

    data = load_manifest()
    wallpapers = data["wallpapers"]

    header("Recording wallpapers")
    added = 0
    for workshop_id in ids:
        project = read_project(workshop_id)
        if not project:
            warn(f"[{workshop_id}] no project.json (download failed?), skipping")
            continue
        video_path = item_video_path(workshop_id)
        if not video_path:
            warn(f"[{workshop_id}] video file missing, skipping")
            continue

        title = project.get("title", "")
        filename = project.get("file", "")
        sha256 = sha256_file(video_path)

        # Already recorded with this exact content? no-op.
        existing = next(
            (
                name
                for name, entry in wallpapers.items()
                if entry.get("id") == workshop_id and entry.get("sha256") == sha256
            ),
            None,
        )
        if existing:
            unchanged = paint("(unchanged)", Style.DIM)
            ok(
                f"[{workshop_id}] already recorded as "
                f"{paint(existing, Style.BOLD)} {unchanged}"
            )
            continue

        prior_names = [
            name for name, entry in wallpapers.items() if entry.get("id") == workshop_id
        ]

        print()
        label = paint(f"[{workshop_id}]", Style.DIM)
        heading = paint(title, Style.BOLD)
        source = paint(f"({filename})", Style.DIM)
        if not prior_names:
            step(f"New wallpaper {label} {heading} {source}")
        else:
            step(f"Updated wallpaper {label} {heading} {source}")
            info("content changed; existing name(s) are kept frozen:")
            for prior_name in prior_names:
                info(f"  - {prior_name}")
            info("choose a NEW name for this version.")

        suggestion = free_name(suggest_name(title), wallpapers)
        name = prompt_name(suggestion, wallpapers)

        wallpapers[name] = {"id": workshop_id, "sha256": sha256}
        save_manifest(data)
        added += 1
        asset = paint(f"{Glyph.ARROW} {name}.mp4", Style.DIM)
        ok(f"added {paint(name, Style.BOLD)} {asset}")

    header("Done")
    where = paint(str(MANIFEST), Style.DIM)
    ok(f"{paint(str(added), Style.BOLD)} added, manifest at {where}")
    return 0


def github_asset_names(repo: str, tag: str) -> set[str]:
    result = subprocess.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            repo,
            "--json",
            "assets",
            "--jq",
            ".assets[].name",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def cmd_publish(args: argparse.Namespace) -> int:
    repo = REPO
    tag = RELEASE_TAG

    ensure_github_auth()

    data = load_manifest()
    wallpapers = data["wallpapers"]
    if not wallpapers:
        die(f"{MANIFEST} has no wallpapers; run 'fetch' first.")

    # Ensure every item is downloaded locally (CI re-downloads from Steam).
    if args.download is not None:
        user = resolve_steam_user(args.download or None)
        ids = sorted({entry["id"] for entry in wallpapers.values()})
        steam_download(user, ids)

    # Ensure the single release exists.
    header(f"Publishing to {repo}")
    step(f"Ensuring release {paint(tag, Style.BOLD)} exists{Glyph.ELLIPSIS}")
    exists = (
        subprocess.run(
            ["gh", "release", "view", tag, "--repo", repo],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    if not exists:
        created = subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                "--repo",
                repo,
                "--title",
                "Abi Toads wallpapers",
                "--notes",
                (
                    "Abi Toads wallpapers, sourced from the Steam Workshop. "
                    "Assets are named <Name>.mp4 and are immutable; see "
                    "workshop.json for the sha256-pinned manifest."
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            die(f"failed to create release {tag}:\n{created.stderr.strip()}")
        ok(f"created release {paint(tag, Style.BOLD)}")

    existing = github_asset_names(repo, tag)

    with tempfile.TemporaryDirectory() as staging_name:
        staging = Path(staging_name)
        to_upload: list[Path] = []
        skipped = 0

        for name, entry in wallpapers.items():
            asset = f"{name}.mp4"
            if asset in existing:
                skipped += 1
                continue
            workshop_id = entry["id"]
            video_path = item_video_path(workshop_id)
            if video_path is None:
                die(
                    f"[{name}] expected video not found for id {workshop_id}; "
                    f"download it first (fetch/publish --download)."
                )
            # Never upload bytes that don't match the committed hash.
            actual = sha256_file(video_path)
            if actual != entry["sha256"]:
                die(
                    f"[{name}] sha256 mismatch; refusing to publish.\n"
                    f"       manifest: {entry['sha256']}\n"
                    f"       actual:   {actual}"
                )
            link = staging / asset
            link.symlink_to(video_path)
            to_upload.append(link)
            step(f"queued {paint(asset, Style.BOLD)}")

        if skipped:
            info(f"skipping {skipped} asset(s) already present (immutable)")

        if not to_upload:
            ok("nothing new to upload; release is up to date")
            return 0

        count = paint(str(len(to_upload)), Style.BOLD)
        step(f"Uploading {count} new asset(s){Glyph.ELLIPSIS}")
        subprocess.run(
            ["gh", "release", "upload", tag, *map(str, to_upload), "--repo", repo],
            check=True,
        )

    header("Done")
    count = paint(str(len(to_upload)), Style.BOLD)
    ok(f"{count} asset(s) uploaded to {repo} release {paint(tag, Style.BOLD)}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    data = load_manifest()
    wallpapers = data["wallpapers"]
    if not wallpapers:
        die(f"{MANIFEST} has no wallpapers.")

    checked = 0
    missing = 0
    mismatched: list[str] = []

    header("Verifying local files")
    for name, entry in wallpapers.items():
        video_path = item_video_path(entry["id"])
        if not video_path:
            info(f"{name} {Glyph.DASH} not downloaded locally, skipping")
            missing += 1
            continue
        actual = sha256_file(video_path)
        if actual == entry["sha256"]:
            ok(name)
            checked += 1
        else:
            mark = paint(str(Glyph.ERROR), Style.RED)
            label = paint(name, Style.BOLD)
            status = paint("MISMATCH", Style.RED)
            print(f"{mark} {label} {status}")
            info(f"manifest: {entry['sha256']}")
            info(f"actual:   {actual}")
            mismatched.append(name)

    header("Summary")
    summary = (
        f"{paint(str(checked), Style.BOLD)} ok, "
        f"{len(mismatched)} mismatched, {missing} not downloaded"
    )
    if mismatched:
        print(f"{paint(str(Glyph.ERROR), Style.RED)} {summary}")
        return 1
    ok(summary)
    return 0


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abitoads", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch", help="download item(s) and record in manifest"
    )
    fetch_parser.add_argument("user", help="Steam username that owns Wallpaper Engine")
    fetch_parser.add_argument("ids", nargs="+", help="Steam Workshop item id(s)")
    fetch_parser.set_defaults(func=cmd_fetch)

    publish_parser = subparsers.add_parser(
        "publish", help="upload manifest assets to the release"
    )
    publish_parser.add_argument(
        "--download",
        nargs="?",
        const="",
        default=None,
        metavar="STEAM_USER",
        help=(
            "re-download manifest items from Steam before uploading; "
            "optionally takes the Steam username (defaults to $STEAM_USER)"
        ),
    )
    publish_parser.set_defaults(func=cmd_publish)

    verify_parser = subparsers.add_parser(
        "verify", help="re-hash local files against the manifest"
    )
    verify_parser.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
