#!/usr/bin/env bash
set -euo pipefail

# Tear down the vox_meter null sink and any loopback modules pointing to it.

if ! command -v pactl >/dev/null 2>&1; then
  echo "pactl not found. Install PulseAudio/PipeWire utilities." >&2
  exit 1
fi

NULL_SINK_NAME="vox_meter"

# Restore defaults before unloading modules.
if pactl info >/dev/null 2>&1; then
  echo "Restoring default sink/source to @DEFAULT_SINK@ / @DEFAULT_SOURCE@"
  pactl set-default-sink @DEFAULT_SINK@ 2>/dev/null || true
  pactl set-default-source @DEFAULT_SOURCE@ 2>/dev/null || true
fi

# Unload loopback modules that reference the vox_meter monitor.
while read -r id rest; do
  if [[ "$rest" == *"${NULL_SINK_NAME}.monitor"* ]]; then
    pactl unload-module "$id" || true
    echo "Unloaded loopback module $id"
  fi
done < <(pactl list short modules)

# Unload the null sink module itself.
while read -r id rest; do
  if [[ "$rest" == *"module-null-sink"* && "$rest" == *"$NULL_SINK_NAME"* ]]; then
    pactl unload-module "$id" || true
    echo "Unloaded null sink module $id"
  fi
done < <(pactl list short modules)

echo "Teardown complete. Restore your default sink if needed:"
echo "  pactl set-default-sink @DEFAULT_SINK@"
