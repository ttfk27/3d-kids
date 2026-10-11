#!/usr/bin/env bash
# تثبيت PartCrafter (Python 3.11 + torch 2.5.1 cu124) — الترخيص MIT
set -euo pipefail
source "$(dirname "$0")/common.sh"
[ -d "$TP/PartCrafter" ] || git clone https://github.com/wgsxm/PartCrafter.git "$TP/PartCrafter"
conda create -y -n partcrafter python=3.11.13
eval "$(conda shell.bash hook)"; conda activate partcrafter
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124
cd "$TP/PartCrafter" && bash settings/setup.sh
echo "تم. الأوزان تُحمَّل تلقائيًا عند أول تشغيل."
