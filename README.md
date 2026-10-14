# Abitoads Wallpaper Collection

A mirror of [Abi Toads](https://abitoads.com) animated wallpapers, sourced from
the [Steam Workshop](https://steamcommunity.com/app/431960/workshop/) (Wallpaper
Engine).

The video files are **not stored in this repository.** Instead, this repo holds
a small manifest, [`workshop.json`](./workshop.json), that maps a clean name to
each wallpaper's Steam Workshop id and `sha256`. The actual `.mp4` files are
published as assets on GitHub releases, so the repo stays tiny and easy to pull
into other projects (e.g. a Nix config).

## How it works

- Every wallpaper has a clean, stable name (e.g. `AxolotlRide`). That name is
  the manifest key, the release asset name (`AxolotlRide.mp4`), and the on-disk
  filename.
- Each publish cuts a **new release** (`v1`, `v2`, ...) containing the **full
  current set** of wallpapers. GitHub's `releases/latest` pointer always tracks
  the newest, so the latest release is always the complete, current collection.
- When a wallpaper is updated by the artist, its entry keeps the **same name**
  and its `sha256` is updated in place; the next release carries the new bytes
  under that same asset name. There are no `V2`-style suffixes.
- Releases are snapshots: a given tag (e.g. `v3`) is never edited after it is
  cut, so anything pinned to a specific release tag keeps working. Your
  "version" is either a release tag or the commit of `workshop.json` you pin.

## Downloading the wallpapers

Each wallpaper is an individual asset on the latest release, downloadable by
name:

```
https://github.com/rhedgeco/abitoads/releases/latest/download/AxolotlRide.mp4
```

To pin a specific snapshot, swap `latest` for a tag, e.g.
`releases/download/v3/AxolotlRide.mp4`. The names and their integrity hashes are
listed in [`workshop.json`](./workshop.json).

### Using the wallpapers from Nix

Read the manifest and `fetchurl` each wallpaper by name, pinned by `sha256`:

```nix
let
  manifest = builtins.fromJSON (builtins.readFile ./workshop.json);
  baseUrl = "https://github.com/rhedgeco/abitoads/releases/latest/download";
in
  builtins.mapAttrs
    (name: w: pkgs.fetchurl {
      url = "${baseUrl}/${name}.mp4";
      sha256 = w.sha256;
    })
    manifest.wallpapers
```

This gives you an attrset of `name -> derivation`, so you can pull just the
wallpapers you want. Pin reproducibly by pairing a revision of `workshop.json`
with the matching release: the `sha256` in a given commit of the manifest
corresponds to the bytes in the release cut from it. For a frozen URL, replace
`latest` with that release's tag (e.g. `v3`). To update, bump the pinned
revision/tag together.

## Maintaining the collection

The video source of truth is the Steam Workshop, which requires an account that
owns Wallpaper Engine (a paid app) and an interactive, Steam Guard-confirmed
login. Registering new items is therefore done **locally** by the maintainer.
Everything runs through the [`justfile`](./justfile) inside a `devenv` shell,
which provides `just`, `python3`, `steamcmd`, `gh`, and the rest. Credentials
(`STEAM_USER`, `GH_TOKEN`) are resolved through
[secretspec](./secretspec.toml), so no usernames or tokens are passed on the
command line.

```sh
# Register one or more Workshop items by id into workshop.json. Prompts for a
# name for each new item; an updated item just has its sha256 refreshed in
# place (steamcmd handles login).
just register <workshop-id> [workshop-id ...]

# Download every manifest item from Steam, verify it against the manifest
# sha256, and collect the videos into .wallpapers/. Add --update to refresh
# the manifest sha256 to match downloaded content instead of failing on a
# mismatch (useful when the artist updates a wallpaper).
just fetch [--update]

# Re-hash the collected .wallpapers/ videos against the manifest.
just verify

# Cut a new release snapshot (v1, v2, ...) holding the full current set, which
# becomes releases/latest. Add --download to re-pull every manifest item from
# Steam first (what the publish runner uses).
just publish [--download]
```

Publishing re-hashes each `.mp4` against the committed `sha256` and aborts on any
mismatch, so a wrong hash can never reach the release. Pushing a `workshop.json`
change to `main` also triggers publishing automatically on the maintainer's
self-hosted runner, cutting a fresh release snapshot; see
[`CONTRIBUTING.md`](./CONTRIBUTING.md) for the contributor workflow.

## License & attribution

The code and configuration in this repository (scripts, CI workflow, the
justfile, and documentation) are licensed under the MIT [LICENSE](./LICENSE),
copyright Ryan Hedgecock.

The wallpapers themselves are **not** covered by that license. They are the
original, copyrighted artwork of **[Abi Toads](https://abitoads.com)**, mirrored
here unofficially on the basis of her public statement that her wallpapers are
"free for anyone to use." See [ATTRIBUTION.md](./ATTRIBUTION.md) for full
attribution and terms. If you enjoy them, please support the artist at
[abitoads.com](https://abitoads.com).
