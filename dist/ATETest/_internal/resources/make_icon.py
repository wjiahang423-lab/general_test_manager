"""
生成 app.ico — ATETest 图标
依赖: Pillow (pip install pillow)

图标设计:
  深蓝背景圆角矩形，上方大字 "ATE"，下方小字 "Test"，左侧绿色竖条装饰
尺寸: 16 32 48 64 128 256 (多尺寸 ico)
"""

from __future__ import annotations
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[make_icon] Pillow 未安装，执行: pip install pillow")
    sys.exit(1)


OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")

_BG       = (18,  42,  88)   # 深蓝
_BG2      = (26,  58, 116)   # 稍浅蓝
_ACCENT   = (46, 196, 108)   # 绿色
_WHITE    = (255, 255, 255)
_GRAY     = (180, 200, 230)  # 副文字


def _rounded_rect(d: ImageDraw.ImageDraw, box, r: int, fill):
    x0, y0, x1, y1 = box
    # clamp radius so it never exceeds half the smallest dimension
    r = min(r, (x1 - x0) // 2, (y1 - y0) // 2)
    if r <= 0:
        d.rectangle([x0, y0, x1, y1], fill=fill)
        return
    d.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    d.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
    for cx, cy, a0, a1 in (
        (x0 + r, y0 + r, 180, 270),
        (x1 - r, y0 + r, 270, 360),
        (x1 - r, y1 - r,   0,  90),
        (x0 + r, y1 - r,  90, 180),
    ):
        d.pieslice([cx - r, cy - r, cx + r, cy + r], a0, a1, fill=fill)


def _make_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    pad = max(1, size // 16)
    r   = max(3, size // 10)
    x0, y0, x1, y1 = pad, pad, size - pad - 1, size - pad - 1

    # 背景
    _rounded_rect(d, (x0, y0, x1, y1), r, _BG2)

    # 左侧绿色竖条
    bar_w = max(2, size // 14)
    _rounded_rect(d, (x0, y0, x0 + bar_w, y1), r, _ACCENT)
    # 遮掉右侧圆角使竖条右边是直边
    d.rectangle([x0 + bar_w // 2, y0, x0 + bar_w, y1], fill=_ACCENT)

    if size >= 48:
        # 大号 "ATE"
        ate_size  = max(8, int(size * 0.40))
        test_size = max(5, int(size * 0.22))
        try:
            font_ate  = ImageFont.truetype("arialbd.ttf", ate_size)
            font_test = ImageFont.truetype("arial.ttf",   test_size)
        except Exception:
            font_ate  = ImageFont.load_default()
            font_test = font_ate

        cx = (x0 + bar_w + x1) // 2
        # "ATE"
        bb = d.textbbox((0, 0), "ATE", font=font_ate)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        ty = y0 + int(size * 0.15)
        d.text((cx - tw // 2, ty), "ATE", font=font_ate, fill=_WHITE)
        # "Test"
        bb2 = d.textbbox((0, 0), "Test", font=font_test)
        tw2 = bb2[2] - bb2[0]
        ty2 = ty + th + max(1, size // 24)
        d.text((cx - tw2 // 2, ty2), "Test", font=font_test, fill=_ACCENT)
    else:
        # 小尺寸：只画简单文字 "AT"
        try:
            font = ImageFont.truetype("arialbd.ttf", max(6, size // 3))
        except Exception:
            font = ImageFont.load_default()
        bb = d.textbbox((0, 0), "AT", font=font)
        tw = bb[2] - bb[0]
        cx = (x0 + bar_w + x1) // 2
        d.text((cx - tw // 2, y0 + size // 6), "AT", font=font, fill=_WHITE)

    return img


def build_ico():
    sizes = [16, 32, 48, 64, 128, 256]
    frames = [_make_frame(s) for s in sizes]
    frames[0].save(
        OUT,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"[make_icon] 图标已生成: {OUT}")


if __name__ == "__main__":
    build_ico()
