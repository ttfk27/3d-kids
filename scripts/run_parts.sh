#!/usr/bin/env bash
# المرحلة 2: صورة -> أجزاء منفصلة بـ PartCrafter (بطاقة GPU_PARTS)
# الاستخدام: scripts/run_parts.sh outputs/prep/character.png 6 girl_v1
set -euo pipefail
source "$(dirname "$0")/common.sh"
IMG="$(realpath "$1")"; PARTS="${2:-6}"; TAG="${3:-character}"
eval "$(conda shell.bash hook)"; conda activate partcrafter
cd "$TP/PartCrafter"
CUDA_VISIBLE_DEVICES="$GPU_PARTS" python scripts/inference_partcrafter.py \
  --image_path "$IMG" --num_parts "$PARTS" --tag "$TAG" --rmbg --render
echo "النتائج في: $TP/PartCrafter/results/$TAG"
