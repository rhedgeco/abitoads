#!/usr/bin/env bash
#
# DESTRUCTIVE: rewrite git history to permanently remove the wallpaper videos.
#
# Why: the videos (26 .mp4 in wallpapers/, ~4.8 GB, stored via Git LFS) are no
# longer kept in the repo -- they're published as GitHub release assets and
# described by workshop.json. This script purges them from ALL history so the
# repo (and everyone's clones) stop carrying the large objects.
#
# What it does:
#   1. Makes a full backup clone next to the repo.
#   2. Uses git-filter-repo to drop wallpapers/ and the LFS .gitattributes from
#      every commit.
#   3. Leaves you to review, then force-push and prune LFS yourself.
#
# It does NOT push anything. Read the final instructions and run the push by
# hand once you're satisfied.
#
# Requires git-filter-repo. On NixOS:
#   nix-shell -p git-filter-repo --run scripts/purge-history.sh
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

if ! command -v git-filter-repo >/dev/null 2>&1; then
  echo "error: git-filter-repo not found." >&2
  echo "       on NixOS: nix-shell -p git-filter-repo --run $0" >&2
  exit 1
fi

# Refuse to run with a dirty tree -- commit or stash your current changes first
# (e.g. the workshop.json / docs / scripts changes) so they're in history.
if [ -n "$(git status --porcelain)" ]; then
  echo "error: working tree is not clean. Commit or stash changes first," >&2
  echo "       so this rewrite operates on a known state." >&2
  git --no-pager status --short >&2
  exit 1
fi

backup="${repo_root}.backup-$(date +%Y%m%d-%H%M%S)"
echo "1/3  Backing up to: $backup"
git clone --no-local --mirror "$repo_root" "$backup.git"
echo "     (bare mirror backup created; keep it until you've verified the push)"

echo "2/3  Rewriting history to remove wallpapers/ and .gitattributes ..."
# --invert-paths drops the listed paths from every commit in all refs.
git filter-repo --force \
  --path wallpapers \
  --path .gitattributes \
  --invert-paths

echo "3/3  Done rewriting. Local history no longer contains the videos."
echo
echo "git-filter-repo removed the 'origin' remote as a safety measure."
echo "Next steps (run these yourself once you've reviewed the result):"
echo
echo "  # 1. Re-add your remote:"
echo "  git remote add origin git@github-personal:rhedgeco/abitoads.git"
echo
echo "  # 2. Inspect: confirm wallpapers/ and the videos are gone from history:"
echo "  git --no-pager log --oneline --stat | grep -i wallpapers   # expect nothing"
echo "  git lfs ls-files                                           # expect nothing"
echo
echo "  # 3. Force-push the rewritten history (this rewrites the remote!):"
echo "  git push origin --force --all"
echo "  git push origin --force --tags"
echo
echo "  # 4. Remove the now-orphaned LFS objects locally to reclaim ~4.8 GB:"
echo "  rm -rf .git/lfs"
echo "  git reflog expire --expire=now --all && git gc --prune=now --aggressive"
echo
echo "  # 5. On GitHub, you may also want to delete any OLD releases/tags that"
echo "  #    referenced the in-repo videos, and (optionally) purge LFS storage"
echo "  #    from the repo's settings, since LFS is no longer used."
echo
echo "The backup mirror is at: $backup.git"
echo "If anything looks wrong, you can restore from it before pushing."
