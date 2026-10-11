#!/usr/bin/env python3
"""المرحلة 1: صورة -> مجسم Hunyuan3D-2.1 (شكل فقط، ثم تركسشر اختياريًا).
يُشغَّل من بيئة hy3d:  CUDA_VISIBLE_DEVICES=0 python scripts/run_shape.py ...
ملاحظة: لم يُختبر على GPU داخل بيئة الإنشاء؛ واجهة الـ pipeline مأخوذة من README الرسمي.
"""
import argparse, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HY = ROOT / "third_party" / "Hunyuan3D-2.1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default=str(ROOT / "outputs" / "shape"))
    ap.add_argument("--texture", action="store_true", help="توليد تركسشر (يحتاج ~21GB VRAM)")
    a = ap.parse_args()

    os.chdir(HY)  # المسارات في المستودع نسبية للجذر
    sys.path.insert(0, str(HY / "hy3dshape"))
    sys.path.insert(0, str(HY / "hy3dpaint"))
    from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline

    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    image = str(Path(a.image).resolve())

    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained("tencent/Hunyuan3D-2.1")
    mesh = pipe(image=image)[0]
    shape_path = out / "shape.glb"
    mesh.export(str(shape_path))
    print("shape ->", shape_path)

    if a.texture:
        import torch, gc
        del pipe; gc.collect(); torch.cuda.empty_cache()
        from textureGenPipeline import Hunyuan3DPaintPipeline, Hunyuan3DPaintConfig
        paint = Hunyuan3DPaintPipeline(Hunyuan3DPaintConfig(max_num_view=6, resolution=512))
        obj_path = out / "shape.obj"
        mesh.export(str(obj_path))
        tex = paint(str(obj_path), image_path=image)
        print("textured ->", tex)


if __name__ == "__main__":
    main()
