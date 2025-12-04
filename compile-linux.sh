#!/usr/bin/env bash
set -euo pipefail

# Build Linux binaries for listener and transmitter using PyInstaller.
# Run from the repo root on a Linux host with python3 and PyInstaller installed.

DIST_DIR="dist/linux"
BUILD_DIR="build/linux"
TARGETS=(vox-listener.py vox-transmit.py)

rm -rf "$DIST_DIR" "$BUILD_DIR"
mkdir -p "$DIST_DIR"

for target in "${TARGETS[@]}"; do
  name="${target%.py}"
  target_build="$BUILD_DIR/$name"
  mkdir -p "$target_build"
  python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name "$name" \
    --distpath "$DIST_DIR" \
    --workpath "$target_build" \
    --specpath "$target_build" \
    --clean \
    "$target"
done
