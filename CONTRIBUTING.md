# Contributing

This repository does **not** store the wallpaper videos. It stores a manifest,
[`workshop.json`](./workshop.json), mapping each wallpaper's clean **name** to
its Steam Workshop `id` and the video's `sha256`. The actual `.mp4` files are
published as assets on GitHub releases (each publish cuts a new snapshot that
becomes `releases/latest`).

All tooling lives in a single stdlib-only CLI, `scripts/abitoads.py`, exposed
through the justfile.

## Contributing a wallpaper (pull request)

The best way to add a wallpaper is to **open a pull request that adds an entry
to `workshop.json`**, mapping a clean, filename-safe name to the Steam Workshop
`id` and the video's `sha256`:

```json
{
  "wallpapers": {
    "CozyCampfire": { "id": "3119714017", "sha256": "<64-hex-char sha256>" }
  }
}
```

Guidelines for the entry:

- **Name** is the manifest key and the release asset name (`<Name>.mp4`); it must
  be filename-safe (`^[A-Za-z][A-Za-z0-9_-]*$`). Pick a stable, descriptive name.
- When a wallpaper's content changes, **keep the same name** and just update its
  `sha256` -- do not add a new `V2`-style entry. The identity is the Workshop
  `id`, and the next release carries the new bytes under the same asset name.
- **`sha256`** must be the hash of the exact `.mp4` as distributed on the
  Workshop. If you own Wallpaper Engine you can produce it with `just register`
  (see below), which records `id` and `sha256` for you. If you don't, open the
  PR with the `id` and your best name and note that the hash still needs filling
  in -- the maintainer can complete it.

CI validates the manifest shape on every PR (valid JSON, each entry has an `id`
and a valid `sha256`, each name is filename-safe). After merge, pushing the
`workshop.json` change to `main` automatically triggers publishing on the
maintainer's self-hosted runner, which re-downloads each item from Steam and
re-hashes it against the committed `sha256`, aborting on any mismatch -- so a
wrong hash can never reach the release.

If you'd rather not edit JSON, opening an issue with the Workshop `id` is also
fine.

## Producing a `sha256` with `just register`

If you own Wallpaper Engine, `just register` downloads items from the Workshop
and records them in `workshop.json` for you, so you don't have to compute hashes
by hand.

Prerequisites: `just` and `python3`, plus `steamcmd` (on NixOS it runs via
`steam-run`) and the secretspec SDK. A `devenv` shell provides all of these.
Your Steam username is resolved through [secretspec](./secretspec.toml) (the
`STEAM_USER` secret), not passed on the command line.

```sh
just register <workshop-id> [workshop-id ...]
```

This downloads each item (steamcmd handles your password and Steam Guard
confirmation -- credentials are never stored or logged), computes the `.mp4`'s
`sha256`, then records it in `workshop.json`:

- A brand-new wallpaper prompts once for a clean, filename-safe **name**, with a
  suggestion derived from the title (e.g. `AxolotlRide`).
- An updated wallpaper (same Workshop `id`, new content) keeps its existing name
  and just has its `sha256` refreshed in place -- no prompt.
- Re-registering unchanged content is a no-op.

Commit the updated `workshop.json` and open your PR. You can re-hash the
collected videos in `.wallpapers/` against the manifest with `just verify`, and
pull every manifest item from Steam (verifying each against its `sha256` and
collecting it into `.wallpapers/`) with `just fetch`. If a wallpaper's content
has changed upstream, `just fetch --update` refreshes the manifest `sha256` to
match the freshly-downloaded video instead of failing on the mismatch.
