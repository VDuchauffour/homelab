#!/usr/bin/env bash
# Move videos from qBittorrent download to library
# Usage: ./move-to-library.sh [download_root] [library_root]
set -euo pipefail

DOWNLOAD_ROOT="${1:-/mnt/tank/media/downloads}"
LIBRARY_ROOT="${2:-/mnt/tank/media/videos}"

# Direct mappings: source → destination
declare -a MAPS=(
	"documentaries:documentaries"
	"movies:movies"
	"shows:shows"
	"stand-up:stand-up"
	"tv-programs:tv-programs"
	"tv-shows:tv-shows"
)

for mapping in "${MAPS[@]}"; do
	src_subdir="${mapping%%:*}"
	dest_subdir="${mapping##*:}"

	src="$DOWNLOAD_ROOT/$src_subdir"
	dest="$LIBRARY_ROOT/$dest_subdir"

	# Skip if source doesn't exist or is empty
	if [[ ! -d "$src" ]] || [[ -z "$(ls -A "$src" 2>/dev/null)" ]]; then
		echo "Skipping: $src (not found or empty)"
		continue
	fi

	mkdir -p "$dest"

	echo "────────────────────────────────────────"
	echo "Moving: $src → $dest"
	echo "────────────────────────────────────────"

	ls -1 "$src/"

	shopt -s dotglob nullglob
	mv "$src"/* "$dest/"
	shopt -u dotglob nullglob

	echo
done

echo "All transfers complete."
