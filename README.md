# Abitoads Wallpaper Collection

A mirror of [Abi Toads](https://abitoads.com) animated wallpapers, sourced from
[Steam Workshop](https://steamcommunity.com/app/431960/workshop/) (Wallpaper Engine).

The video files are **not stored in this repository.**
Instead, the `main` branch holds a small manifest, [`workshop.json`](./workshop.json),
that maps a clean name to each wallpaper's Steam Workshop id and `sha256`.
The actual `.mp4` files are published as assets on GitHub releases.

## Downloading the wallpapers

Each wallpaper is an individual asset on a release, downloadable by name:

```
https://github.com/rhedgeco/abitoads/releases/latest/download/AxolotlRide.mp4
```

To pin a specific release, use a tag instead,
e.g. `releases/download/release3/AxolotlRide.mp4`.
The names and their integrity hashes are listed in [`workshop.json`](./workshop.json).

### Using the wallpapers from Nix

The `release` branch is a flake, that imports a manifest.
The manifest is updated for every new release and maps the file to its hash.

```nix
{
  inputs.abitoads.url = "github:rhedgeco/abitoads/release";

  outputs = { self, nixpkgs, abitoads }:
    let system = "x86_64-linux"; in {
      # one wallpaper (a <Name>.mp4 derivation)
      #   abitoads.packages.${system}.wallpapers.LazyRiver
      # a directory of every <Name>.mp4
      #   abitoads.packages.${system}.all
    };
}
```

From the CLI the same outputs build directly, with your current system filled in
automatically:

```
nix build github:rhedgeco/abitoads/release#wallpapers.LazyRiver   # individual file
nix build github:rhedgeco/abitoads/release#all                    # directory of every <Name>.mp4
```

`all` is also the default package (`nix build github:rhedgeco/abitoads/release`).

If you already have a `pkgs` in scope and would rather not index by system,
use the overridable `fetch` helper. It is just `import ./.` on the `release` branch,
so it also lets you supply your own `pkgs`, `owner`, `repo`, or `manifest`:

```nix
abitoads.fetch { inherit pkgs; }
# => { wallpapers = { LazyRiver = <drv>; ... }; all = <drv>; }
```

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
