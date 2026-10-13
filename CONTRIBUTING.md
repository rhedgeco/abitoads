# Contributing

This repository does **not** store the wallpaper videos. It stores a manifest,
[`workshop.json`](./workshop.json), describing each wallpaper (clean name, Steam
Workshop id, original filename, and `sha256`). The actual `.mp4` files are
published as assets on a single long-lived GitHub release.

Because the videos come from the Steam Workshop (Wallpaper Engine, a paid app
behind an interactive Steam Guard login), adding or updating wallpapers is done
locally by a maintainer who owns the app -- it cannot run in CI. If you'd like a
wallpaper added, the easiest contribution is to **open an issue with the Steam
Workshop item id**.

## Maintainer workflow

### Prerequisites

- `just`, `jq`, `curl`, `sha256sum`
- A Steam account that owns Wallpaper Engine (for fetching)
- The GitHub CLI `gh`, authenticated (for publishing)
- On NixOS, `steamcmd` runs via `steam-run` (the fetch script handles this);
  `gh` can be provided with `nix-shell -p gh`.

### 1. Fetch and record

```sh
just fetch <steam-username> <workshop-id> [workshop-id ...]
```

This downloads each item from the Workshop (steamcmd prompts for your password
and Steam Guard confirmation -- credentials are never stored or logged), then
records it in `workshop.json`. For each new or changed item you're prompted for
a clean, filename-safe **name**, with a suggestion derived from the title:

- A brand-new wallpaper gets a fresh name (e.g. `AxolotlRide`).
- If a wallpaper's content changed, the existing entry is left **frozen** and a
  new name is suggested (e.g. `AxolotlRideV2`). Names are immutable -- an
  existing name is never repointed.
- Re-fetching unchanged content is a no-op.

Commit the updated `workshop.json`.

### 2. Publish the assets

```sh
scripts/publish-release.sh rhedgeco/abitoads
```

This uploads any wallpapers from `workshop.json` that are **missing** from the
release, named `<Name>.mp4`. It never overwrites or deletes existing assets, so
published names stay permanently valid.

## CI

The only automated check is **validate-manifest**, which runs on pull requests
and pushes that touch `workshop.json`. It verifies the manifest is well-formed:
valid JSON, every entry has an id/file/valid `sha256`, and every name is
filename-safe. CI does not touch Steam or the release assets.
