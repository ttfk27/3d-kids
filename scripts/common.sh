#!/usr/bin/env bash
# متغيرات مشتركة. المسار الجذري للمشروع:
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TP="$ROOT/third_party"
mkdir -p "$TP" "$ROOT/outputs"
# تقسيم البطاقتين: 0 = توليد الشكل (Hunyuan3D)، 1 = الأجزاء (PartCrafter) أو التركسشر
GPU_SHAPE="${GPU_SHAPE:-0}"
GPU_PARTS="${GPU_PARTS:-1}"
