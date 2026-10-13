# Contributing

This repository does **not** store the wallpaper videos. It stores a manifest,
[`workshop.json`](./workshop.json), mapping each wallpaper's clean **name** to
its Steam Workshop `id` and the video's `sha256`. The actual `.mp4` files are
published as assets on a single long-lived GitHub release.

All tooling lives in a single stdlib-only CLI, `scripts/abitoads.py`, with
`fetch`, `publish`, and `verify` subcommands.

## Contributing a wallpaper (pull request)

The best way to add a wallpaper is to **open a pull request that adds an entry
to `workshop.json`**, mapping a clean, filename-safe name to the Steam Workshop
`id` and the video's `sha256`:

```json
"CozyCampfire": { "id": "3119714017", "sha256": "<64-hex-char sha256>" }
```

Guidelines for the entry:

- **Name** is the identity and is **immutable** -- it becomes the release asset
  (`<Name>.mp4`) and must stay filename-safe (`^[A-Za-z][A-Za-z0-9_-]*$`). If a
  wallpaper's content changed, add it under a **new** name (e.g. `CozyCampfireV2`)
  rather than editing an existing entry; old entries stay frozen forever.
- **`sha256`** must be the hash of the exact `.mp4` as distributed on the
  Workshop. If you own Wallpaper Engine you can produce it with the maintainer
  flow below (`just fetch ...` records `id` and `sha256` for you). If you don't,
  open the PR with the `id` and your best name, and note that the hash still
  needs filling in -- the maintainer can complete it.

CI validates the manifest shape on every PR. Once merged, publishing (below)
runs on the maintainer's self-hosted runner, which downloads each item from
Steam, verifies it against the committed `sha256`, and uploads it to the release.
A mismatched hash fails the run, so a wrong `sha256` can never reach the release.

If you'd rather not edit JSON, opening an issue with the Workshop `id` is also
fine.

## Maintainer workflow

### Prerequisites

- `just`, `python3`
- A Steam account that owns Wallpaper Engine (for fetching)
- The GitHub CLI `gh`, authenticated (for publishing)
- On NixOS, `steamcmd` runs via `steam-run` (handled automatically; a `devenv`
  shell provides everything). `gh` can also be provided with `nix-shell -p gh`.

### 1. Fetch and record (local)

```sh
just fetch <steam-username> <workshop-id> [workshop-id ...]
```

This downloads each item from the Workshop (steamcmd prompts for your password
and Steam Guard confirmation -- credentials are never stored or logged),
computes the `.mp4`'s `sha256`, then records it in `workshop.json`. For each new
or changed item you're prompted for a clean, filename-safe **name**, with a
suggestion derived from the title:

- A brand-new wallpaper gets a fresh name (e.g. `AxolotlRide`).
- If a wallpaper's content changed, the existing entry is left **frozen** and a
  new name is suggested (e.g. `AxolotlRideV2`). Names are immutable -- an
  existing name is never repointed.
- Re-fetching unchanged content is a no-op.

Commit the updated `workshop.json`.

### 2. Verify (optional)

```sh
just verify
```

Re-hashes the locally-downloaded videos and checks them against the manifest.

### 3. Publish the assets

```sh
just publish
# or, to re-download the manifest's items from Steam first:
just publish --download
# --download also accepts an explicit Steam username (defaults to $STEAM_USER):
just publish --download rhedgeco
```

This uploads any wallpapers from `workshop.json` that are **missing** from the
release, named `<Name>.mp4`. It never overwrites or deletes existing assets, so
published names stay permanently valid.

- With `--download`, it first pulls every manifest item from Steam (this is what
  the self-hosted runner uses, so it doesn't rely on files already on disk). The
  Steam username is read from `$STEAM_USER`.
- Without `--download`, it uploads from the items already downloaded locally
  (e.g. right after `just fetch`).

Before uploading each asset, publish re-hashes the local `.mp4` and compares it
to the committed `sha256`; **a mismatch aborts the run before anything is
uploaded**, so a wrong hash can never reach the release. Existing assets (already
present in the release) are skipped and never re-checked or clobbered.

## CI

Two layers of CI, split by what each can safely do:

- **validate-manifest** (GitHub-hosted runners, on PRs): verifies the manifest
  is well-formed -- valid JSON, every entry has an `id` and a valid `sha256`, and
  every name is filename-safe. It does not touch Steam or the release.
- **publish** (the maintainer's **self-hosted runner**): on merges to `main`, it
  downloads each manifest item from Steam, checks it against the committed
  `sha256`, and uploads any missing `<Name>.mp4` assets to the release. The Steam
  session and credentials live locally on that server -- never in the repo or in
  GitHub secrets.
