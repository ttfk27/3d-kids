# 3d-kids — من صورة شخصية إلى شخصية 3D تتحرك وتتكلم

مشروع محلي على **2× RTX 3090 (24GB لكل بطاقة)**. الفكرة: لا نعتمد على أداة واحدة (Tripo/Meshy تُنتج مجسمًا ملتصقًا)، بل خط إنتاج من مراحل، والأجزاء الدقيقة (العينان، الفم، الأصابع) **تُركَّب** ولا تُولَّد.

> **حالة المشروع:** هيكل بداية. السكربتات كُتبت من README الرسمية للمشاريع ولم تُختبر على GPU
> (بيئة الإنشاء بلا GPU). الاختبار الوحيد الذي تم: `prep_image.py`. توقّع تعديلات عند أول تشغيل.

## الخط العام

```
صورة (وجه محايد، A-pose)
  └─1─> prep_image.py         خلفية بيضاء + مربع
  └─2─> Hunyuan3D 2.1        شكل كامل           (GPU 0)
  └─2b─> PartCrafter          أجزاء منفصلة       (GPU 1)
  └─3─> Blender               فصل/تنظيف + عينان + فم + 52 blendshape
  └─4─> Make-It-Animatable    Rig + skinning تلقائي
  └─5─> HY-Motion             حركة الجسم من نص   (مرحلة لاحقة)
  └─6─> Audio2Face-3D + TTS   كلام وشفاه         (مرحلة لاحقة)
```

| المرحلة | المشروع | الترخيص | VRAM (حسب مصادر غير رسمية) |
|---|---|---|---|
| شكل | [Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) | راجع ملف LICENSE في المستودع | ~10GB شكل / ~21GB تركسشر / ~29GB معًا |
| أجزاء | [PartCrafter](https://github.com/wgsxm/PartCrafter) | MIT | 8GB على الأقل |
| Rig | [Make-It-Animatable](https://github.com/jasongzy/Make-It-Animatable) | MIT | غير مذكور |

## البدء

```bash
# 1) تجهيز الصورة (جاهزة ببيئة بايثون عادية + Pillow)
python3 scripts/prep_image.py assets/reference/character_original.webp outputs/character_prep.png

# 2) تثبيت (كل مشروع ببيئة conda منفصلة)
bash scripts/setup_hunyuan.sh
bash scripts/setup_partcrafter.sh
bash scripts/setup_mia.sh

# 3) توليد — بطاقتان تعملان بالتوازي
conda activate hy3d
CUDA_VISIBLE_DEVICES=0 python scripts/run_shape.py outputs/character_prep.png            # شكل فقط
bash scripts/run_parts.sh outputs/character_prep.png 6 girl_v1                           # على GPU 1

# 4) Blender: فصل الأجزاء، ثم
blender your.blend --python blender/add_face_rig.py -- --head Head
```

## ملاحظات مهمة عن الصورة المرجعية

الصورة الحالية (`assets/reference/character_original.webp`) فمها **مفتوح** بأسنان ولسان، وهذا يُنتج كتلة ملتصقة في أي مولّد 3D.
**ولّد نسخة بفم مغلق ومحايد** قبل التشغيل — الوصفات في [docs/image_prompts.md](docs/image_prompts.md). الأجزاء المتوقع فصلها: شعر، رأس، جسم/قميص، سالوبيت، حذاءان، يدان.

## ما يبقى يدويًا (بصراحة)

- نحت الـ 52 blendshape (السكربت يُنشئها فارغة بأسماء ARKit فقط).
- تموضع العينين والفم الداخلي (السكربت يضع بدائل بمكان تقريبي).
- ضبط skin weights عند الكتف والرقبة: نِسب الشخصية كرتونية (رأس كبير) وقد لا يناسبها الـ rigging التلقائي المدرَّب على نِسب بشرية.
- العربية في TTS: لم يُتحقق من دعمها في Fish Speech / CosyVoice؛ ابحث عن fine-tune عربي قبل الاعتماد عليها.

## هيكل المستودع

```
assets/reference/   الصور المرجعية
scripts/            التثبيت والتشغيل
blender/            سكربتات Blender + قائمة ARKit
docs/               وصفات الصور
third_party/        (مستبعد من git) المشاريع المستنسخة
outputs/            (مستبعد من git) النتائج
```
