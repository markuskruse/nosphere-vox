#!/usr/bin/env bash
set -euo pipefail

# Create a null sink named vox_meter and loop its monitor to the default sink.
# Requires pactl (PulseAudio/PipeWire).

if ! command -v pactl >/dev/null 2>&1; then
  echo "pactl not found. Install PulseAudio/PipeWire utilities." >&2
  exit 1
fi

NULL_SINK_NAME="vox_meter"
NULL_SINK_DESC="Vox_Meter"

# Load null sink if not already loaded.
if pactl list short sinks | grep -q "$NULL_SINK_NAME"; then
  echo "Null sink '$NULL_SINK_NAME' already exists."
else
  echo "Loading null sink '$NULL_SINK_NAME'..."
  # Try a few argument forms to avoid parse errors on different PA builds.
  attempt_args=(
    "sink_name=$NULL_SINK_NAME sink_properties=device.description=$NULL_SINK_DESC"
    "sink_name=$NULL_SINK_NAME format=s16le channels=2 rate=44100 sink_properties=device.description=$NULL_SINK_DESC"
    "sink_name=$NULL_SINK_NAME"
  )
  loaded=false
  for args in "${attempt_args[@]}"; do
    echo "Attempt: pactl load-module module-null-sink $args"
    if pactl load-module module-null-sink $args >/dev/null; then
      loaded=true
      echo "Created null sink '$NULL_SINK_NAME' with args: $args"
      break
    else
      echo "Attempt failed: $args"
    fi
  done
  if [ "$loaded" = false ]; then
    echo "Failed to load module-null-sink after attempts. Current sinks/modules:"
    echo "--- Sinks ---"
    pactl list short sinks || true
    echo "--- Modules ---"
    pactl list short modules || true
    echo "--- pactl info ---"
    pactl info || true
    echo "Tips:"
    echo " - If Server Name shows PipeWire, ensure pipewire-pulse/libspa-0.2-modules are installed and restart your session."
    echo " - On PulseAudio, module-null-sink is present but rejecting args; try editing /etc/pulse/default.pa to add:"
    echo "     load-module module-null-sink sink_name=$NULL_SINK_NAME"
    echo "   then restart PulseAudio (pulseaudio -k)."
    exit 1
  fi
fi

# Set as default sink.
pactl set-default-sink "$NULL_SINK_NAME"
echo "Default sink set to '$NULL_SINK_NAME'."

# Set default source to the monitor so metering sees speaker output.
pactl set-default-source "${NULL_SINK_NAME}.monitor" || true
echo "Default source set to '${NULL_SINK_NAME}.monitor'."

echo "To meter: python vox-meter.py ${NULL_SINK_NAME}.monitor"
