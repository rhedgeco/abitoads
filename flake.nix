{
  description = "Abi Toads animated wallpapers.";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      inherit (nixpkgs) lib;
      fetch = import ./.;
      systemPkgs = system: nixpkgs.legacyPackages.${system};
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;
      abitoads = system: fetch { pkgs = systemPkgs system; };
    in
    {
      # re-export the fetch function
      # so downstream flakes can override args if needed
      inherit fetch;

      # export the videos for all systems
      packages = forAllSystems (system: {
        wallpapers = (abitoads system).wallpapers;
        default = (abitoads system).all;
        all = (abitoads system).all;
      });
    };
}
