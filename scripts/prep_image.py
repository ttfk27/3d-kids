#!/usr/bin/env python3
"""يحوّل صورة الشخصية إلى PNG مربع بخلفية بيضاء نقية (مدخل مناسب لنماذج 3D)."""
import argparse
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--margin", type=float, default=0.06, help="هامش نسبي حول الشخصية")
    a = ap.parse_args()

    img = Image.open(a.src).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img).convert("RGB")

    # اقتصاص حدود الشخصية (كل ما ليس أبيض تقريبًا)
    mask = img.convert("L").point(lambda p: 255 if p < 245 else 0)
    box = mask.getbbox()
    if box:
        img = img.crop(box)

    side = int(max(img.size) * (1 + 2 * a.margin))
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    canvas.resize((a.size, a.size), Image.LANCZOS).save(a.dst)
    print(f"saved {a.dst} ({a.size}x{a.size})")


if __name__ == "__main__":
    main()
