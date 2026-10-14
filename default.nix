# Abi Toads wallpapers, packaged from the GitHub release snapshots.
{
  pkgs ? import <nixpkgs> { },
  # The repo that hosts the releases.
  owner ? "rhedgeco",
  repo ? "abitoads",
  # Release tag to pull assets from ("latest" or a pinned snapshot like "v3").
  tag ? "latest",
  # The pinned manifest. Defaults to the one in this directory.
  manifest ? builtins.fromJSON (builtins.readFile ./workshop.json),
}:
let
  inherit (pkgs) lib;

  # build the asset url based on the specified tag
  assetUrlBase =
    if tag == "latest" then
      "https://github.com/${owner}/${repo}/releases/latest/download"
    else
      "https://github.com/${owner}/${repo}/releases/download/${tag}";
  assetUrl = name: "${assetUrlBase}/${name}.mp4";

  # Fetch a remote wallpaper using a manifest entry. pkgs.fetchurl is a proper
  # build step, so it is substitutable from binary caches, runs on remote
  # builders, and does not download anything at eval time.
  fetchWallpaper =
    name: entry:
    pkgs.fetchurl {
      name = "${name}.mp4";
      url = assetUrl name;
      sha256 = entry.sha256;
    };

  # map of wallpaper name -> <Name>.mp4 derivation
  wallpapers = lib.mapAttrs fetchWallpaper manifest.wallpapers;

  # collect every wallpaper into a directory
  all = pkgs.runCommand "abitoads-wallpapers" { } ''
    mkdir -p "$out"
    ${lib.concatStringsSep "\n" (
      lib.mapAttrsToList (name: drv: ''
        cp ${lib.escapeShellArg drv} "$out/${name}.mp4"
      '') wallpapers
    )}
  '';
in
{
  inherit wallpapers all;
}
