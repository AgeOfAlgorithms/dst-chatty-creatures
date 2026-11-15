"""What makes the salamander an axolotl: its colour (the design's olive skin to a pink axolotl's, by a gradient map on
each part's brightness: the ink stays black, the brown spots go to soft rose freckles, the cream belly to a pale
cream-pink) and its gills (three fleshy pink stalks a side, each with a fluffy fringe of filaments, drawn here in the
design's scratchy ink style: Qwen-Image-Edit could not draw one, 2026-11-05).

    python tools/gen/axolotl.py [gill out: art/source/gill_axo.png]      (draws the gill)

As a module: recolor(img) -> img; draw_gill(out).
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INK = (22, 20, 18)

# (brightness -> colour: the ink, the spots, the skin's shade, the skin, its sheen, the belly, white)
STOPS = [
    (0.00, (22, 12, 16)),
    (0.11, (38, 18, 26)),
    (0.26, (206, 122, 136)),
    (0.40, (232, 150, 158)),
    (0.54, (246, 182, 184)),
    (0.66, (252, 206, 204)),
    (0.92, (255, 230, 222)),
    (1.00, (255, 250, 248)),
]


def recolor(img):
    """olive skin to pink: a gradient map on brightness (RGBA in, RGBA out; alpha kept). The spots - dark, but warm
    (brown: their red well above their blue), not ink (grey) - are lifted first, to freckles a little darker than
    the skin"""
    a = np.asarray(img.convert("RGBA")).astype(np.float32) / 255
    rgb = a[..., :3]
    L = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    warm = np.clip((rgb[..., 0] - rgb[..., 2] - 0.035) / 0.05, 0, 1) * np.clip((0.32 - L) / 0.1, 0, 1)
    L = L + warm * 0.13
    xs = np.array([s[0] for s in STOPS], np.float32)
    out = np.stack([np.interp(L, xs, np.array([s[1][c] for s in STOPS], np.float32)) for c in range(3)], -1) / 255
    return Image.fromarray((np.concatenate([out, a[..., 3:4]], -1) * 255 + 0.5).astype(np.uint8), "RGBA")


# --- the gill ------------------------------------------------------------------------------------------------------

STALK, STALK_HI, STALK_SH = (240, 112, 146), (255, 206, 218), (206, 70, 110)
FRINGE_BACK, FRINGE, FRINGE_TIP = (170, 22, 74), (226, 56, 112), (255, 138, 170)
HAIR = (128, 18, 58)


def _band(p, hw):
    d = np.gradient(p, axis=0)
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
    n = np.stack([-d[:, 1], d[:, 0]], 1)
    return np.concatenate([p + n * hw[:, None], (p - n * hw[:, None])[::-1]]), d, n


def draw_gill(out, seed=3, W=600, H=900):
    """one gill stalk on white: its base at the bottom middle, curling back (to the left: the salamander faces
    right) toward its tip at the top"""
    rnd = np.random.default_rng(seed)
    K = 3
    Wk, Hk = W * K, H * K
    Lg = 0.66 * H * K                              # (the stalk's length)
    base = np.array([Wk * 0.60, Hk * 0.965])
    s = np.linspace(0, 1, 120)
    curl = 0.18
    cl = base + np.stack([-curl * Lg * s ** 2 + 0.03 * Lg * np.sin(np.pi * s), -Lg * s], 1)
    hw = Lg * (0.052 - 0.030 * s + 0.018 * np.exp(-(s / 0.07) ** 2))
    stalk, tan, nrm = _band(cl, hw)
    END = 104                                      # (the stalk stops short of the tip, rounded: the fringe's tuft)
    cs, hs = cl[:END], hw[:END]

    def stalk_poly(dr, c, h):
        dr.polygon([tuple(v) for v in _band(c, h)[0]], fill=255)
        r = h[-1]
        dr.ellipse((c[-1][0] - r, c[-1][1] - r, c[-1][0] + r, c[-1][1] + r), fill=255)

    def at(u):
        i = min(len(s) - 1, max(0, int(u * (len(s) - 1))))
        return cl[i], tan[i], nrm[i], hw[i]

    def filament(u, side, length, width, bend):
        p, t, n, h = at(u)
        root = p + n * side * h * 0.7
        # (pointing out and along toward the tip: the tangent turned ~55 degrees out, curling back toward the tip)
        ang = math.radians(68 + rnd.uniform(-10, 10))
        d0 = t * math.cos(ang) + n * side * math.sin(ang)
        d0 = d0 / np.linalg.norm(d0)
        pts, wid = [], []
        q = root.copy()
        d = d0.copy()
        m = 10
        for k in range(m + 1):
            f = k / m
            pts.append(q.copy())
            wid.append(width * (1 - 0.55 * f) * (1 - f ** 6) ** 0.5 + 0.6 * K)      # (blunt, rounded tips)
            rot = math.radians(-side * bend / m)
            c, si = math.cos(rot), math.sin(rot)
            d = np.array([c * d[0] - si * d[1], si * d[0] + c * d[1]])
            q = q + d * length / m
        return np.array(pts), np.array(wid) / 2

    fils_back, fils_front = [], []
    for side in (1, -1):
        u = 0.13
        while u < 0.985:
            env = math.sin(math.pi * min(1, (u - 0.05) / 0.98)) ** 0.7
            length = Lg * (0.08 + 0.17 * env) * rnd.uniform(0.8, 1.2) * (1.0 if side == 1 else 0.9)
            fils_back.append(filament(u + 0.007, side, length * 1.12, Lg * 0.04, rnd.uniform(15, 45)))
            fils_front.append(filament(u, side, length, Lg * 0.036, rnd.uniform(10, 40)))
            u += 0.0145 * rnd.uniform(0.85, 1.15)
    # (a tuft round the tip)
    for k in range(9):
        side = (1, -1, 0)[k % 3]
        fils_front.append(filament(rnd.uniform(0.95, 0.99), side, Lg * rnd.uniform(0.05, 0.08), Lg * 0.03, 15))

    def mask(polys_fn):
        m = Image.new("L", (Wk, Hk), 0)
        dr = ImageDraw.Draw(m)
        polys_fn(dr)
        return m

    def fil_poly(f, extra=0.0):
        pts, w = f
        band, _, _ = _band(pts, w + extra)
        return [tuple(v) for v in band]

    iw = 0.010 * Lg                                # (the ink line)

    def ink_all(dr):
        for j in range(3):
            jit = rnd.normal(0, 0.0025 * Lg, 2)
            for f in fils_back + fils_front:
                dr.polygon(fil_poly((f[0] + jit, f[1]), iw * rnd.uniform(0.8, 1.1)), fill=255)
            stalk_poly(dr, cs + jit, hs + iw * 1.2)

    ink = mask(ink_all)
    back = mask(lambda dr: [dr.polygon(fil_poly(f), fill=255) for f in fils_back]
                + [stalk_poly(dr, cl[END - 20:], hw[END - 20:] * 1.3)])     # (the fringe's core, past the stalk)
    front = mask(lambda dr: [dr.polygon(fil_poly(f), fill=255) for f in fils_front])
    # (the front filaments' tips lighter: their outer halves)
    tips = mask(lambda dr: [dr.polygon(fil_poly((f[0][5:], f[1][5:])), fill=255) for f in fils_front])
    hair = mask(lambda dr: [dr.line([tuple(v) for v in f[0][1:8]], fill=255, width=max(1, int(0.0035 * Lg)))
                            for i, f in enumerate(fils_front) if i % 2 == 0])
    stalk_ink = mask(lambda dr: stalk_poly(dr, cs, hs + iw * 0.9))
    stalk_m = mask(lambda dr: stalk_poly(dr, cs, hs))
    sl = slice(10, 95)
    hi = mask(lambda dr: dr.line([tuple(v) for v in (cl - nrm * hw[:, None] * 0.45)[sl]], fill=255,
                                 width=int(0.016 * Lg), joint="curve"))
    sh = mask(lambda dr: stalk_poly(dr, (cl + nrm * hw[:, None] * 0.5)[:END], hs * 0.5))

    def F(m, sig=0.7):
        return ndimage.gaussian_filter(np.asarray(m).astype(np.float32) / 255, sig * K)

    img = np.ones((Hk, Wk, 3), np.float32) * 255

    def lay(m, col):
        nonlocal img
        img = img * (1 - m[..., None]) + np.array(col, np.float32) * m[..., None]

    lay(F(ink), INK)
    lay(F(back), FRINGE_BACK)
    fr = F(front)
    lay(fr, FRINGE)
    lay(F(tips, 2.5) * fr, FRINGE_TIP)
    lay(F(hair) * fr * 0.55, HAIR)
    lay(F(stalk_ink), INK)
    st = F(stalk_m)
    lay(st, STALK)
    lay(F(sh, 3) * st, STALK_SH)
    lay(F(hi, 1.5) * st * 0.9, STALK_HI)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").resize((W, H), Image.BOX)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out)
    return out


if __name__ == "__main__":
    print(draw_gill(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "art", "source", "gill_axo.png")))
