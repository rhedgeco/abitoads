{
  description = "Abi Toads animated wallpapers, fetched from the GitHub release snapshots";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      inherit (nixpkgs) lib;
      eachSystem = lib.genAttrs lib.systems.flakeExposed;
      forSystem = system: import ./. { pkgs = nixpkgs.legacyPackages.${system}; };
    in
    {
      # Per-system packages. `all` is the default.
      # each wallpaper is also its own package.
      packages = eachSystem (
        system:
        let
          abitoads = forSystem system;
        in
        abitoads.wallpapers
        // {
          default = abitoads.all;
          all = abitoads.all;
        }
      );

      # Overridable helper so downstream flakes can pin a specific release tag,
      # supply their own manifest, or use a different pkgs instance:
      #
      # abitoads.fetchWallpapers { pkgs = ...; tag = "v3"; }
      fetchWallpapers = import ./.;
    };
}
