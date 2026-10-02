#!/usr/bin/env python3
"""Stamps photos with the "Made With Love" watermark used across the site.

Style: a single diagonal line of text through the centre of the photo,
white at 50% opacity, so it's hard to crop out but doesn't block the
flowers underneath.

This is wired into build_flower_site.py already — every catalogue photo
pulled in from catalogue-data.json gets watermarked automatically, every
time the site is rebuilt, so nothing extra is needed for those.

For a photo added by hand to images/ (the Home/Portfolio hero-style shots,
not the catalogue), run this once before uploading it:

    python3 watermark.py images/your-new-photo.jpg

That overwrites the file in place with the watermark applied. Pass several
files to do more than one at once.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

TEXT = "Made With Love"
ALPHA = 128  # 50% opacity
ROTATION_DEGREES = 30

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def watermark_image(src_path, out_path=None):
    """Applies the centred-diagonal "Made With Love" watermark to the image
    at src_path and saves it to out_path (defaults to overwriting src_path).
    Safe to call on any JPEG/PNG; always writes a JPEG out."""
    out_path = out_path or src_path
    im = Image.open(src_path).convert("RGBA")
    w, h = im.size

    font = _load_font(max(28, w // 10))
    txt_img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt_img)
    bbox = d.textbbox((0, 0), TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((w * 2 - tw) / 2, (h * 2 - th) / 2), TEXT, font=font, fill=(255, 255, 255, ALPHA))
    txt_img = txt_img.rotate(ROTATION_DEGREES, expand=False)
    left = (txt_img.width - w) // 2
    top = (txt_img.height - h) // 2
    txt_img = txt_img.crop((left, top, left + w, top + h))

    out_im = Image.alpha_composite(im, txt_img).convert("RGB")
    out_im.save(out_path, quality=92)
    return out_path


def watermark_bytes(data, is_png=False):
    """Same as watermark_image, but takes raw image bytes and returns raw
    JPEG bytes back out — used by build_flower_site.py so a freshly
    decoded catalogue photo never has to round-trip through a second,
    unwatermarked file on disk."""
    import io
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    w, h = im.size

    font = _load_font(max(28, w // 10))
    txt_img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt_img)
    bbox = d.textbbox((0, 0), TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((w * 2 - tw) / 2, (h * 2 - th) / 2), TEXT, font=font, fill=(255, 255, 255, ALPHA))
    txt_img = txt_img.rotate(ROTATION_DEGREES, expand=False)
    left = (txt_img.width - w) // 2
    top = (txt_img.height - h) // 2
    txt_img = txt_img.crop((left, top, left + w, top + h))

    out_im = Image.alpha_composite(im, txt_img).convert("RGB")
    buf = io.BytesIO()
    out_im.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 watermark.py <image1> [image2 ...]")
        sys.exit(1)
    for path in sys.argv[1:]:
        watermark_image(path)
        print("watermarked:", path)
