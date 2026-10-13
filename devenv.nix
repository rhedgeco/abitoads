{ pkgs, ... }: {
  packages = with pkgs; [
    just # task runner (justfile)
    jq # manifest (workshop.json) manipulation
    coreutils # sha256sum, stat, etc.
    curl # steam-fetch.sh downloads steamcmd
    gnused # name derivation in fetch-wallpaper.sh
    gawk # name derivation in fetch-wallpaper.sh
    gh # publish-release.sh uploads release assets
    git # version control
    git-lfs # legacy; harmless to have around
    git-filter-repo # purge-history.sh
    steam-run # runs the unfree steamcmd on NixOS (steam-fetch.sh)
  ];
}
