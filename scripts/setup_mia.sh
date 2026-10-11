#!/usr/bin/env bash
# تثبيت Make-It-Animatable (Rig تلقائي) — الترخيص MIT
set -euo pipefail
source "$(dirname "$0")/common.sh"
[ -d "$TP/Make-It-Animatable" ] || git clone https://github.com/jasongzy/Make-It-Animatable --recursive --single-branch "$TP/Make-It-Animatable"
conda create -y -n mia python=3.11
eval "$(conda shell.bash hook)"; conda activate mia
cd "$TP/Make-It-Animatable"
pip install -r requirements.txt huggingface_hub
hf download jasongzy/Make-It-Animatable --include 'output/best/new/**' --local-dir .
hf download jasongzy/Make-It-Animatable --include 'data/**' --local-dir .
wget -nc https://github.com/facebookincubator/FBX2glTF/releases/download/v0.9.7/FBX2glTF-linux-x64 -O util/FBX2glTF
chmod +x util/FBX2glTF
echo "تم. التشغيل: conda activate mia && cd third_party/Make-It-Animatable && python app.py"
