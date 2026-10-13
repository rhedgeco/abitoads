#!/usr/bin/env bash
#
# Publish the Abi Toads wallpapers to the single, long-lived GitHub Release.
#
# Model: there is ONE release (default tag "wallpapers"). Each wallpaper is an
# asset named "<Name>.mp4", where <Name> is a key from workshop.json. Names are
# immutable and WRITE-ONCE:
#   - An asset that already exists in the release is never re-uploaded or
#     clobbered (it's frozen, so consumers pinned to it never break).
#   - Only names missing from the release are uploaded.
# When a wallpaper changes, 'just fetch' records it under a NEW name (e.g.
# <Name>V2), which this script then uploads as a new, separate asset.
#
# Consumers download  https://github.com/<repo>/releases/download/<tag>/<Name>.mp4
# and verify it against workshop.json's sha256. Each asset is a single .mp4
# (largest ~934 MB), well under GitHub's 2 GiB per-asset limit.
#
# Requires the GitHub CLI (gh), authenticated (gh auth login).
#
# Usage:
#   scripts/publish-release.sh <github-owner/repo> [release-tag] [content-dir]
#
# Example:
#   scripts/publish-release.sh rhedgeco/abitoads
set -euo pipefail

APP_ID=431960

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <github-owner/repo> [release-tag] [content-dir]" >&2
  exit 1
fi

repo="$1"
tag="${2:-wallpapers}"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
content_dir="${3:-$repo_root/.steam-fetch/out/steamapps/workshop/content/$APP_ID}"
manifest="$repo_root/workshop.json"

for cmd in gh jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: $cmd is required but not found on PATH." >&2
    [ "$cmd" = gh ] && echo "       on NixOS you can run this inside: nix-shell -p gh" >&2
    exit 1
  fi
done

if [ ! -f "$manifest" ]; then
  echo "error: $manifest not found; run 'just fetch ...' first." >&2
  exit 1
fi

if [ ! -d "$content_dir" ]; then
  echo "error: content dir not found: $content_dir" >&2
  echo "       run scripts/fetch-wallpaper.sh first to download items." >&2
  exit 1
fi

# Ensure the single release exists.
echo "Ensuring release '$tag' exists on $repo ..."
if ! gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
  gh release create "$tag" --repo "$repo" \
    --title "Abi Toads wallpapers" \
    --notes "Abi Toads wallpapers, sourced from the Steam Workshop. Assets are named <Name>.mp4 and are immutable; see workshop.json for the sha256-pinned manifest." \
    --draft=false
fi

# Assets already present in the release (write-once: we never touch these).
existing_assets="$(gh release view "$tag" --repo "$repo" --json assets \
  --jq '.assets[].name' 2>/dev/null || true)"

asset_exists() {
  printf '%s\n' "$existing_assets" | grep -Fxq "$1.mp4"
}

# Stage only the wallpapers whose asset is missing, as "<Name>.mp4" symlinks.
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT

to_upload=()
skipped=0
while IFS="$(printf '\t')" read -r name id file; do
  if asset_exists "$name"; then
    skipped=$((skipped + 1))
    continue
  fi
  mp4="$content_dir/$id/$file"
  if [ ! -f "$mp4" ]; then
    echo "  [$name] ERROR: expected file not found: $mp4" >&2
    echo "         (re-run 'just fetch <user> $id' to download it)" >&2
    exit 1
  fi
  ln -s "$mp4" "$staging/$name.mp4"
  to_upload+=("$staging/$name.mp4")
  echo "  will upload $name.mp4"
done < <(jq -r '.wallpapers | to_entries[] | [.key, .value.id, .value.file] | @tsv' "$manifest")

echo
echo "Skipping $skipped asset(s) already present (immutable)."

if [ "${#to_upload[@]}" -eq 0 ]; then
  echo "Nothing new to upload. Release is up to date."
  exit 0
fi

echo "Uploading ${#to_upload[@]} new asset(s)..."
# No --clobber: these names are guaranteed absent, and we never overwrite.
gh release upload "$tag" "${to_upload[@]}" --repo "$repo"

echo
echo "Done. ${#to_upload[@]} new asset(s) uploaded to $repo release $tag."
