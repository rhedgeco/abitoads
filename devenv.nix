{ pkgs, ... }: {
  packages = with pkgs; [
    just # task runner (justfile)
    python3 # scripts/abitoads.py (fetch / publish / verify)
    ruff # python linter + formatter (LSP: formatting, lint fixes)
    basedpyright # python type checker + language server (hover, completion, go-to-def)
    curl # general networking / steamcmd fallback
    gh # abitoads.py publish uploads release assets
    git # version control
    steamcmd # downloads workshop items (abitoads.py fetch)
    steam-run # FHS wrapper steamcmd needs on NixOS
  ];
}
