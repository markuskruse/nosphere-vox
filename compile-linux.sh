#!/usr/bin/env bash
set -euo pipefail

# Build Linux binaries for all Python scripts using PyInstaller.
# Run from the repo root on a Linux host with python3 and PyInstaller installed.

DIST_DIR="dist/linux"
BUILD_DIR="build/linux"
TARGETS=($(ls *.py))

rm -rf "$DIST_DIR" "$BUILD_DIR"
mkdir -p "$DIST_DIR"

for target in "${TARGETS[@]}"; do
  name="${target%.py}"
  target_build="$BUILD_DIR/$name"
  mkdir -p "$target_build"
  extra=()
  if [[ "$target" == "vox.py" ]]; then
    extra=(--icon "assets/nosphere-vox.png")
  fi
  python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name "$name" \
    --distpath "$DIST_DIR" \
    --workpath "$target_build" \
    --specpath "$target_build" \
    --clean \
    --add-data "assets/nosphere-vox.png:assets" \
    "${extra[@]}" \
    "$target"
done
