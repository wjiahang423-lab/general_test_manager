"""
生成 app.ico — 通用测试管理工具图标
依赖: Pillow (pip install pillow)

图标设计:
  深蓝背景圆角矩形，中央绿色三角（运行），右下角绿色勾（通过）
尺寸: 256x256  16x16  32x32  48x48  (多尺寸 ico)
"""

from __future__ import annotations
import math
import os
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("[make_icon] Pillow 未安装，执行: pip install pillow")
    sys.exit(1)


OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")

_BG       = (30,  60, 110)   # 深蓝
_BG_LIGHT = (40,  80, 140)   # 稍浅蓝（渐变模拟）
_GREEN    = (46, 180, 100)   # 运行三角 & 勾
_WHITE    = (255, 255, 255)
_ALPHA    = 0                # 透明


def _make_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    r   = max(4, size // 8)          # 圆角半径
    pad = max(1, size // 16)         # 边距

    # --- 背景圆角矩形 ---
    x0, y0 = pad, pad
    x1, y1 = size - pad - 1, size - pad - 1

    # 填充两种颜色模拟轻微渐变（上半深 / 下半浅）
    for y in range(y0 + r, y1 - r + 1):
        t = (y - y0) / max(1, y1 - y0)
        color = tuple(
            int(_BG[i] + (_BG_LIGHT[i] - _BG[i]) * t) for i in range(3)
        ) + (255,)
        d.line([(x0, y), (x1, y)], fill=color)

    # 圆角：用四个圆弧填充角
    for cx, cy, a0, a1 in (
        (x0 + r, y0 + r, 180, 270),
        (x1 - r, y0 + r, 270, 360),
        (x1 - r, y1 - r,   0,  90),
        (x0 + r, y1 - r,  90, 180),
    ):
        d.pieslice([cx - r, cy - r, cx + r, cy + r], a0, a1,
                   fill=_BG_LIGHT + (255,), outline=None)

    # 左右竖条（圆角矩形两侧）
    d.rectangle([x0, y0 + r, x0 + r - 1, y1 - r], fill=_BG + (255,))
    d.rectangle([x1 - r + 1, y0 + r, x1, y1 - r], fill=_BG_LIGHT + (255,))

    # --- 中央播放三角形 ---
    cx   = size // 2
    cy   = int(size * 0.45)
    th   = int(size * 0.38)          # 三角高度
    tw   = int(th * 0.87)            # 三角宽度 ≈ 等边
    p1   = (cx - tw // 2,           cy - th // 2)
    p2   = (cx - tw // 2,           cy + th // 2)
    p3   = (cx - tw // 2 + tw,      cy)
    d.polygon([p1, p2, p3], fill=_GREEN + (255,))

    # --- 右下角勾（✓）---
    if size >= 32:
        sw   = max(2, size // 24)    # 线宽
        bx   = int(size * 0.55)
        by   = int(size * 0.62)
        arm  = int(size * 0.14)
        pts  = [
            (bx,        by + arm // 2),
            (bx + arm // 2, by + arm),
            (bx + arm,  by),
        ]
        d.line(pts, fill=_GREEN + (255,), width=sw)

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
