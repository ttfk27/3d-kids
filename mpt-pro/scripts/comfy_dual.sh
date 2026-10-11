#!/usr/bin/env bash
# One ComfyUI per GPU so mptpro can generate two clips at once. Usage: COMFY_DIR=~/ComfyUI scripts/comfy_dual.sh
set -euo pipefail
COMFY_DIR="${COMFY_DIR:?set COMFY_DIR to your ComfyUI checkout}"
PYTHON="${PYTHON:-python}"
cd "$COMFY_DIR"
trap 'kill 0' EXIT
CUDA_VISIBLE_DEVICES=0 "$PYTHON" main.py --listen 127.0.0.1 --port 8188 &
CUDA_VISIBLE_DEVICES=1 "$PYTHON" main.py --listen 127.0.0.1 --port 8189 &
wait
