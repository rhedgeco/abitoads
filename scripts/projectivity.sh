#!/usr/bin/env bash

DEST="/storage/emulated/0/Android/data/com.spocky.projengmenu/files/wallpapers/"

if [ $# -eq 0 ]; then
  echo "Usage: $0 <path> [path...]"
  echo "  <path> can be an .mp4 file or a directory containing .mp4 files."
  exit 1
fi

push_file() {
  local file="$1"
  local name
  name="$(basename "$file")"
  if ! adb shell "[ -f '${DEST}${name}' ]"; then
    echo "Pushing $name..."
    adb push "$file" "$DEST"
  else
    echo "$name already exists on TV, skipping."
  fi
}

for path in "$@"; do
  if [ -d "$path" ]; then
    while IFS= read -r -d '' file; do
      push_file "$file"
    done < <(find "$path" -type f -name '*.mp4' -print0)
  elif [ -f "$path" ]; then
    push_file "$path"
  else
    echo "Warning: '$path' is not a valid file or directory, skipping."
  fi
done
