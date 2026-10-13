#!/usr/bin/env bash
#
# Fetch one (or more) Steam Workshop item(s) and add them to workshop.json.
#
# For each id this:
#   1. downloads it from the Workshop via scripts/steam-fetch.sh (interactive
#      login -- you own Wallpaper Engine; steamcmd prompts for password/2FA),
#   2. computes the .mp4's sha256,
#   3. records it under a unique, immutable pretty name in workshop.json.
#
# Names are the identity and are WRITE-ONCE:
#   - If this id + this exact content (sha256) is already recorded under some
#     name, nothing changes (no-op).
#   - If the id is new, you're prompted for a name.
#   - If the id is known but its CONTENT changed (Abi updated the wallpaper),
#     the existing entry is left untouched (frozen) and you're prompted for a
#     NEW name, suggested as "<LatestName>V2". Both coexist, and both become
#     separate, permanently-addressable release assets.
#
# workshop.json is keyed by name; the name doubles as the release asset and
# on-disk filename ("<Name>.mp4"). No URL is stored -- consumers build it. The
# same id may appear under multiple names (different versions); id is just
# provenance, the name is the key.
#
# Usage:
#   scripts/fetch-wallpaper.sh <steam-username> <workshop-id> [workshop-id ...]
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
out="$repo_root/workshop.json"
content_dir="$repo_root/.steam-fetch/out/steamapps/workshop/content/$APP_ID"

for cmd in jq sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: $cmd is required." >&2; exit 1; }
done

# A valid name: filename-safe, must start with a letter.
valid_name() {
  echo "$1" | grep -qE '^[A-Za-z][A-Za-z0-9_-]*$'
}

# Build an editable default name from a title (strip the Abi Toads suffix,
# drop non-alphanumerics, join words capitalized). You can accept or replace it.
suggest_name() {
  echo "$1" \
    | sed -E 's/ by Abi Toads//I; s/ Abi Toads//I' \
    | sed -E 's/[^a-zA-Z0-9]+/ /g' \
    | awk '{
        out="";
        for (i=1;i<=NF;i++) out = out toupper(substr($i,1,1)) tolower(substr($i,2));
        print out;
      }'
}

# Given a desired base name, return the first non-colliding variant: the base
# itself if free, else base + V2, V3, ... until one isn't already a key in
# workshop.json.
free_name() {
  local base="$1" candidate n
  candidate="$base"
  n=1
  while jq -e --arg c "$candidate" '.wallpapers | has($c)' "$out" >/dev/null; do
    n=$((n + 1))
    candidate="${base}V${n}"
  done
  echo "$candidate"
}

# Prompt for a unique, valid name (rejecting ones already in workshop.json).
# Arg 1 is an editable default shown in brackets. Echoes the chosen name.
prompt_name() {
  local suggestion="$1" name
  while :; do
    if [ -n "$suggestion" ]; then
      printf '    Name [%s]: ' "$suggestion" >&2
    else
      printf '    Name: ' >&2
    fi
    read -r name </dev/tty || { echo >&2; echo "error: no TTY to prompt for name." >&2; exit 1; }
    [ -z "$name" ] && name="$suggestion"
    if [ -z "$name" ]; then
      echo "    A name is required." >&2; continue
    fi
    if ! valid_name "$name"; then
      echo "    Invalid: letters, digits, - or _, starting with a letter." >&2; continue
    fi
    if jq -e --arg n "$name" '.wallpapers | has($n)' "$out" >/dev/null; then
      echo "    '$name' is already used; pick another." >&2; continue
    fi
    break
  done
  echo "$name"
}

# Download the requested items (one interactive login for all of them).
"$repo_root/scripts/steam-fetch.sh" "$username" "${ids[@]}"

# Ensure workshop.json exists with the expected shape.
if [ ! -f "$out" ]; then
  jq -n --arg appId "$APP_ID" '{appId: $appId, wallpapers: {}}' >"$out"
fi

for id in "${ids[@]}"; do
  item_dir="$content_dir/$id"
  project="$item_dir/project.json"

  if [ ! -f "$project" ]; then
    echo "  [$id] WARNING: no project.json (download failed?), skipping" >&2
    continue
  fi

  title="$(jq -r '.title // empty' "$project")"
  file="$(jq -r '.file // empty' "$project")"
  mp4="$item_dir/$file"

  if [ -z "$file" ] || [ ! -f "$mp4" ]; then
    echo "  [$id] WARNING: video file missing, skipping" >&2
    continue
  fi

  sha256="$(sha256sum "$mp4" | cut -d' ' -f1)"

  # Already recorded with this exact content? Then there's nothing to do.
  existing_name="$(jq -r --arg id "$id" --arg sha "$sha256" \
    'first((.wallpapers | to_entries[] | select(.value.id == $id and .value.sha256 == $sha) | .key)) // empty' "$out")"
  if [ -n "$existing_name" ]; then
    echo "  [$id] already recorded as '$existing_name' (unchanged), skipping"
    continue
  fi

  # Any existing names for this id (same wallpaper, different/older content)?
  prior_names="$(jq -r --arg id "$id" '.wallpapers | to_entries[] | select(.value.id == $id) | .key' "$out")"

  echo
  if [ -z "$prior_names" ]; then
    echo "  New wallpaper: [$id] \"$title\" ($file)"
  else
    echo "  Updated wallpaper: [$id] \"$title\" ($file)"
    echo "    content changed; existing name(s) are kept frozen:"
    echo "$prior_names" | sed 's/^/      - /'
    echo "    choose a NEW name for this version."
  fi

  # Generate the name from the title, then bump V2/V3/... only if it collides.
  suggestion="$(free_name "$(suggest_name "$title")")"

  name="$(prompt_name "$suggestion")"

  tmp="$(mktemp)"
  jq --arg n "$name" --arg id "$id" --arg file "$file" --arg sha256 "$sha256" \
    '.wallpapers[$n] = {id: $id, file: $file, sha256: $sha256}
     | .wallpapers |= (to_entries | sort_by(.key) | from_entries)' \
    "$out" >"$tmp" && mv "$tmp" "$out"

  echo "  [$id] added as '$name' -> $name.mp4"
done

echo
echo "Updated $out"
