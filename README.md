# Abitoads Wallpaper Collection

A collection of abitoads wallpapers extracted from the steam workshop.

## Downloading the wallpapers

The wallpapers are published as assets on each [GitHub
release](https://github.com/rhedgeco/abitoads/releases). Every `.mp4` is an
individual asset, alongside a `SHA256SUMS` file, so you can fetch just the ones
you want:

```
https://github.com/rhedgeco/abitoads/releases/download/<tag>/Picnic.mp4
```

To grab the whole collection in one download, each release also includes bundle
archives:

```
https://github.com/rhedgeco/abitoads/releases/download/<tag>/abitoads-wallpapers.zip
https://github.com/rhedgeco/abitoads/releases/download/<tag>/abitoads-wallpapers.tar.gz
```

(The videos are already compressed, so the archives are mostly a convenient
single-file download rather than a space saving.)

To always grab the newest release without looking up a tag, use the `latest`
URLs (GitHub redirects them to the current release):

```
https://github.com/rhedgeco/abitoads/releases/latest/download/abitoads-wallpapers.tar.gz
https://github.com/rhedgeco/abitoads/releases/latest/download/Picnic.mp4
```

### Using the wallpapers from Nix

Add the wallpaper collection to your flake as a (non-flake) tarball input. The
`latest` URL means the input always tracks the newest release, and the pinned
bytes live in your `flake.lock` for reproducibility:

```nix
{
  inputs.abitoads = {
    type = "tarball";
    url = "https://github.com/rhedgeco/abitoads/releases/latest/download/abitoads-wallpapers.tar.gz";
    flake = false;
  };

  outputs = { self, nixpkgs, abitoads, ... }: {
    # `abitoads` is the unpacked tarball; wallpapers live under `wallpapers/`.
    # For example, referencing a single wallpaper:
    #   "${abitoads}/wallpapers/Picnic.mp4"
  };
}
```

The exact release is pinned in `flake.lock`, so builds are reproducible. To bump
to the latest wallpapers, update the input deliberately:

```
nix flake update abitoads
```

If instead you want to pin one specific release (rather than tracking latest),
use the versioned URL and the sha256 from that release's `SHA256SUMS`:

```nix
pkgs.fetchurl {
  url = "https://github.com/rhedgeco/abitoads/releases/download/v1/Picnic.mp4";
  hash = "sha256-...";
}
```

Never combine a `latest` URL with a hardcoded `hash` -- the content behind
`latest` changes with each release, which would break the hash.

## Releases

Releases are fully automated. Whenever a change to the `wallpapers/` directory
lands on `main`, the `release` workflow cuts a new release (`v1`, `v2`, ...) and
uploads every wallpaper plus a `SHA256SUMS` file as assets. Pushes that don't
touch `wallpapers/` do not create a release.

Adding a wallpaper is therefore just:

```
git add wallpapers/NewWallpaper.mp4
git commit -m "add NewWallpaper"
git push
```
