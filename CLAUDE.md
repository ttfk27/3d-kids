# CLAUDE.md — 3d-kids

## الهدف
تحويل شخصية كرتونية (طفلة Pixar: شعر بني، سالوبيت أصفر، حذاء أحمر) من صورة إلى **شخصية 3D قابلة للتحريك والكلام**، محليًا على **2× RTX 3090 (24GB)**. اللغة مع المستخدم: **العربية**.

## لماذا هذا المشروع
Tripo/Meshy تُنتج مجسمًا واحدًا ملتصقًا (أصابع ملتصقة، فم بلا تجويف). الحل: خط إنتاج من مراحل، والأجزاء الدقيقة (عينان، فم، أصابع) تُركَّب ولا تُولَّد.

## الخط
1. `scripts/prep_image.py` — خلفية بيضاء ومربع.
2. `scripts/run_shape.py` — Hunyuan3D-2.1 (GPU 0).
3. `scripts/run_parts.sh` — PartCrafter أجزاء منفصلة (GPU 1).
4. `blender/add_face_rig.py` — 52 ARKit shape key + عينان + فم داخلي.
5. Make-It-Animatable — Rig (واجهة `app.py` فقط، لا CLI موثَّق).
6. لاحقًا: HY-Motion (حركة)، Audio2Face-3D + TTS (كلام).

## الصور المرجعية (`assets/reference/`)
- `body_apose_neutral.webp` — الجسم A-pose (ابتسامة خفيفة).
- `face_neutral_v2.webp` — الوجه المحايد الصحيح (مرجع Basis).
- `character_original.webp` / `face_neutral.webp` — أقدم، فم مفتوح/مبتسم؛ لا تستخدمها كمدخل 3D.

## حالة المشروع (صادقة)
- **لم تُختبر** أي سكربت على GPU؛ فقط `prep_image.py` اختُبر. الأوامر منقولة من README الرسمية.
- `mesh.export()` في `run_shape.py` غير مؤكد على ناتج Hunyuan3D.
- Make-It-Animatable لا يوثّق CLI ولا متطلبات pose.
- دعم العربية في TTS غير مؤكد.
- نحت الـ blendshapes وضبط skin weights يدويان.

## ملاحظة Windows (مهمة)
جهاز المستخدم Windows (`C:\Users\bensa\Downloads\youtube auto\3d-kids`). السكربتات هنا **bash + conda لنظام Linux** (وملف FBX2glTF لنظام Linux)، لذا تُشغَّل داخل **WSL2 (Ubuntu)** وليس PowerShell.
- شغّل Claude Code من داخل WSL، واستنسخ المستودع في نظام ملفات WSL (`~/3d-kids`) لا في `/mnt/c/...` (أسرع وأقل مشاكل).
- تأكد أن `nvidia-smi` داخل WSL يُظهر البطاقتين قبل أي تثبيت.
- Blender يمكن تشغيله على Windows لتحرير الملفات؛ الخرجات في `outputs/` يمكن نسخها إليه.

## قواعد العمل
- قبل أي شيء: `nvidia-smi` وتأكد من وجود بطاقتين؛ ولا تفترض أن البيئة تعمل.
- لا تنسخ أرقام VRAM أو تراخيص من الذاكرة؛ تحقق من README/LICENSE في `third_party/<repo>`.
- كل مشروع ببيئة conda منفصلة (`hy3d`, `partcrafter`, `mia`)؛ لا تخلطها.
- `third_party/` و`outputs/` خارج git. لا تدفع ملفات glb/fbx كبيرة.
- عند فشل خطوة: أصلح السكربت في المستودع (لا حلًا مؤقتًا في الطرفية)، وسجّل ما تغيّر في `docs/TASKS.md`.
- لا تعد بنتيجة قبل رؤيتها: وصف ما ظهر فعلًا في المخرجات (أصابع، أجزاء، فم).
- الفرع: `claude/github-3d-character-animation-rmzrkm`. لا PR إلا بطلب.

انظر `docs/TASKS.md` للمهام بالترتيب.
