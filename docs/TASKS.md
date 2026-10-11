# المهام (للتنفيذ على جهاز الـ GPU)

علّم كل مهمة `[x]` عند إنجازها فعلًا واكتب تحتها ملاحظات الأخطاء والإصلاحات.

## 0. البيئة
- [ ] `nvidia-smi -L` يُظهر بطاقتين 3090. `conda --version`، `git`، `blender --version`.
- [ ] `python3 scripts/prep_image.py assets/reference/body_apose_neutral.webp outputs/body_prep.png`

## 1. Hunyuan3D (GPU 0)
- [ ] `bash scripts/setup_hunyuan.sh` (راجع الأخطاء، خصوصًا compile_mesh_painter وcustom_rasterizer).
- [ ] `conda activate hy3d && CUDA_VISIBLE_DEVICES=0 python scripts/run_shape.py outputs/body_prep.png` ينتج `outputs/shape/shape.glb`.
- [ ] تأكد من `mesh.export` وإلا أصلح `run_shape.py`.
- [ ] (اختياري) `--texture` على GPU بذاكرة كافية (~21GB؛ أو `--low_vram_mode` عبر gradio_app).
- [ ] افتح النتيجة في Blender وسجّل: هل الأصابع منفصلة؟ هل الشعر ملتصق؟

## 2. PartCrafter (GPU 1)
- [ ] `bash scripts/setup_partcrafter.sh`
- [ ] `bash scripts/run_parts.sh outputs/body_prep.png 6 girl_v1` ثم جرّب 4 و8 أجزاء.
- [ ] قارن مع نتيجة Hunyuan3D: أيهما أنظف وأقرب لفصل (شعر/رأس/جسم/سالوبيت/حذاءان/يدان)؟

## 2b. Pixal3D Multiview (ComfyUI، Windows مباشرة أو WSL) — انظر docs/PIXAL3D.md
- [ ] حضّر 4 صور بروفايل حقيقية (أمام/يسار/خلف/يمين) من `body_apose_neutral.webp`، 1024×1024، خلفية مزالة.
- [ ] نفّذ الـ workflow وقارن GLB مع Hunyuan3D وPartCrafter (أصابع، شعر، أجزاء).

## 3. Blender
- [ ] ادمج/نظّف الأجزاء، سمِّ الرأس `Head`.
- [ ] `blender file.blend --python blender/add_face_rig.py -- --head Head` ثم ضبط مواضع العينين والفم.
- [ ] نحت الـ blendshapes الأساسية: `jawOpen`, `mouthSmile*`, `mouthFunnel`, `mouthPucker`, `eyeBlink*` أولًا.

## 4. Rig
- [ ] `bash scripts/setup_mia.sh` ثم `python app.py` (واجهة)؛ اختبر على النموذج وصدّر FBX.
- [ ] راجع skin weights عند الكتف والرقبة (نِسب كرتونية).

## 5. لاحقًا
- [ ] HY-Motion → retarget على الـ Rig.
- [ ] Audio2Face-3D (blendshapes ARKit) + TTS (تحقق من العربية أولًا).
