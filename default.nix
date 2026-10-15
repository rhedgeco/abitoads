# Abi Toads wallpapers, built from the pinned release manifest.
{
  pkgs ? import <nixpkgs> { },
  owner ? "rhedgeco",
  repo ? "abitoads",
  manifest ? builtins.fromJSON (builtins.readFile ./manifest.json),
}:
let
  inherit (pkgs) lib;

  # Every release contains the full set of wallpapers
  releaseTag = "release${manifest.release}";
  repoUrl = "https://github.com/${owner}/${repo}";
  assetUrl = name: "${repoUrl}/releases/download/${releaseTag}/${name}.mp4";

  # fetches a remote wallpaper by name, pinned by its hash
  fetchWallpaper =
    name: sha256:
    pkgs.fetchurl {
      name = "${name}.mp4";
      url = assetUrl name;
      inherit sha256;
    };
in
rec {
  # attribute set of all named wallpapers in the manifest
  wallpapers = lib.mapAttrs fetchWallpaper manifest.wallpapers;

  # for convenience, a package with every wallpaper in it is also created
  all = pkgs.runCommand "abitoads-wallpapers" { } ''
    mkdir -p "$out"
    ${lib.concatStringsSep "\n" (
      lib.mapAttrsToList (name: drv: ''
        cp ${lib.escapeShellArg drv} "$out/${name}.mp4"
      '') wallpapers
    )}
  '';
}
