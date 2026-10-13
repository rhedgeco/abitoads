# Abitoads Wallpaper Collection

A mirror of [Abi Toads](https://abitoads.com) animated wallpapers, sourced from
the [Steam Workshop](https://steamcommunity.com/app/431960/workshop/) (Wallpaper
Engine).

The video files are **not stored in this repository.** Instead, this repo holds
a small manifest, [`workshop.json`](./workshop.json), that maps a clean name to
each wallpaper's Steam Workshop id, original filename, and `sha256`. The actual
`.mp4` files are published as assets on a single long-lived GitHub release, so
the repo stays tiny and easy to pull into other projects (e.g. a Nix config).

## How it works

- Every wallpaper has a unique, **immutable** name (e.g. `AxolotlRide`). That
  name is the manifest key, the release asset name (`AxolotlRide.mp4`), and the
  on-disk filename.
- There is a **single release** (tag `wallpapers`). Assets are write-once: once
  `AxolotlRide.mp4` is published it is never overwritten or deleted.
- When a wallpaper is updated by the artist, it is added under a **new** name
  (e.g. `AxolotlRideV2`) as a separate asset. The old one stays frozen, so
  anything already pinned to it keeps working.
- Your "version" is simply the commit of `workshop.json` you pin -- its git
  history is the timeline of what changed and when.

## Downloading the wallpapers

Each wallpaper is an individual asset on the release, downloadable by name:

```
https://github.com/rhedgeco/abitoads/releases/download/wallpapers/AxolotlRide.mp4
```

The names and their integrity hashes are listed in
[`workshop.json`](./workshop.json).

### Using the wallpapers from Nix

Read the manifest and `fetchurl` each wallpaper by name, pinned by `sha256`:

```nix
let
  manifest = builtins.fromJSON (builtins.readFile ./workshop.json);
  baseUrl = "https://github.com/rhedgeco/abitoads/releases/download/wallpapers";
in
  builtins.mapAttrs
    (name: w: pkgs.fetchurl {
      url = "${baseUrl}/${name}.mp4";
      sha256 = w.sha256;
    })
    manifest.wallpapers
```

This gives you an attrset of `name -> derivation`, so you can pull just the
wallpapers you want. Because names and their hashes are immutable, these
fetches are reproducible and cache-stable. To update, pin a newer revision of
`workshop.json` (e.g. via `fetchurl` of its `raw.githubusercontent.com` URL at a
specific commit, or by bumping a flake input that provides this repo).

## Maintaining the collection

The video source of truth is the Steam Workshop, which requires an account that
owns Wallpaper Engine (a paid app) and an interactive, Steam Guard-confirmed
login. This means fetching and publishing is done **locally** by the maintainer;
it cannot run unattended in CI. CI only validates `workshop.json`.

Recipes (see the [`justfile`](./justfile)):

```sh
# Fetch one or more Workshop items by id and record them in workshop.json.
# Prompts for a name for each new/changed item (steamcmd prompts for login).
just fetch <steam-username> <workshop-id> [workshop-id ...]
```

Publishing the `.mp4` assets to the release is a separate manual step using the
GitHub CLI:

```sh
scripts/publish-release.sh rhedgeco/abitoads
```

It uploads only assets that are missing from the release (write-once); it never
clobbers or deletes existing ones. See the script headers in
[`scripts/`](./scripts) for details.

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
