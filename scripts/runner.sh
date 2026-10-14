#!/usr/bin/env bash
# Thin NixOS entry point for the self-hosted runner: run the Python tooling
# inside the devenv shell so steamcmd, steam-run, python3 and the secretspec
# venv are all set up, then hand off. The Python `runner` subcommand does all
# the real work (install, register, prime Steam login, run).
#
# The only thing this needs on PATH is devenv. Run it from the repo root (the
# justfile ensures that). See `abitoads.py runner` for the behavior and flags.
#
# We go through `devenv shell -- ...` (rather than just sourcing the exported
# environment) because the Python virtualenv that provides the secretspec SDK
# is activated by devenv's shell tasks, which a plain env export does not run.

set -euo pipefail

command -v devenv >/dev/null || {
    printf 'error: devenv is required but not found on PATH.\n' >&2
    exit 1
}

exec devenv shell -- python3 scripts/abitoads.py runner "$@"
