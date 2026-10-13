#!/usr/bin/env bash
#
# Interactive, LOCAL-ONLY test for downloading Abi Toads wallpapers from the
# Steam Workshop with your own Steam account.
#
# IMPORTANT / SECURITY:
#   - This script never stores, prints, or transmits your password or Steam
#     Guard code. steamcmd prompts you for them interactively; you type them in.
#   - Do NOT use this in CI as-is, and do NOT hardcode credentials.
#   - Wallpaper Engine (app 431960) is a paid app, so anonymous download does
#     not work -- you must log in with an account that owns Wallpaper Engine.
#
# Usage:
#   scripts/steam-fetch.sh <steam-username> <workshop-id> [workshop-id ...]
#
# Example (Frog Picnic):
#   scripts/steam-fetch.sh myuser 3219522309
#
# Downloads land in: ./.steam-fetch/out/steamapps/workshop/content/431960/<id>/
set -euo pipefail

APP_ID=431960

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <steam-username> <workshop-id> [workshop-id ...]" >&2
  exit 1
fi

username="$1"
shift
ids=("$@")

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

# steam-run's bwrap sandbox does not expose /tmp on this setup, but it does
# expose paths under $HOME. Use a working dir inside the repo (which lives under
# $HOME) so steamcmd can actually see its own files.
work="$repo_root/.steam-fetch"
mkdir -p "$work"

# Fetch upstream steamcmd if we don't already have it.
if [ ! -f "$work/steamcmd.sh" ]; then
  echo "Downloading steamcmd..."
  curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" \
    -o "$work/steamcmd.tar.gz"
  tar -xzf "$work/steamcmd.tar.gz" -C "$work"
fi

# Build the steamcmd command line: login, then one download per id, then quit.
cmd=(+force_install_dir "$work/out" +login "$username")
for id in "${ids[@]}"; do
  cmd+=(+workshop_download_item "$APP_ID" "$id")
done
cmd+=(+quit)

echo "Logging in as '$username' (you will be prompted for your password and"
echo "Steam Guard code). Downloading ${#ids[@]} item(s)..."
echo

# steam-run provides the FHS environment the Steam binary needs on NixOS.
# If steam-run is already on PATH (e.g. inside the devenv shell), use it
# directly; otherwise fall back to fetching it via nix-shell. steam-run is
# unfree, hence NIXPKGS_ALLOW_UNFREE for the fallback.
if command -v steam-run >/dev/null 2>&1; then
  steam-run "$work/steamcmd.sh" "${cmd[@]}"
else
  NIXPKGS_ALLOW_UNFREE=1 nix-shell --impure -p steam-run \
    --run "steam-run $work/steamcmd.sh ${cmd[*]}"
fi

echo
echo "Done. Downloaded content is under:"
echo "  $work/out/steamapps/workshop/content/$APP_ID/"
for id in "${ids[@]}"; do
  dir="$work/out/steamapps/workshop/content/$APP_ID/$id"
  if [ -d "$dir" ]; then
    echo "  [$id]:"
    find "$dir" -type f -printf '    %s bytes  %p\n'
  else
    echo "  [$id]: (no files found -- download may have failed)"
  fi
done
