"""The anger mark: the comic popping vein (four thick curved red pieces, their backs bowed in toward the middle, the
gaps between them a cross), drawn in the heart's style (glossy red, a scratchy thick black ink outline, a white
highlight on each piece), on plain white like the generated drawings, so cutout.py cuts it the same way.

    python tools/gen/vein.py [out: art/source/fx_vein.png]

(Qwen-Image-Edit drew a red X for it, 2026-11-05: so drawn here.)
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIZE = 512
K = 4                                  # (drawn this much bigger, boxed down)
INK = (22, 20, 18)
RED, DARK, LIGHT = (214, 46, 44), (150, 22, 30), (255, 236, 232)


def bez(a, c, b, n=40):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * a + 2 * (1 - t) * t * c + t ** 2 * b, t[:, 0]


def piece(rot):
    """one piece (unit coords, centre 0, y down): its centre line and half widths, turned rot degrees"""
    a, c, b = np.array([-0.92, -0.25]), np.array([-0.21, -0.21]), np.array([-0.25, -0.92])
    p, t = bez(a, c, b)
    hw = 0.075 + 0.05 * np.sin(np.pi * t)        # (fat in its middle)
    th = math.radians(rot)
    R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    return p @ R.T, hw


def outline(p, hw):
    """the band round a centre line (flat ends: round_ends puts discs on them)"""
    d = np.gradient(p, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    return np.concatenate([p + nrm * hw[:, None], (p - nrm * hw[:, None])[::-1]])


def band(draw_, px, p, hw, scale):
    draw_.polygon(px(outline(p, hw)), fill=255)
    for i in (0, -1):
        (X, Y), = px([p[i]])
        r = hw[i] * scale
        draw_.ellipse((X - r, Y - r, X + r, Y + r), fill=255)


def draw(out, seed=5):
    rnd = np.random.default_rng(seed)
    W = SIZE * K
    scale = W * 0.40                   # (unit -> pixels: the mark fills ~80% of the canvas)
    cx = cy = W / 2
    px = lambda q: [(cx + x * scale, cy + y * scale) for x, y in q]  # noqa: E731
    ink = Image.new("L", (W, W), 0)
    fill = Image.new("L", (W, W), 0)
    shade = Image.new("L", (W, W), 0)
    hi = Image.new("L", (W, W), 0)
    di, df, ds, dh = (ImageDraw.Draw(m) for m in (ink, fill, shade, hi))
    iw = 0.06                          # (the ink line, unit)
    for rot in (0, 90, 180, 270):
        p, hw = piece(rot + rnd.uniform(-4, 4))
        p = p * rnd.uniform(0.96, 1.04)
        # (ink: the piece fattened, drawn a few times jittered: a scratchy edge)
        for j in range(5):
            jit = rnd.normal(0, 0.012, p.shape)
            band(di, px, p + jit, hw + iw * rnd.uniform(0.85, 1.1), scale)
        band(df, px, p, hw, scale)
        # (the shade: the outer half - away from the middle)
        d = np.gradient(p, axis=0)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        nrm = np.stack([-d[:, 1], d[:, 0]], 1)
        outward = np.sign((nrm * p).sum(1, keepdims=True))
        o = p + nrm * outward * hw[:, None] * 0.45
        band(ds, px, o, hw * 0.55, scale)
        # (the highlight: a thin stroke along its inner side, its middle only)
        h = p - nrm * outward * hw[:, None] * 0.38
        sl = slice(int(len(h) * 0.22), int(len(h) * 0.62))
        dh.line(px(h[sl]), fill=255, width=int(0.045 * scale), joint="curve")
        q = h[int(len(h) * 0.72)]
        r = 0.028 * scale
        X, Y = cx + q[0] * scale, cy + q[1] * scale
        dh.ellipse((X - r, Y - r, X + r, Y + r), fill=255)
    # (a few loose hairlines along the outside, as the heart has)
    for _ in range(10):
        rot = rnd.choice([0, 90, 180, 270])
        p, hw = piece(rot)
        i0 = rnd.integers(0, 25)
        seg = p[i0:i0 + rnd.integers(8, 15)]
        d = np.gradient(seg, axis=0)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        nrm = np.stack([-d[:, 1], d[:, 0]], 1)
        outward = np.sign((nrm * seg).sum(1, keepdims=True))
        seg = seg + nrm * outward * (hw[i0:i0 + len(seg), None] + iw * rnd.uniform(1.1, 1.6))
        di.line(px(seg), fill=255, width=max(2, int(0.012 * scale)), joint="curve")
    f = lambda m, s=1.0: ndimage.gaussian_filter(np.asarray(m).astype(np.float32) / 255, s)  # noqa: E731
    fa, sa, ha, ia = f(fill), f(shade, K * 2.5), f(hi, K * 0.8), f(ink)
    sa *= fa
    ha = ha * ndimage.binary_erosion(np.asarray(fill) > 128, iterations=K * 3)
    col = np.array(RED, np.float32) * (1 - sa[..., None]) + np.array(DARK, np.float32) * sa[..., None]
    col = col * (1 - ha[..., None]) + np.array(LIGHT, np.float32) * ha[..., None]
    out_a = np.ones((W, W, 3), np.float32) * 255
    out_a = out_a * (1 - ia[..., None]) + np.array(INK, np.float32) * ia[..., None]
    out_a = out_a * (1 - fa[..., None]) + col * fa[..., None]
    im = Image.fromarray(np.clip(out_a, 0, 255).astype(np.uint8), "RGB").resize((SIZE, SIZE), Image.BOX)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out)
    return out


if __name__ == "__main__":
    print(draw(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "art", "source", "fx_vein.png")))
