#!/usr/bin/env python3
"""Abi Toads wallpaper tooling.

A small CLI for managing the Steam Workshop -> GitHub release pipeline for Abi
Toads animated wallpapers. It uses only the Python standard library plus the
secretspec SDK (provided by the devenv) to resolve credentials.

Subcommands:
    register <id>...  download item(s), hash, name, record in the manifest
    fetch  [--update]  download every manifest item and collect it into .wallpapers/
    verify            re-hash the collected .wallpapers/ files against the manifest
    publish  [--download]  download manifest items, cut a new release snapshot

Design / model (see README, CONTRIBUTING):
    * workshop.json maps a clean, filename-safe NAME -> {id, sha256}.
    * NAME is stable: it is the manifest key, the release asset name
      ("<Name>.mp4"), and the on-disk name. When a wallpaper's content changes,
      its entry keeps the same NAME and its sha256 is updated in place (keyed by
      the Workshop id, which is stable across versions).
    * Each publish cuts a NEW release tag (v1, v2, ...) holding the full current
      set, so GitHub's `releases/latest` always points at the current snapshot.
      Consumers fetch `releases/latest/download/<Name>.mp4`.
    * The original Workshop filename is NOT stored -- it is read from each
      item's project.json when needed. No URL is stored; consumers build it.

The videos come from Wallpaper Engine (paid app, Steam Guard). Steam and GitHub
credentials (STEAM_USER, GH_TOKEN) are resolved through secretspec, which each
environment provisions however it likes (see secretspec.toml). `register` is
interactive (name prompt + Steam Guard); `fetch`/`publish` are not. Before
uploading, publish re-hashes each local file against the committed sha256 and
aborts on any mismatch.
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
from functools import lru_cache
from pathlib import Path
from typing import NoReturn

from secretspec import SecretSpec, SecretSpecError

# workshop and repo ids
APP_ID = "431960"
REPO = "rhedgeco/abitoads"
# Each publish cuts a new snapshot release tagged v1, v2, ...; GitHub's
# `releases/latest` pointer then tracks the newest by semver.
RELEASE_TAG_PREFIX = "v"

# asset paths
MANIFEST = Path("workshop.json")
# steamcmd's download cache (raw, nested by workshop id); git-ignored.
STEAM_WORK = Path(".steam")
CONTENT_DIR = STEAM_WORK / "out" / "steamapps" / "workshop" / "content" / APP_ID
# A clean, flat collection of the videos named by their manifest names; the
# steam cache above is where they are downloaded, this is where they are copied
# for convenient local use. git-ignored.
COLLECTED_DIR = Path(".wallpapers")

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


# --------------------------------------------------------------------------
# secrets (resolved through secretspec; each environment provisions the
# provider, see secretspec.toml)
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_secrets() -> dict[str, str]:
    """Resolve the declared secrets via secretspec, cached for the process.

    The secrets are declared optional in secretspec.toml so resolution never
    fails just because one is absent; each command enforces only the secret it
    actually needs via require_secret(). The provider (env, dotenv, keyring,
    ...) is chosen by the environment, not here.
    """
    try:
        resolved = SecretSpec.builder().with_reason("abitoads wallpaper tooling").load()
    except SecretSpecError as error:
        die(f"could not resolve secrets via secretspec: {error}")
    return {name: (secret.get or "") for name, secret in resolved.secrets.items()}


def require_secret(name: str) -> str:
    value = load_secrets().get(name)
    if not value:
        die(f"{name} is not set; provision it via secretspec (see secretspec.toml).")
    return value


def ensure_github_auth() -> None:
    """Ensure gh is available and has a token, resolved through secretspec.

    gh reads GH_TOKEN from the environment, so exporting the resolved value is
    enough to authenticate it.
    """
    if not is_on_path("gh"):
        die("gh is required but not found on PATH; enter the devenv shell first.")
    os.environ["GH_TOKEN"] = require_secret("GH_TOKEN")


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


def collect_video(name: str, video_path: Path) -> Path:
    """Copy a downloaded video into COLLECTED_DIR as '<name>.mp4'.

    This gives a clean, flat folder of the videos named by their manifest
    names, separate from steamcmd's nested download cache. Copies only when the
    destination is missing or differs, so re-runs are cheap.
    """
    COLLECTED_DIR.mkdir(parents=True, exist_ok=True)
    destination = COLLECTED_DIR / f"{name}.mp4"
    if (
        destination.is_file()
        and destination.stat().st_size == video_path.stat().st_size
    ):
        return destination
    shutil.copyfile(video_path, destination)
    return destination


# --------------------------------------------------------------------------
# steam
# --------------------------------------------------------------------------


def resolve_steam_user() -> str:
    """The Steam username, resolved through secretspec."""
    return require_secret("STEAM_USER")


def steam_download(user: str, ids: list[str]) -> None:
    """Download workshop items via steamcmd (interactive login).

    steamcmd is provided by the devenv (it wraps steam-run internally), so we
    just invoke it from PATH. Downloads land under STEAM_WORK via
    +force_install_dir so the rest of the tooling can find them.
    """
    if not is_on_path("steamcmd"):
        die("steamcmd not found on PATH; enter the devenv shell first.")

    # steamcmd resolves a relative +force_install_dir against its own install
    # location, not the current working directory, so pass an absolute path to
    # keep downloads inside this repo's STEAM_WORK where the tooling finds them.
    output_dir = (STEAM_WORK / "out").resolve()
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


def cmd_register(args: argparse.Namespace) -> int:
    user = resolve_steam_user()
    ids = args.ids

    steam_download(user, ids)

    data = load_manifest()
    wallpapers = data["wallpapers"]

    header("Registering wallpapers")
    changed = 0
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

        # An id is the stable identity of a wallpaper across content updates.
        existing_name = next(
            (
                name
                for name, entry in wallpapers.items()
                if entry.get("id") == workshop_id
            ),
            None,
        )

        label = paint(f"[{workshop_id}]", Style.DIM)
        heading = paint(title, Style.BOLD)
        source = paint(f"({filename})", Style.DIM)

        if existing_name is not None:
            if wallpapers[existing_name].get("sha256") == sha256:
                collect_video(existing_name, video_path)
                unchanged = paint("(unchanged)", Style.DIM)
                ok(f"[{workshop_id}] {paint(existing_name, Style.BOLD)} {unchanged}")
                continue
            # Same wallpaper, new content: update its hash in place, keep name.
            print()
            step(f"Updated wallpaper {label} {heading} {source}")
            wallpapers[existing_name]["sha256"] = sha256
            save_manifest(data)
            collect_video(existing_name, video_path)
            changed += 1
            asset = paint(f"{Glyph.ARROW} {existing_name}.mp4", Style.DIM)
            ok(f"updated {paint(existing_name, Style.BOLD)} {asset}")
            continue

        # Brand-new wallpaper: name it once.
        print()
        step(f"New wallpaper {label} {heading} {source}")
        name = prompt_name(suggest_name(title), wallpapers)
        wallpapers[name] = {"id": workshop_id, "sha256": sha256}
        save_manifest(data)
        collect_video(name, video_path)
        changed += 1
        asset = paint(f"{Glyph.ARROW} {name}.mp4", Style.DIM)
        ok(f"registered {paint(name, Style.BOLD)} {asset}")

    header("Done")
    where = paint(str(MANIFEST), Style.DIM)
    collected = paint(str(COLLECTED_DIR), Style.DIM)
    ok(f"{paint(str(changed), Style.BOLD)} added/updated, manifest at {where}")
    info(f"videos collected in {collected}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    user = resolve_steam_user()

    data = load_manifest()
    wallpapers = data["wallpapers"]
    if not wallpapers:
        die(f"{MANIFEST} has no wallpapers; run 'register' first.")

    ids = sorted({entry["id"] for entry in wallpapers.values()})
    steam_download(user, ids)

    header("Collecting videos")
    collected = 0
    updated = 0
    for name, entry in wallpapers.items():
        video_path = item_video_path(entry["id"])
        if not video_path:
            die(f"[{name}] video not found after download for id {entry['id']}.")
        actual = sha256_file(video_path)
        if actual != entry["sha256"]:
            if args.update:
                # Refresh the manifest to match the freshly-downloaded content.
                entry["sha256"] = actual
                save_manifest(data)
                updated += 1
                collect_video(name, video_path)
                ok(f"{name}.mp4 {paint('(sha256 updated)', Style.YELLOW)}")
                collected += 1
                continue
            die(
                f"[{name}] sha256 mismatch after download.\n"
                f"       manifest: {entry['sha256']}\n"
                f"       actual:   {actual}\n"
                f"       (pass --update to refresh the manifest to match)"
            )
        collect_video(name, video_path)
        ok(f"{name}.mp4")
        collected += 1

    header("Done")
    where = paint(str(COLLECTED_DIR), Style.DIM)
    ok(f"{paint(str(collected), Style.BOLD)} wallpaper(s) collected in {where}")
    if updated:
        manifest_path = paint(str(MANIFEST), Style.DIM)
        info(f"{updated} sha256(s) updated in {manifest_path}")
    return 0


def next_release_tag(repo: str) -> str:
    """The next snapshot tag: one past the highest existing vN (v1 if none)."""
    result = subprocess.run(
        [
            "gh",
            "release",
            "list",
            "--repo",
            repo,
            "--json",
            "tagName",
            "--jq",
            ".[].tagName",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    highest = 0
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            match = re.fullmatch(rf"{re.escape(RELEASE_TAG_PREFIX)}(\d+)", line.strip())
            if match:
                highest = max(highest, int(match.group(1)))
    return f"{RELEASE_TAG_PREFIX}{highest + 1}"


def cmd_verify(args: argparse.Namespace) -> int:
    data = load_manifest()
    wallpapers = data["wallpapers"]
    if not wallpapers:
        die(f"{MANIFEST} has no wallpapers.")

    checked = 0
    missing = 0
    mismatched: list[str] = []

    header("Verifying collected files")
    for name, entry in wallpapers.items():
        video_path = COLLECTED_DIR / f"{name}.mp4"
        if not video_path.is_file():
            info(f"{name} {Glyph.DASH} not collected in {COLLECTED_DIR}, skipping")
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
        f"{len(mismatched)} mismatched, {missing} not collected"
    )
    if mismatched:
        print(f"{paint(str(Glyph.ERROR), Style.RED)} {summary}")
        return 1
    ok(summary)
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    repo = REPO

    ensure_github_auth()

    data = load_manifest()
    wallpapers = data["wallpapers"]
    if not wallpapers:
        die(f"{MANIFEST} has no wallpapers; run 'register' first.")

    # Ensure every item is downloaded locally (CI re-downloads from Steam).
    if args.download:
        user = resolve_steam_user()
        ids = sorted({entry["id"] for entry in wallpapers.values()})
        steam_download(user, ids)

    tag = next_release_tag(repo)

    header(f"Publishing to {repo}")
    step(f"New release snapshot {paint(tag, Style.BOLD)}")

    with tempfile.TemporaryDirectory() as staging_name:
        staging = Path(staging_name)
        to_upload: list[Path] = []
        missing: list[str] = []
        mismatched: list[tuple[str, str, str]] = []

        # The release is a snapshot of the full current set; every wallpaper is
        # included, so consumers can grab everything from `releases/latest`.
        # Verify ALL of them before creating anything, so a mismatch never
        # leaves a half-published release and every problem is reported at once.
        for name, entry in wallpapers.items():
            asset = f"{name}.mp4"
            workshop_id = entry["id"]
            video_path = item_video_path(workshop_id)
            if video_path is None:
                missing.append(f"{name} (id {workshop_id})")
                continue
            # Never upload bytes that don't match the committed hash.
            actual = sha256_file(video_path)
            if actual != entry["sha256"]:
                mismatched.append((name, entry["sha256"], actual))
                continue
            link = staging / asset
            link.symlink_to(video_path)
            to_upload.append(link)
            step(f"queued {paint(asset, Style.BOLD)}")

        if missing or mismatched:
            lines = [
                paint(
                    "refusing to publish: the manifest does not match the ", Style.RED
                )
                + paint("downloaded videos.", Style.RED),
            ]
            if missing:
                lines.append("")
                lines.append(paint("missing downloads:", Style.BOLD))
                lines += [f"  - {item}" for item in missing]
            if mismatched:
                lines.append("")
                lines.append(paint("sha256 mismatches:", Style.BOLD))
                for name, expected, actual in mismatched:
                    lines.append(f"  - {paint(name, Style.BOLD)}")
                    lines.append(f"      manifest: {expected}")
                    lines.append(f"      actual:   {actual}")
            lines.append("")
            lines.append(
                "A mismatch means the upstream video no longer matches the "
                "approved manifest."
            )
            lines.append(
                "This needs maintainer review -- do NOT auto-accept it in CI. "
                "Locally run"
            )
            lines.append(
                "'just fetch --update' (or 're-register' the item), review the "
                "workshop.json"
            )
            lines.append(
                "diff, and commit it; the push re-triggers a clean publish. "
                "No release was created."
            )
            die("\n".join(lines))

        count = paint(str(len(to_upload)), Style.BOLD)
        tag_label = paint(tag, Style.BOLD)
        step(f"Creating {tag_label}, uploading {count} asset(s){Glyph.ELLIPSIS}")
        created = subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                *map(str, to_upload),
                "--repo",
                repo,
                "--latest",
                "--title",
                f"Abi Toads wallpapers {tag}",
                "--notes",
                (
                    "Abi Toads wallpapers, sourced from the Steam Workshop. A "
                    "snapshot of the full current set; assets are named "
                    "<Name>.mp4. See workshop.json for the sha256-pinned "
                    "manifest. Consumers can pull the current set from "
                    "releases/latest/download/<Name>.mp4."
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            die(f"failed to create release {tag}:\n{created.stderr.strip()}")

    header("Done")
    count = paint(str(len(to_upload)), Style.BOLD)
    ok(f"{count} asset(s) published to {repo} release {paint(tag, Style.BOLD)}")
    info("it is now the latest release; consumers can pull releases/latest")
    return 0


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abitoads", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser(
        "register", help="download item(s), name them, and record in the manifest"
    )
    register_parser.add_argument("ids", nargs="+", help="Steam Workshop item id(s)")
    register_parser.set_defaults(func=cmd_register)

    fetch_parser = subparsers.add_parser(
        "fetch", help="download every manifest item and collect it into .wallpapers/"
    )
    fetch_parser.add_argument(
        "--update",
        action="store_true",
        help="update the manifest sha256 to match downloaded content instead of "
        "failing on a mismatch",
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    publish_parser = subparsers.add_parser(
        "publish", help="upload manifest assets to the release"
    )
    publish_parser.add_argument(
        "--download",
        action="store_true",
        help="re-download manifest items from Steam before uploading",
    )
    publish_parser.set_defaults(func=cmd_publish)

    verify_parser = subparsers.add_parser(
        "verify", help="re-hash the collected .wallpapers/ files against the manifest"
    )
    verify_parser.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
