{ pkgs, ... }: {
  packages = with pkgs; [
    just # task runner (justfile)
    ruff # python linter + formatter (LSP: formatting, lint fixes)
    basedpyright # python type checker + language server (hover, completion, go-to-def)
    curl # general networking / steamcmd fallback
    gh # abitoads.py publish uploads release assets
    git # version control
    steamcmd # downloads workshop items (abitoads.py register / fetch)
    steam-run # FHS wrapper steamcmd needs on NixOS
  ];

  # Python for scripts/abitoads.py. A venv provides the secretspec SDK
  languages.python = {
    enable = true;
    venv = {
      enable = true;
      requirements = ''
        secretspec
      '';
    };
  };
}
