#!/usr/bin/env bash
# تثبيت Hunyuan3D-2.1 (Python 3.10 + torch 2.5.1 cu124 حسب README الرسمي)
set -euo pipefail
source "$(dirname "$0")/common.sh"
[ -d "$TP/Hunyuan3D-2.1" ] || git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1.git "$TP/Hunyuan3D-2.1"
conda create -y -n hy3d python=3.10
eval "$(conda shell.bash hook)"; conda activate hy3d
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124
cd "$TP/Hunyuan3D-2.1"
pip install -r requirements.txt
pip install trimesh pillow
# rasterizer + mesh painter للتركسشر
(cd hy3dpaint/custom_rasterizer && pip install -e .)
(cd hy3dpaint/DifferentiableRenderer && bash compile_mesh_painter.sh)
mkdir -p hy3dpaint/ckpt
wget -nc https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth -P hy3dpaint/ckpt
echo "تم. فعّل البيئة: conda activate hy3d"
