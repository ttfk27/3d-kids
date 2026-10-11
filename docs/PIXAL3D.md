# Pixal3D Multiview (مرشّح لمرحلة الشكل)

مصدر: https://github.com/pixelartistry/PixelArtistry-Pixal3D-MultiView (ترخيص الـ workflow: MIT؛ النماذج لها تراخيصها الخاصة).

## ما هو (حسب README المستودع)
- Workflow جاهز لـ **ComfyUI** (عقد core فقط، بلا custom nodes): نص ← ورقة turnaround بأربع زوايا ← Pixal3D Multiview ← **GLB واحد بتركسشر**.
- المدخل: 4 صور 1024×1024، خلفية مزالة، الشخصية في المنتصف: أمام / يسار / خلف / يمين بخطوة 90° ثابتة. **الجوانب بروفايل حقيقي لا ثلاثة أرباع.**
- النماذج المطلوبة ~25GB: Qwen-Image 2.1 (6.76GB)، Pixal3D Multiview (5.2GB)، Qwen3-VL 8B text encoder (8.71GB)، ثلاثة VAE، DINOv3 clip vision، BiRefNet.
- VRAM: ~12GB حسب تجربة صاحب المستودع (غير مؤكَّد على جهازنا).
- يوجد `download_models_win.bat` ⇒ يعمل على Windows مباشرة (بدون WSL) لهذه المرحلة.

## ما لا يفعله (بحسب README)
- لا يذكر فصل الأجزاء ولا الـ rigging ⇒ الناتج مجسم واحد؛ مشكلة الأصابع/الفم/الشعر تبقى، والمراحل 3-4 (Blender + Make-It-Animatable) ما زالت لازمة.
- يولّد الزوايا من **نص**، لا من شخصيتنا الموجودة. لشخصيتنا نحتاج 4 صور بروفايل حقيقية بنفس التصميم (توليدها بنموذج تحرير صور من `body_apose_neutral.webp`)، ثم تمريرها بدل عقد توليد الورقة. هل يقبل الـ workflow ذلك بسهولة: غير مؤكد.

## غير مؤكَّد (لم أستطع فتحه من بيئتي)
- روابط Hugging Face وpixel-artistry.com محجوبة من بيئة الإنشاء، فلم أقرأ صفحة Comfy-Org/Pixal3D ولا دليلي GGUF وTrellis 2.
- رابط "Qwen Image 2.1" المُرسَل يشير إلى `Qwen/Qwen2.5-VL-7B-Instruct`، وهو نموذج **فهم صور/نص** لا مولّد صور. المطلوب حسب README هو Qwen-Image 2.1 (diffusion) + Qwen3-VL 8B كـ text encoder؛ استخدم سكربت التحميل في المستودع لا الرابط.

## كيف يدخل في الخط
شكل (بديل/مقارنة مع Hunyuan3D وPartCrafter) ← Blender (فصل + وجه) ← Make-It-Animatable. قارن الثلاثة على نفس الشخصية.
