"""سكربت Blender: يجهّز الوجه للـ lip-sync.
التشغيل:  blender character.blend --python blender/add_face_rig.py -- --head HeadMesh
يقوم بـ:
  1) إضافة 52 Shape Key فارغًا بأسماء ARKit إلى شبكة الرأس (يجب نحتها يدويًا بعد ذلك).
  2) إنشاء كرتي العينين وتجويف الفم/اللسان/الأسنان كأجسام مستقلة (مكان مؤقت تضبطه يدويًا).
هذا هيكل بداية وليس نتيجة نهائية: الشكل الفعلي للـ blendshapes يحتاج نحتًا أو نقلًا من قالب.
"""
import sys
from pathlib import Path
import bpy

ARKIT = (Path(__file__).parent / "arkit_blendshapes.txt").read_text().split()


def arg(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index(name) + 1] if name in argv else default


head = bpy.data.objects.get(arg("--head", "Head"))
if head is None:
    raise SystemExit("لم أجد شبكة الرأس. مرّر الاسم عبر: -- --head <name>")

if head.data.shape_keys is None:
    head.shape_key_add(name="Basis")
for n in ARKIT:
    if n not in head.data.shape_keys.key_blocks:
        head.shape_key_add(name=n, from_mix=False)


def add(kind, name, loc, scale):
    getattr(bpy.ops.mesh, kind)(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.parent = head
    return o


for side, x in (("L", 0.35), ("R", -0.35)):
    add("primitive_uv_sphere_add", f"Eye_{side}", (x, -0.7, 0.2), (0.18, 0.18, 0.18))
add("primitive_uv_sphere_add", "MouthInterior", (0, -0.55, -0.35), (0.3, 0.2, 0.15))
add("primitive_uv_sphere_add", "Tongue", (0, -0.6, -0.4), (0.15, 0.12, 0.05))
add("primitive_cube_add", "TeethUpper", (0, -0.7, -0.28), (0.22, 0.03, 0.03))
add("primitive_cube_add", "TeethLower", (0, -0.7, -0.42), (0.2, 0.03, 0.03))
print(f"added {len(ARKIT)} shape keys + eye/mouth placeholders on {head.name}")
