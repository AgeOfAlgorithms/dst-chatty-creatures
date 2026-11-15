"""The salamander (an axolotl) drawn as vectors: each part its own closed shape, with its own scratchy ink outline, so
nothing of a neighbour is ever on it (sal_parts.py cut the parts out of one painted design: a leg came with the
belly's line, the jaw only as deep as the paint under the smile). The shapes are traced over the design
(art/source/clean531.png, its canvas's pixels: 1328 x 800, y down), so the proportions and the joints are its.

    python tools/gen/sal_vector.py      (-> art/parts/<symbol>/<key>.png and art/parts/parts.json, as sal_parts.py)

The style, the design's: flat skin, a lighter rim along the top and a deeper shade along the bottom, a heavy uneven
black ink line (heavier under: the light from above), broken hairlines just outside it, freckles, a few white
specks, hatching in the shadows. Each part is rendered at SS times the canvas, then scaled to the game's size.
Parts: the body (its fin along the back; its tail end faded, over the tail), the tail (one shape, its fins, cut in
three), the head (its back faded under the gills; a cheek over the mouth's corner), the jaw (a real lower jaw: lip,
chin, pale throat), the mouth's inside (sal_parts.mouth_inside), the eye (sal_parts.eye_states, from the head drawn
with its eye), the legs (a round thigh / shoulder about the joint, the leg, a foot, toes, claws). The gills and the
effects as sal_parts.py has them.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import axolotl as AX  # noqa: E402
import cutout as C  # noqa: E402
import sal_parts as P  # noqa: E402

SS = 2                         # (render pixels a canvas pixel)
INK = (22, 14, 16)
# (DST's mobs: dusty, low-saturation, high contrast - countershaded: a deeper back, lit sides, a dark underside)
SKIN_T, SKIN, SKIN_B = (170, 104, 116), (212, 148, 148), (118, 66, 84)
LIGHT, SHADE, DEEP = (228, 176, 168), (168, 104, 114), (110, 60, 78)
BELLY_T, BELLY_B = (222, 178, 164), (160, 108, 112)
BELLY, BELLY_SH = BELLY_T, BELLY_B
SPOT, SPOT2 = (138, 76, 92), (116, 62, 80)
FIN_T, FIN, FIN_B = (204, 138, 146), (180, 110, 124), (148, 82, 100)
FIN_ALPHA = 0.95
FIN_RAY, FIN_LINE = (96, 46, 62), (96, 46, 62)
CLAW = (238, 230, 214)
FANG = (244, 238, 224)
SOCKET, SOCKET_RIM = (34, 18, 26), (70, 38, 52)
GLOW = (255, 250, 236)
W_INK = 8.4                    # (the outline, canvas px)
FIN_EDGE = (168, 82, 102)

JOINTS = dict(P.JOINTS)
JOINTS.update({"leg_bn": (487, 480), "leg_fn": (776, 494), "tail": (430, 468)})

# --- the shapes (canvas pixels, y down; traced over the design) ----------------------------------------------------

TOP = [(4, 476), (60, 469), (120, 458), (200, 438), (280, 404), (350, 368), (420, 330), (480, 301), (560, 251),
       (620, 231), (700, 213), (780, 198), (860, 186), (940, 181)]          # (the back's line, tail tip to neck)
BODY = [(350, 368), (420, 330), (480, 301), (560, 251),    # (its back on the tail's line, TOP: they cross-fade)
        (620, 231), (700, 213), (780, 198), (860, 186), (940, 181),
        (1000, 187), (1052, 197), (1076, 262), (1082, 380), (1072, 478), (1046, 538), (1000, 553), (940, 567),
        (880, 586), (800, 606), (700, 616), (600, 610), (520, 593), (450, 581), (380, 579), (356, 545), (350, 450)]
BELLY_LINE = [(380, 548), (450, 552), (520, 562), (620, 577), (700, 581), (800, 572), (880, 553), (960, 530),
              (1040, 503), (1090, 480)]
TAIL = [(10, 478), (60, 469), (120, 458), (200, 438), (280, 404), (350, 368), (420, 330), (480, 301), (520, 290),
        (540, 360), (540, 470), (520, 579), (430, 579), (350, 575), (280, 574), (200, 565), (130, 549), (72, 518),
        (30, 492)]
TAIL_BELLY = [(30, 488), (80, 520), (140, 542), (220, 556), (300, 563), (420, 566), (540, 566)]
TAIL_BOT = [(10, 482), (30, 492), (72, 518), (130, 549), (200, 565), (280, 574)]


def fin_h(x):
    """the axolotl's fin over the back, its height: none behind the gills, rising down the back, along the tail"""
    return float(np.interp(x, [0, 30, 130, 300, 470, 640, 820], [8, 32, 46, 44, 30, 13, 0]))


def fin_bot_h(x):
    return float(np.interp(x, [0, 30, 120, 220, 300], [7, 24, 34, 20, 0]))


HEAD = [(938, 186), (1000, 188), (1060, 198), (1110, 214), (1152, 232), (1180, 246), (1206, 241), (1234, 254),
        (1250, 284), (1266, 326), (1280, 370), (1289, 410), (1286, 438), (1273, 452)] + \
    [p for p in reversed(P.MOUTH[1:-1])] + [(975, 447), (956, 449), (938, 440), (930, 400), (928, 330), (928, 240)]
HEAD_FADE = (928, 962)         # (its back edge, under the gills, faded into the neck: x from, to)
SMILE_BAND = [(985, 436), (1000, 444), (1040, 452), (1080, 458), (1120, 461), (1160, 460), (1200, 456),
              (1240, 448), (1272, 436)]
EYE, EYE_R = (1095, 372), 41
# (the jaw: its back end round about the mouth's corner, so it turns there without a gap)
JAW = [(975, 450)] + [(x, y + 2) for x, y in P.MOUTH[1:-3]] + [
    (1250, 465), (1262, 471), (1267, 484), (1259, 500), (1240, 514), (1200, 528), (1150, 539), (1100, 545),
    (1050, 547), (1010, 541), (984, 527), (966, 504), (961, 479), (965, 459)]
JAW_THROAT = [(996, 528), (1040, 536), (1100, 536), (1160, 529), (1215, 518), (1248, 503)]
LIP = (236, 124, 142)          # (the jaw's inner lip: shows as the mouth opens)
# (the legs, traced: the outline; toes (base, tip); the crease where the thigh goes over the leg; hatching
#  (where, angle, length, how many); the top faded into the body over [y0, y1], or not)
LEG_B = dict(
    outline=[(400, 440), (425, 408), (462, 394), (505, 393), (545, 402), (575, 425), (590, 460), (594, 505),
             (587, 545), (574, 570), (582, 595), (594, 620), (600, 646), (588, 662), (565, 672), (540, 680),
             (515, 686), (490, 686), (462, 680), (436, 670), (414, 656), (398, 636), (392, 610), (390, 585),
             (382, 556), (377, 520), (382, 478)],
    toes=[((566, 636), (600, 652)), ((546, 650), (574, 674)), ((522, 660), (544, 686)), ((496, 664), (512, 690))],
    crease=[(404, 528), (430, 548), (470, 563), (520, 568), (562, 560), (586, 545)],
    hatch=[((462, 612), 70, 34, 9), ((404, 486), 100, 36, 5)],
    fade=None)
LEG_F = dict(
    outline=[(745, 440), (780, 434), (815, 444), (836, 480), (834, 515), (838, 548), (848, 580), (864, 605),
             (886, 616), (908, 630), (922, 648), (918, 664), (900, 680), (872, 688), (842, 694), (812, 694),
             (786, 688), (760, 676), (736, 656), (718, 626), (708, 590), (706, 545), (711, 500), (722, 458)],
    toes=[((882, 650), (920, 664)), ((860, 664), (896, 684)), ((834, 672), (864, 692)), ((806, 674), (830, 696))],
    crease=[(845, 612), (866, 624), (880, 640)],
    hatch=[((728, 600), 112, 30, 6)],
    fade=(440, 505))


# --- the renderer --------------------------------------------------------------------------------------------------

def spline(pts, closed=True, n=10):
    """a Catmull-Rom curve through pts"""
    p = np.array(pts, float)
    if closed:
        p = np.concatenate([p[-1:], p, p[:2]])
    else:
        p = np.concatenate([p[:1], p, p[-1:]])
    out = []
    for i in range(1, len(p) - 2):
        a, b, c, d = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3))
    if not closed:
        out.append(p[-2])
    return np.array(out)


class Part:
    def __init__(self, box, seed=0):
        self.x0, self.y0, x1, y1 = box
        self.W, self.H = int((x1 - self.x0) * SS), int((y1 - self.y0) * SS)
        self.a = np.zeros((self.H, self.W, 4), np.float32)          # (premultiplied)
        self.rnd = np.random.default_rng(seed)

    def px(self, pts):
        return [((x - self.x0) * SS, (y - self.y0) * SS) for x, y in pts]

    def poly(self, pts, blur=0.6, smooth=True, closed=True):
        q = spline(pts, closed) if smooth else np.array(pts, float)
        m = Image.new("L", (self.W, self.H), 0)
        ImageDraw.Draw(m).polygon(self.px(q), fill=255)
        return ndimage.gaussian_filter(np.asarray(m).astype(np.float32) / 255, blur * SS)

    def ellipse(self, c, r, blur=0.6, rot=0.0):
        t = np.linspace(0, 2 * math.pi, 72, endpoint=False)
        ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = [(c[0] + r[0] * math.cos(u) * ca - r[1] * math.sin(u) * sa,
                c[1] + r[0] * math.cos(u) * sa + r[1] * math.sin(u) * ca) for u in t]
        return self.poly(pts, blur, smooth=False)

    def capsule(self, pts_w, blur=0.6):
        """a limb: round ends, its width along its points ((x, y), half width)"""
        m = Image.new("L", (self.W, self.H), 0)
        d = ImageDraw.Draw(m)
        for (p, w), (q, v) in zip(pts_w, pts_w[1:]):
            for t in np.linspace(0, 1, 12):
                c = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
                r = (w + (v - w) * t) * SS
                X, Y = self.px([c])[0]
                d.ellipse((X - r, Y - r, X + r, Y + r), fill=255)
        return ndimage.gaussian_filter(np.asarray(m).astype(np.float32) / 255, blur * SS)

    def stroke(self, pts, width, smooth=True, passes=3, jitter=0.35, taper=True):
        """a scratchy ink line (canvas px wide), its ends tapered"""
        q = spline(pts, closed=False, n=8) if smooth and len(pts) > 2 else np.array(pts, float)
        m = Image.new("L", (self.W, self.H), 0)
        d = ImageDraw.Draw(m)
        n = len(q)
        for k in range(passes):
            jq = q + self.rnd.normal(0, jitter, q.shape)
            for i in range(n - 1):
                f = i / max(1, n - 2)
                w = width * (math.sin(math.pi * min(1, max(0, f))) ** 0.5 if taper else 1.0)
                w *= (1.0 if k == 0 else self.rnd.uniform(0.35, 0.6))
                d.line(self.px([jq[i], jq[i + 1]]), fill=255, width=max(1, int(round(w * SS))))
        return ndimage.gaussian_filter(np.asarray(m).astype(np.float32) / 255, 0.5 * SS)

    def shift(self, m, dx, dy):
        return ndimage.shift(m, (dy * SS, dx * SS), order=1, mode="constant", cval=0.0)

    def noise(self, scale=10.0, seed=None):
        r = np.random.default_rng(self.rnd.integers(1 << 30) if seed is None else seed)
        n = ndimage.gaussian_filter(r.normal(0, 1, (self.H, self.W)).astype(np.float32), scale * SS)
        return n / (n.std() + 1e-6)

    def ink_ring(self, m, w=W_INK, heavy=(1.6, 5.0), hair=True):
        """the outline: the shape grown by w, more below and to the right (heavy), its width wavering; broken
        hairlines just outside it"""
        inside = m > 0.5
        d = ndimage.distance_transform_edt(~inside) / SS
        d2 = ndimage.distance_transform_edt(~(self.shift(m, *heavy) > 0.5)) / SS
        nz = self.noise(14)
        ww = w * (1 + 0.2 * nz)
        ink = np.clip((ww - np.minimum(d, d2 + 0.6)) * SS / 1.6 + 0.5, 0, 1)
        if hair:
            for off, thr in ((w + 2.4, 0.55), (w + 4.2, 1.1)):
                band = np.clip(1 - np.abs(d - off * (1 + 0.15 * self.noise(20))) * SS / 0.9, 0, 1)
                ink = np.maximum(ink, band * (self.noise(9) > thr))
        return np.maximum(ink, m)

    def paint(self, m, col, alpha=1.0):
        m = np.clip(m * alpha, 0, 1)[..., None]
        c = np.array(list(np.array(col, np.float32) / 255) + [1.0], np.float32)
        self.a = self.a * (1 - m) + c * m

    def rims(self, m, top=12, bot=16, light=LIGHT, shade=SHADE, deep=DEEP):
        """lit from above: a light rim along its top, a shade along its bottom, deeper at the very edge"""
        up = self.shift(m, 0, top)            # (the shape moved down: what is not under it is its top rim)
        self.paint(ndimage.gaussian_filter(m * (1 - up), 3 * SS), light, 0.75)
        dn = self.shift(m, 0, -bot)
        self.paint(ndimage.gaussian_filter(m * (1 - dn), 4 * SS) * m, shade, 0.85)
        dn2 = self.shift(m, 0, -bot * 0.4)
        self.paint(ndimage.gaussian_filter(m * (1 - dn2), 1.5 * SS) * m, deep, 0.6)

    def freckles(self, area, n, rmin=5, rmax=14, cols=(SPOT, SPOT2)):
        ys, xs = np.nonzero(area > 0.9)
        if not len(xs):
            return
        for _ in range(n):
            i = self.rnd.integers(len(xs))
            c = (xs[i] / SS + self.x0, ys[i] / SS + self.y0)
            r = self.rnd.uniform(rmin, rmax)
            e = self.ellipse(c, (r, r * self.rnd.uniform(0.7, 1.0)), blur=0.9, rot=self.rnd.uniform(0, 180))
            self.paint(e * area, cols[self.rnd.integers(len(cols))], self.rnd.uniform(0.6, 0.9))

    def specks(self, area, n):
        ys, xs = np.nonzero(area > 0.9)
        if not len(xs):
            return
        for _ in range(n):
            i = self.rnd.integers(len(xs))
            c = (xs[i] / SS + self.x0, ys[i] / SS + self.y0)
            r = self.rnd.uniform(0.8, 2.0)
            self.paint(self.ellipse(c, (r, r * 1.6), blur=0.4, rot=self.rnd.uniform(0, 180)), (255, 250, 246), 0.8)

    def hatch(self, area, n, ang, length, width=1.1, spacing=5.0, start=None):
        """parallel short strokes (an angle, degrees from +x, y down) where area is"""
        ys, xs = np.nonzero(area > 0.5)
        if not len(xs):
            return
        cx, cy = (start if start else (xs.mean() / SS + self.x0, ys.mean() / SS + self.y0))
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        for k in range(n):
            o = (k - n / 2) * spacing
            px_, py_ = cx - dy * o, cy + dx * o
            L = length * self.rnd.uniform(0.7, 1.15)
            bend = L * 0.12
            pts = [(px_ - dx * L / 2, py_ - dy * L / 2), (px_ - dy * bend, py_ + dx * bend),
                   (px_ + dx * L / 2, py_ + dy * L / 2)]
            self.paint(self.stroke(pts, width, passes=1, jitter=0.15) * area, INK, 0.7)

    def fade_x(self, x_from, x_to, keep=None):
        xs = (np.arange(self.W) / SS + self.x0)
        r = np.clip((xs - x_from) / (x_to - x_from), 0, 1)[None, :, None]
        if keep is not None:
            r = np.maximum(r, keep[..., None])
        self.a = self.a * r

    # --- DST's look --------------------------------------------------------------------------------------------

    def resample(self, poly, step=2.0, closed=True):
        q = np.asarray(poly, float)
        if closed:
            q = np.vstack([q, q[:1]])
        seg = np.diff(q, axis=0)
        cum = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
        s = np.arange(0, cum[-1], step)
        return np.stack([np.interp(s, cum, q[:, 0]), np.interp(s, cum, q[:, 1])], 1)

    def outward(self, P, union):
        """P's tangents and outward normals (the side away from union)"""
        T = np.gradient(P, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-6)
        N = np.stack([T[:, 1], -T[:, 0]], 1)
        probe = P + N * 4
        ix = np.clip(((probe[:, 0] - self.x0) * SS).astype(int), 0, self.W - 1)
        iy = np.clip(((probe[:, 1] - self.y0) * SS).astype(int), 0, self.H - 1)
        if (union[iy, ix] > 0.5).mean() > 0.5:
            N = -N
        return T, N

    def sketch(self, polys, union, w=W_INK, gate=None, passes=((1.0, 0.0), (0.55, 1.5), (0.4, -1.3)),
               weight=0.55):
        """DST's ink line: each contour stroked in pieces of random length, each tapered at both ends and running a
        little past its neighbours', in a few passes at slight offsets; heavier where the edge faces down (weight);
        only along union's own edge (no lines inside it where the pieces it is made of overlap); painted last, over
        the fill, astride the edge"""
        m = Image.new("L", (self.W, self.H), 0)
        d = ImageDraw.Draw(m)
        for poly in polys:
            P = self.resample(poly)
            if len(P) < 4:
                continue
            T, N = self.outward(P, union)
            wp = w * np.clip(0.95 + weight * N[:, 1], 0.8, 1.45)
            n = len(P)
            for scale, off in passes:
                i = int(self.rnd.integers(0, 12))
                while i < n:
                    ln = int(self.rnd.integers(22, 60))
                    a, b = max(0, i - int(self.rnd.integers(2, 6))), min(n, i + ln)
                    seg = P[a:b] + N[a:b] * (off + self.rnd.normal(0, 0.35))
                    if len(seg) >= 2:
                        over = self.rnd.uniform(1.5, 5.0)
                        seg = np.vstack([seg[0] - T[a] * over, seg, seg[-1] + T[b - 1] * over])
                        k = len(seg)
                        drift = np.cumsum(self.rnd.normal(0, 0.12, (k, 1)), 0) * N[np.clip(np.arange(a - 1, a - 1 + k),
                                                                                         0, n - 1)]
                        seg = seg + drift
                        for j in range(k - 1):
                            f = j / max(1, k - 2)
                            ww = wp[min(n - 1, a + j)] * scale * (math.sin(math.pi * f) ** 0.45)
                            if ww * SS >= 0.6:
                                d.line(self.px([seg[j], seg[j + 1]]), fill=255, width=max(1, int(round(ww * SS))))
                    i = b
        ink = ndimage.gaussian_filter(np.asarray(m).astype(np.float32) / 255, 0.45 * SS)
        inside = union > 0.5
        din = ndimage.distance_transform_edt(inside) / SS
        dout = ndimage.distance_transform_edt(~inside) / SS
        band = np.clip((w * 1.6 + 2 - np.maximum(din, dout)) / 2.0, 0, 1)
        ink = ink * band
        if gate is not None:
            ink = ink * gate
        return ink

    def flicks(self, poly, union, n, length=(6, 15), w=1.7, facing=0.25, area=None):
        """short tapered ink flicks in from the edge where it faces down (the shadow side), as DST's fur and
        creases"""
        P = self.resample(poly, 3.0)
        T, N = self.outward(P, union)
        idx = np.nonzero(N[:, 1] > facing)[0]
        if not len(idx):
            return np.zeros_like(union)
        m = Image.new("L", (self.W, self.H), 0)
        d = ImageDraw.Draw(m)
        for i in self.rnd.choice(idx, size=min(n, len(idx)), replace=False):
            L = self.rnd.uniform(*length)
            ang = math.radians(self.rnd.uniform(-28, 28))
            c, s = math.cos(ang), math.sin(ang)
            dv = -N[i]
            dv = np.array([c * dv[0] - s * dv[1], s * dv[0] + c * dv[1]])
            pts = [P[i] + dv * (L * t) + T[i] * (L * 0.15 * t * t) for t in np.linspace(0, 1, 6)]
            for j in range(5):
                ww = w * (1 - j / 5) ** 0.8
                d.line(self.px([pts[j], pts[j + 1]]), fill=255, width=max(1, int(round(ww * SS))))
        f = ndimage.gaussian_filter(np.asarray(m).astype(np.float32) / 255, 0.45 * SS) * (union > 0.5)
        return f * (area if area is not None else 1)

    def grad_fill(self, m, top, mid, bot, split=0.45):
        """filled lighter at its top, darker and warmer at its bottom (each column from the shape's own top to its
        bottom, smoothed along it)"""
        inside = m > 0.5
        anyc = inside.any(0)
        ti = np.where(anyc, inside.argmax(0), 0).astype(np.float32)
        bi = np.where(anyc, self.H - 1 - inside[::-1].argmax(0), self.H - 1).astype(np.float32)
        ti = ndimage.gaussian_filter1d(ti, 25 * SS, mode="nearest")
        bi = ndimage.gaussian_filter1d(bi, 25 * SS, mode="nearest")
        rows = np.arange(self.H, dtype=np.float32)[:, None]
        t = np.clip((rows - ti) / np.maximum(bi - ti, 1), 0, 1)[..., None]
        top, mid, bot = (np.array(c, np.float32) / 255 for c in (top, mid, bot))
        u1 = np.clip(t / split, 0, 1)
        u2 = np.clip((t - split) / (1 - split), 0, 1)
        col = np.where(t < split, top + (mid - top) * u1, mid + (bot - mid) * u2)
        mm = m[..., None]
        self.a = self.a * (1 - mm) + np.concatenate([col, np.ones_like(col[..., :1])], -1) * mm

    def mottle(self, m, amt=0.03):
        """the paint's unevenness: broad soft patches and a little fine grain"""
        f = 1 + amt * (0.8 * self.noise(9) + 0.35 * self.noise(1.6))
        self.a[..., :3] *= (1 + (f - 1) * m)[..., None]

    def blobs(self, area, n, rmin, rmax, cols, alpha=(0.55, 0.85)):
        """freckles: irregular soft blobs"""
        ys, xs = np.nonzero(area > 0.9)
        if not len(xs):
            return
        for _ in range(n):
            i = self.rnd.integers(len(xs))
            c = np.array((xs[i] / SS + self.x0, ys[i] / SS + self.y0))
            r = self.rnd.uniform(rmin, rmax)
            ph = self.rnd.uniform(0, 6.3, 3)
            th = np.linspace(0, 2 * math.pi, 40, endpoint=False)
            rr = r * (1 + 0.16 * np.sin(2 * th + ph[0]) + 0.1 * np.sin(3 * th + ph[1]) + 0.06 * np.sin(5 * th + ph[2]))
            sq = self.rnd.uniform(0.65, 1.0)
            pts = [(c[0] + q * math.cos(a), c[1] + q * sq * math.sin(a)) for q, a in zip(rr, th)]
            self.paint(self.poly(pts, blur=0.8, smooth=False) * area, cols[self.rnd.integers(len(cols))],
                       self.rnd.uniform(*alpha))

    def col_t(self, m):
        """each pixel's height in its column of m: 0 at the shape's top, 1 at its bottom (smoothed)"""
        inside = m > 0.5
        anyc = inside.any(0)
        ti = np.where(anyc, inside.argmax(0), 0).astype(np.float32)
        bi = np.where(anyc, self.H - 1 - inside[::-1].argmax(0), self.H - 1).astype(np.float32)
        ti = ndimage.gaussian_filter1d(ti, 25 * SS, mode="nearest")
        bi = ndimage.gaussian_filter1d(bi, 25 * SS, mode="nearest")
        rows = np.arange(self.H, dtype=np.float32)[:, None]
        return np.clip((rows - ti) / np.maximum(bi - ti, 1), 0, 1)

    def texture(self, m, n, length=(8, 18), ang=95.0, spread=12.0, w=1.1, low=0.5, edge=0.35, alpha=0.7):
        """short tapered hairline strokes (DST's hatching), placed where it is darker: toward the shape's bottom
        (low: from this height down they thicken) and near its edge; each a slight curve at ang (degrees, y down)"""
        t = self.col_t(m)
        din = ndimage.distance_transform_edt(m > 0.5) / SS
        dens = (m > 0.6) * (0.02 + np.clip((t - low) / (1 - low), 0, 1) ** 1.6 + edge * np.exp(-din / 10))
        flat = dens.ravel() / max(dens.sum(), 1e-6)
        idx = self.rnd.choice(flat.size, size=n, p=flat)
        ys, xs = np.divmod(idx, self.W)
        im = Image.new("L", (self.W, self.H), 0)
        d = ImageDraw.Draw(im)
        for x, y in zip(xs, ys):
            L = self.rnd.uniform(*length) * SS
            a_ = math.radians(ang + self.rnd.normal(0, spread))
            dx, dy = math.cos(a_), math.sin(a_)
            bend = self.rnd.uniform(-0.18, 0.18) * L
            pts = [(x + dx * L * u - dy * bend * u * (1 - u) * 4, y + dy * L * u + dx * bend * u * (1 - u) * 4)
                   for u in np.linspace(0, 1, 6)]
            for j in range(5):
                ww = w * SS * math.sin(math.pi * (j + 0.5) / 5) ** 0.6
                d.line([pts[j], pts[j + 1]], fill=255, width=max(1, int(round(ww))))
        tex = ndimage.gaussian_filter(np.asarray(im).astype(np.float32) / 255, 0.4 * SS) * (m > 0.5)
        self.paint(tex, INK, alpha)

    def sheen(self, m, alpha=0.55, depth=0.22):
        """smooth, wet skin: a soft light band along the shape's top, a fainter one under it - no strokes"""
        t = self.col_t(m)
        band = np.exp(-((t - 0.12) / 0.07) ** 2) * (m > 0.5)
        band = ndimage.gaussian_filter(band.astype(np.float32), 3 * SS) * m
        broken = np.clip(0.6 + 0.8 * self.noise(18), 0, 1)                  # (broken up, as a painted gloss)
        self.paint(band * broken, (250, 222, 216), alpha)
        lo = ndimage.gaussian_filter((np.exp(-((t - 0.3) / 0.12) ** 2) * (m > 0.5)).astype(np.float32), 5 * SS) * m
        self.paint(lo, (236, 190, 186), depth)

    def image(self, k):
        """scaled to the game's size (k: build px a canvas px): the image and its top left on the canvas"""
        img = C.unpremul(self.a)
        bb = img.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox()
        img = img.crop(bb)
        x0, y0 = self.x0 + bb[0] / SS, self.y0 + bb[1] / SS
        return C.scaled(img, img.width * k / SS), (x0, y0)


# --- the parts -----------------------------------------------------------------------------------------------------

def capsule_pts(b, t, rb, rt, n=16):
    """a toe's outline: round at both ends"""
    b, t = np.array(b, float), np.array(t, float)
    d = (t - b) / np.linalg.norm(t - b)
    nrm = np.array([-d[1], d[0]])
    a0 = math.atan2(nrm[1], nrm[0])
    pts = [t + rt * np.array([math.cos(a0 - u), math.sin(a0 - u)]) for u in np.linspace(0, math.pi, n)]
    pts += [b + rb * np.array([math.cos(a0 + math.pi - u), math.sin(a0 + math.pi - u)]) for u in np.linspace(0, math.pi, n)]
    return np.array(pts)


def capsule_outline(pts_w, n=14):
    """the outline of a tapering limb through its points ((x, y), half width): its two sides, round at both ends"""
    c = np.array([q for q, _ in pts_w], float)
    w = np.array([r for _, r in pts_w], float)
    d = np.gradient(c, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    left, right = c + nrm * w[:, None], c - nrm * w[:, None]
    a1 = math.atan2(nrm[-1, 1], nrm[-1, 0])
    cap1 = [c[-1] + w[-1] * np.array([math.cos(a1 - u), math.sin(a1 - u)]) for u in np.linspace(0, math.pi, n)]
    a0 = math.atan2(-nrm[0, 1], -nrm[0, 0])
    cap0 = [c[0] + w[0] * np.array([math.cos(a0 - u), math.sin(a0 - u)]) for u in np.linspace(0, math.pi, n)]
    return np.vstack([left, cap1, right[::-1], cap0])


def ramp_x(p, x0, x1):
    xs = np.arange(p.W) / SS + p.x0
    return np.broadcast_to(np.clip((xs - x0) / (x1 - x0), 0, 1)[None, :], (p.H, p.W))


def fin_pts(contour, h_fn, sign, overlap=10):
    """a fin along contour: out from it by h_fn(x) (sign -1: up), its edge gently scalloped (a function of x, so
    the body's and the tail's fins match where they overlap), back along it into the body"""
    q = spline(contour, closed=False, n=8)
    out = [(x, y + sign * h_fn(x) * (1 + 0.1 * math.sin(x * 0.045)) + sign * 2.2 * math.sin(x * 0.21) * (h_fn(x) > 6))
           for x, y in q]
    inner = [(x, y - sign * overlap) for x, y in q[::-1]]
    return out + inner, q


def draw_fin(p, body_m, contour, h_fn, sign, gate=None):
    pts, q = fin_pts(contour, h_fn, sign)
    fin = p.poly(pts, blur=0.7, smooth=False)
    vis = fin * (1 - body_m)
    if gate is not None:
        vis = vis * gate
    p.grad_fill(vis, FIN_T, FIN, FIN_B) if sign < 0 else p.grad_fill(vis, FIN_B, FIN, FIN_T)
    p.a = p.a * (1 - vis[..., None] * (1 - FIN_ALPHA))          # (a membrane: a little see-through)
    i = 3
    while i < len(q) - 2:                                          # (its rays, from the body out: uneven, faint)
        x, y = q[i]
        h = h_fn(x)
        if h > 9:
            ln = p.rnd.uniform(0.55, 0.85)
            ray = [(x, y), (x - h * 0.2, y + sign * h * ln * 0.6), (x - h * 0.34, y + sign * h * ln)]
            p.paint(p.stroke(ray, 1.6, passes=1, jitter=0.25) * vis, FIN_RAY, 0.7)
        i += int(p.rnd.integers(6, 11))
    edge = p.sketch([pts], fin, w=W_INK * 0.6, weight=0.2)
    edge = edge * (1 - body_m) * (gate if gate is not None else 1)
    p.paint(edge, INK)
    return fin


def draw_body():
    p = Part((330, 140, 1110, 640), seed=11)
    m = p.poly(BODY)
    rear = ramp_x(p, 362, 432)                                     # (over the tail: the tail's line shows there)
    draw_fin(p, m, [q for q in TOP if 400 <= q[0] <= 860], fin_h, -1, gate=ramp_x(p, 436, 476))
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B)
    belly = p.poly(BELLY_LINE + [(1100, 640), (330, 640)], blur=1.5) * m
    p.grad_fill(belly, BELLY_T, BELLY_T, BELLY_B, split=0.3)
    p.mottle(m)
    front = ramp_x(p, 440, 470)
    side = m * (1 - ndimage.gaussian_filter(belly, 6 * SS)) * (p.shift(m, 0, 18) > 0.5) * (p.shift(m, 0, -30) > 0.5)
    p.blobs(side * front * (np.arange(p.W)[None, :] / SS + p.x0 < 1000), 34, 6, 16, (SPOT, SPOT2))
    p.a = p.a * rear[..., None]                                    # (the fill only: its line comes in over the tail's)
    p.sheen(m * front)
    p.paint(p.stroke(BELLY_LINE[1:], 2.6, passes=2) * front, INK, 0.75)      # (the belly's edge)
    p.paint(p.flicks(BODY, m, 7, area=front), INK, 0.9)
    p.paint(p.flicks(BELLY_LINE[1:] + [(1100, 700), (330, 700)], belly, 3, length=(5, 10), w=1.3) * front, INK,
            0.7)
    p.paint(p.sketch([spline(BODY)], m, gate=ramp_x(p, 392, 432) * (np.arange(p.H)[:, None] * 0 + 1)), INK)
    return p


WAIST_X = 690                  # (the waist, JOINTS["body"]'s x: where the two halves meet - rig.py)
WAIST_Y = (210, 620)           # (the body's top and bottom there)
CAP_BULGE = 54                 # (how far a half's closed end bulges past the waist)


def closed_body(which):
    """the side's body as one half on its own - the other half turned to another view (rig.py: the game shows it then):
    cut at the waist with a round end (the front's bulging back over where the hips were, the back's forward), inked,
    shaded darker toward it as it turns away"""
    p = draw_body()
    xs = (np.arange(p.W) / SS + p.x0)[None, :]
    ys = (np.arange(p.H) / SS + p.y0)[:, None]
    y0, y1 = WAIST_Y
    yc, hh = (y0 + y1) / 2, (y1 - y0) / 2
    def bulge(y):           # (the front's: fuller low down - a haunch - none up at the back's line; the back half's
        u = np.clip((y - y0) / (y1 - y0), 0, 1)       # (the one the game uses, behind the face): round all over)
        if which == "rear":
            return CAP_BULGE * 1.1 * np.sqrt(np.clip(1 - (2 * u - 1) ** 2, 0, 1)) ** 0.8
        return CAP_BULGE * np.sin(np.pi * u) ** 0.7 * (0.45 + 0.55 * u)
    cap = bulge(ys)
    sgn = -1 if which == "front" else 1
    inside_d = -sgn * (xs - (WAIST_X + sgn * cap))           # (canvas px inside the kept side of the end)
    inside = np.clip(inside_d * SS / 1.2 + 0.5, 0, 1)
    m = p.poly(BODY)
    p.paint(np.clip(1 - inside_d / 90, 0, 1) ** 1.6 * m, SKIN_B, 0.55)        # (turning away: in shade)
    p.paint(np.clip(1 - np.abs(inside_d - 30) / 22, 0, 1) * m * np.clip((ys - yc + 60) / 120, 0, 1), DEEP, 0.18)
    p.a = p.a * inside[..., None]
    pts = [(WAIST_X + sgn * float(bulge(y)), y) for y in np.linspace(y0 + 4, y1 - 4, 26)]
    gate = np.clip((ys - (y0 + 0.28 * (y1 - y0))) / 70, 0, 1) if which == "front" else 1.0   # (the front's line
    #  fades out up toward the back's)
    p.paint(p.stroke(pts, W_INK * 0.8, passes=3) * m * gate, INK)
    return p


def draw_tail():
    p = Part((0, 60, 560, 820), seed=12)                   # (room for it bent)
    m = p.poly(TAIL)
    draw_fin(p, m, [q for q in TOP if q[0] <= 560], fin_h, -1)
    draw_fin(p, m, TAIL_BOT, fin_bot_h, 1)
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B)
    belly = p.poly(TAIL_BELLY + [(560, 640), (0, 640)], blur=1.2) * m
    p.grad_fill(belly, BELLY_T, BELLY_T, BELLY_B, split=0.3)
    p.mottle(m)
    side = m * (1 - ndimage.gaussian_filter(belly, 4 * SS)) * (p.shift(m, 0, 12) > 0.5) * (p.shift(m, 0, -20) > 0.5)
    p.blobs(side, 18, 4, 11, (SPOT, SPOT2))
    p.sheen(m)
    p.paint(p.stroke(TAIL_BELLY[:-1], 2.4, passes=2), INK, 0.75)
    p.paint(p.flicks(TAIL, m, 4), INK, 0.9)
    p.paint(p.sketch([spline(TAIL)], m), INK)
    return p


FANGS = [((1146, 468), 13, 30), ((1206, 465), 11, 24)]     # (on the upper lip: where, half width, length)


def draw_head(with_eye=False):
    p = Part((900, 150, 1320, 520), seed=13)
    m = p.poly(HEAD)
    gate = ramp_x(p, *HEAD_FADE)
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B, split=0.6)
    lip_sh = p.poly(SMILE_BAND + [(1290, 470), (960, 470)], blur=4) * m
    p.paint(lip_sh, BELLY_T, 0.35)
    p.mottle(m)
    socket = p.ellipse(EYE, (EYE_R * 0.9, EYE_R * 0.82), blur=2.5, rot=-8)
    p.paint(ndimage.gaussian_filter(socket, 5 * SS) * m, SOCKET_RIM, 0.55)       # (the eye's socket, sunken)
    area = m * (p.shift(m, 0, 14) > 0.5) * (1 - ndimage.gaussian_filter(socket, 8 * SS))
    p.blobs(area * (np.arange(p.W)[None, :] / SS + p.x0 > 985), 12, 4, 10, (SPOT, SPOT2))
    p.sheen(m * gate * (1 - socket))
    # (the nostril; the smile's long curl back past the eye - the brow is its own symbol: BROWS, by the mood)
    p.paint(p.ellipse((1240, 398), (7, 5.5), rot=-20), INK)
    p.paint(p.stroke([(1186, 252), (1205, 263), (1224, 262)], 2.4, passes=2), INK, 0.85)
    p.paint(p.stroke([(996, 428), (980, 442), (976, 456)], 4.4), INK)
    # (fangs: two white teeth over the lower lip)
    polys = []
    for (c, hw, ln) in FANGS:
        f = [(c[0] - hw, c[1] - 6), (c[0] + hw, c[1] - 6), (c[0] + hw * 0.6, c[1] + ln * 0.55),
             (c[0] - hw * 0.05, c[1] + ln), (c[0] - hw * 0.7, c[1] + ln * 0.5)]
        fm = p.poly(f, blur=0.5, smooth=False)
        p.paint(fm, FANG)
        p.paint(ndimage.gaussian_filter(fm * (1 - p.shift(fm, -3, 0)), 1.5 * SS) * fm, (196, 184, 170), 0.7)
        polys.append(np.array(f + f[:1], float))
        m = np.maximum(m, fm)
    p.paint(p.flicks(HEAD, m, 3, length=(5, 11), facing=0.5) * gate, INK, 0.8)
    p.paint(p.sketch([spline(HEAD)], m, gate=gate, weight=0.3), INK)
    p.paint(p.sketch(polys, m, w=W_INK * 0.45, weight=0.2), INK)
    p.a = p.a * gate[..., None]
    return p


BROWS = {
    "neutral": [(-48, -56), (-20, -70), (12, -73), (44, -60)],
    "angry": [(-48, -70), (-18, -72), (14, -58), (42, -38)],       # (low toward the nose: a scowl)
    "sad": [(-48, -44), (-18, -60), (14, -72), (42, -84)],         # (up toward the nose)
    "surprised": [(-46, -72), (-18, -94), (14, -98), (42, -84)],   # (high, arched)
    "happy": [(-48, -62), (-20, -82), (12, -84), (42, -68)],       # (raised, soft)
    "low": [(-48, -50), (-18, -58), (14, -60), (42, -52)],         # (resting low, sleepy)
}
BROW_OF = {"open": "neutral", "wide": "surprised", "half": "low", "angry": "angry", "sad": "sad", "closed": "low",
           "happy": "happy", "squeeze": "angry", "dead": "sad", "stern": "neutral"}


def brow_parts():
    """the brow's frames, one per mood: a heavy ink ridge about EYE (its pivot; x + toward the nose)"""
    cx, cy = EYE
    out = {}
    for i, (key, pts) in enumerate(BROWS.items()):
        q = Part((cx - 80, cy - 130, cx + 80, cy - 10), seed=60 + i)
        q.paint(q.stroke([(cx + x, cy + y) for x, y in pts], 10.5 if key == "angry" else 9.5, passes=3), INK)
        out[key] = q
    return out


def eye_parts():
    """the eye's frames: a dark socket - and the 'pupil' symbol, what looks about: a small glowing white eye in it,
    as Klei's beefalo and koalefant have"""
    R = EYE_R * 0.9
    cx, cy = EYE
    box = (cx - R * 1.8, cy - R * 1.8, cx + R * 1.8, cy + R * 1.8)

    def socket():
        q = Part(box, seed=16)
        e = q.ellipse(EYE, (R, R * 0.9), blur=1.2, rot=-8)
        q.paint(e, SOCKET)
        q.paint(q.ellipse((cx, cy + R * 0.3), (R * 0.75, R * 0.5), blur=4) * e, SOCKET_RIM, 0.6)
        return q, e

    def lidded(y0, y1):
        q, e = socket()
        lid = q.poly([(cx - R * 1.5, cy - R * 1.6), (cx + R * 1.5, cy - R * 1.6), (cx + R * 1.5, cy + y1 * R),
                      (cx - R * 1.5, cy + y0 * R)], blur=0.6, smooth=False) * ndimage.gaussian_filter(e, 0.8 * SS)
        q.paint(lid, SKIN)
        q.paint(q.stroke([(cx - R * 1.15, cy + y0 * R), (cx + R * 1.15, cy + y1 * R)], 4.6, passes=2, taper=False)
                * ndimage.gaussian_filter(e, 3 * SS), INK)
        q.paint(q.ellipse((cx + R * 0.15, cy + R * 0.25), (R * 0.26, R * 0.24), 0.8) * e * (1 - lid), GLOW, 0.9)
        return q

    def line(pts):
        q, e = socket()
        q.paint(e, SKIN_B, 0.75)
        q.paint(q.stroke(pts, 4.4, passes=2), INK)
        return q

    out = {"open": socket()[0], "wide": socket()[0], "half": lidded(-0.15, -0.15),
           "angry": lidded(-0.05, -0.62), "sad": lidded(-0.62, 0.05),
           "stern": lidded(-0.62, -0.22),             # (the front's rest: a heavy lid, low toward the middle)
           "closed": line([(cx - R * 0.9, cy - R * 0.05), (cx, cy + R * 0.35), (cx + R * 0.9, cy - R * 0.05)]),
           "happy": line([(cx - R * 0.9, cy + R * 0.3), (cx, cy - R * 0.32), (cx + R * 0.9, cy + R * 0.3)]),
           "squeeze": line([(cx - R * 0.6, cy - R * 0.55), (cx + R * 0.5, cy), (cx - R * 0.6, cy + R * 0.55)])}
    dd, e = socket()
    for a_, b_ in (((-0.55, -0.55), (0.55, 0.55)), ((-0.55, 0.55), (0.55, -0.55))):
        dd.paint(dd.stroke([(cx + a_[0] * R, cy + a_[1] * R), (cx + b_[0] * R, cy + b_[1] * R)], 4.0, passes=2),
                 (200, 190, 180))
    out["dead"] = dd
    g = Part(box, seed=19)
    g.paint(ndimage.gaussian_filter(g.ellipse((cx + R * 0.12, cy + R * 0.02), (R * 0.42, R * 0.4), 1), 3 * SS),
            (255, 236, 220), 0.45)                                  # (its glow)
    g.paint(g.ellipse((cx + R * 0.12, cy + R * 0.02), (R * 0.27, R * 0.28), 0.6), GLOW)
    return out, g


def draw_jaw():
    p = Part((930, 430, 1300, 570), seed=14)
    m = p.poly(JAW)
    p.grad_fill(m, SKIN, SKIN_B, DEEP, split=0.4)
    throat = p.poly(JAW_THROAT + [(1290, 570), (950, 570)], blur=4.0) * m
    p.grad_fill(throat, BELLY_T, BELLY_B, BELLY_B, split=0.5)
    p.mottle(m)
    p.sheen(m)
    lip = [(976, 453)] + [(x, y + 4) for x, y in P.MOUTH[1:-3]] + [(1250, 469), (1262, 474)]
    p.paint(p.stroke(lip, 2.6, passes=2) * m, INK, 0.85)
    p.paint(p.flicks(JAW, m, 3, length=(5, 10)), INK, 0.8)
    p.paint(p.sketch([spline(JAW)], m, w=W_INK * 0.9, weight=0.7), INK)    # (thin along its lip, heavy under)
    return p


def draw_leg(spec, seed):
    xs = [q[0] for q in spec["outline"]]
    ys = [q[1] for q in spec["outline"]]
    p = Part((min(xs) - 30, min(ys) - 30, max(xs) + 40, max(ys) + 40), seed=seed)
    m = p.poly(spec["outline"])
    polys = [spline(spec["outline"])]
    claw_polys = []
    toes = np.zeros_like(m)
    claws = np.zeros_like(m)
    for (b, t) in spec["toes"]:
        tp = capsule_pts(b, t, 12.5, 9.5)
        toes = np.maximum(toes, p.poly(tp, smooth=False))
        polys.append(tp)
        d = np.array(t, float) - np.array(b, float)
        d /= np.linalg.norm(d)
        n = np.array([-d[1], d[0]])
        tip = np.array(t) + d * 22 + np.array([0, 6])
        cp = [tuple(np.array(t) + n * 8.5 - d * 4), tuple(np.array(t) + d * 9 + n * 5), tuple(tip),
              tuple(np.array(t) + d * 7 - n * 7), tuple(np.array(t) - n * 8.5 - d * 4)]
        claws = np.maximum(claws, p.poly(cp, blur=0.5))
        claw_polys.append(spline(cp))
    leg = np.maximum(m, toes)
    allm = np.maximum(leg, claws)
    p.paint(claws, CLAW)
    p.grad_fill(leg, SKIN, SKIN, DEEP, split=0.35)                  # (darker down to the feet, as Klei's mobs)
    p.mottle(leg)
    p.sheen(leg)
    if spec["crease"]:
        p.paint(p.stroke(spec["crease"], 3.6, passes=2), INK)
        under = p.shift(p.poly(spec["crease"] + [(spec["crease"][-1][0], spec["crease"][0][1] - 200),
                                                 (spec["crease"][0][0], spec["crease"][0][1] - 200)]), 0, 4)
        p.paint(ndimage.gaussian_filter(leg * (1 - under), 4 * SS) * leg * (p.shift(m, 0, -40) > 0.5), SKIN_B, 0.35)
    for (b, t) in spec["toes"][1:]:                                # (the toes' partings)
        d = np.array(t, float) - np.array(b, float)
        p.paint(p.stroke([tuple(np.array(b) - d * 0.5), tuple(np.array(b) + d * 0.3)], 2.4, passes=2) * leg, INK)
    area = leg * (p.shift(leg, 0, 12) > 0.5) * (p.shift(leg, 0, -26) > 0.5) * (1 - toes)
    p.blobs(area, 7, 5, 12, (SPOT, SPOT2))
    p.paint(p.flicks(spec["outline"], m, 3, length=(6, 14)), INK, 0.9)
    gate = None
    if spec["fade"]:
        y0, y1 = spec["fade"]
        yy = np.arange(p.H) / SS + p.y0
        gate = np.broadcast_to((np.clip((yy - y0) / (y1 - y0), 0, 1) ** 1.3)[:, None], (p.H, p.W))
    p.paint(p.sketch(polys, leg, w=W_INK * 0.95), INK)
    p.paint(p.sketch(claw_polys, claws, w=W_INK * 0.4, weight=0.2, passes=((1.0, 0.0), (0.5, 0.8))) * (1 - leg), INK)
    if gate is not None:
        p.a = p.a * gate[..., None]
    return p


# --- the tail, bent: one drawing, warped to each of TAIL_N curvatures (the symbol's frames), so it has no pieces and
#     no seams; its root, under the body's back, never moves ---------------------------------------------------------

TAIL_ROOT = (430, 468)         # (where it hangs from: the body's joint; the bend starts BEND_FROM along it)
TAIL_TIP = (10, 482)
BEND_FROM = 40                 # (canvas px from the root: behind the body's back, where it fades over the tail)
TAIL_N = 17                    # (frames: the curvatures, -TAIL_BEND .. +TAIL_BEND at the tip)
TAIL_BEND = 40.0               # (degrees: the tip turned this far, up +, at the last frame)


def bend_map(px_, py_, deg, root=TAIL_ROOT, tip=TAIL_TIP, bend_from=BEND_FROM):
    """the bent tail's point for each rest point (canvas coords, y down): along the tail from the root its
    direction turns more and more (as s ** 1.5) until the tip is turned deg (up +)"""
    R, T = np.array(root, float), np.array(tip, float)
    L = np.linalg.norm(T - R)
    a = (T - R) / L
    n = np.array([-a[1], a[0]])                                   # (up, for a tail pointing left)
    if n[1] > 0:
        n = -n
    Ls = L - bend_from
    u = (px_ - R[0]) * a[0] + (py_ - R[1]) * a[1]
    v = (px_ - R[0]) * n[0] + (py_ - R[1]) * n[1]
    s = u - bend_from
    ss = np.linspace(0, Ls * 1.6, 1200)
    th = math.radians(deg) * (ss / Ls) ** 1.5
    ds = ss[1] - ss[0]
    cx = np.concatenate([[0], np.cumsum(np.cos(th[:-1]) * ds)])
    cy = np.concatenate([[0], np.cumsum(np.sin(th[:-1]) * ds)])
    sp = np.clip(s, 0, ss[-1])
    t_ = np.interp(sp, ss, th)
    along, side = np.interp(sp, ss, cx), np.interp(sp, ss, cy)
    B = R + a * bend_from
    # (the spine's point, then out from it by v along its turned normal)
    bx = B[0] + a[0] * along + n[0] * side
    by = B[1] + a[1] * along + n[1] * side
    nx = n[0] * np.cos(t_) - a[0] * np.sin(t_)
    ny = n[1] * np.cos(t_) - a[1] * np.sin(t_)
    qx, qy = bx + v * nx, by + v * ny
    bent = s > 0
    return np.where(bent, qx, px_), np.where(bent, qy, py_)


def bent(part, deg, root=TAIL_ROOT, tip=TAIL_TIP, bend_from=BEND_FROM):
    """a copy of part, its pixels moved by bend_map (inverted by fixed-point steps: each output point's source)"""
    q = Part.__new__(Part)
    q.__dict__.update(part.__dict__)
    if abs(deg) < 1e-6:
        q.a = part.a.copy()
        return q
    H, W = part.H, part.W
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ox, oy = xx / SS + part.x0, yy / SS + part.y0               # (the output's points, canvas coords)
    sx, sy = ox.copy(), oy.copy()
    for _ in range(40):
        fx_, fy_ = bend_map(sx, sy, deg, root, tip, bend_from)
        sx, sy = sx + (ox - fx_), sy + (oy - fy_)
    fx_, fy_ = bend_map(sx, sy, deg, root, tip, bend_from)
    ok = (np.hypot(fx_ - ox, fy_ - oy) < 0.5).astype(np.float32)   # (only where the steps found its source: no ghosts)
    cols = (sx - part.x0) * SS
    rows = (sy - part.y0) * SS
    q.a = np.stack([ndimage.map_coordinates(part.a[..., c], [rows, cols], order=1, mode="constant", cval=0.0)
                    for c in range(4)], -1).astype(np.float32) * ok[..., None]
    return q


# --- out -----------------------------------------------------------------------------------------------------------

def main(G):
    hero = P.full(G, "clean531")
    bb = hero.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    k = P.LENGTH / (bb[2] - bb[0])
    ox, ground = JOINTS["body"][0], P.GROUND_Y

    def world(p):
        return [(p[0] - ox) * k, (ground - p[1]) * k]

    def put(sym, key, part, joint):
        img, (x0, y0) = part.image(k) if isinstance(part, Part) else part
        jx, jy = JOINTS[joint] if isinstance(joint, str) else joint
        P.save(sym, key, img, ((jx - x0) * k, (jy - y0) * k), skin=False)
        return img

    for d in os.listdir(P.OUT):                                    # (a clean set)
        if os.path.isdir(os.path.join(P.OUT, d)):
            for f in os.listdir(os.path.join(P.OUT, d)):
                os.remove(os.path.join(P.OUT, d, f))
    P.PARTS.clear()
    joints = {j: world(p) for j, p in JOINTS.items() if not j.startswith("gill")}
    put("body", "rest", draw_body(), "body")
    put("body", "front_closed", closed_body("front"), "body")
    put("body", "rear_closed", closed_body("rear"), "body")
    for sym, j, spec, seed in (("leg_front", "leg_fn", LEG_F, 21), ("leg_back", "leg_bn", LEG_B, 22)):
        sc = put(sym, "near", draw_leg(spec, seed), j)
        fa = np.asarray(sc).astype(np.float32)
        fa[..., :3] *= np.array([0.74, 0.6, 0.66], np.float32)          # (in shadow: a deeper rose)
        rows = np.arange(fa.shape[0])[:, None]
        fa[..., 3] *= np.clip((rows - fa.shape[0] * 0.3) / (fa.shape[0] * 0.2), 0, 1)
        P.save(sym, "far", Image.fromarray(fa.astype(np.uint8), "RGBA"),
               (P.PARTS[sym]["near"][2] * sc.width, P.PARTS[sym]["near"][3] * sc.height), skin=False)
    for far, (near, (dx, dy)) in P.FAR.items():
        jx, jy = JOINTS[near]
        joints[far] = world((jx + dx, jy + dy))
    # --- the tail: one drawing, bent to each curvature (its frames), hung from its root under the body's back ---
    tail = draw_tail()
    quick = os.environ.get("SAL_QUICK")
    for i, c in enumerate(np.linspace(-1, 1, TAIL_N)):
        if quick and i != TAIL_N // 2:
            c = 0.0
        img, (x0, y0) = bent(tail, c * TAIL_BEND).image(k)
        P.save("tail", str(i), img, ((TAIL_ROOT[0] - x0) * k, (TAIL_ROOT[1] - y0) * k), skin=False)
    P.PARTS["_tail"] = {"n": TAIL_N, "bend": TAIL_BEND}
    # --- the head, its eye's frames (cut from it drawn with its eye), the jaw, the mouth's inside ---
    put("head", "shut", draw_head(), "head")
    eyes, glow = eye_parts()
    for key, part in eyes.items():
        put("eye", key, part, EYE)
    put("pupil", "0", glow, EYE)
    for key, part in brow_parts().items():
        put("brow", key, part, EYE)
    P.PARTS["_brow_of"] = BROW_OF
    put("jaw", "0", draw_jaw(), "jaw")
    inside = P.mouth_inside(hero.size, JOINTS["jaw"])
    iimg, ioff = C.largest(inside, with_offset=True)
    P.save("mouth", "0", C.scaled(iimg, iimg.width * k),
           ((JOINTS["jaw"][0] - ioff[0]) * k, (JOINTS["jaw"][1] - ioff[1]) * k), skin=False)
    # --- the gills and the effects: as sal_parts.py has them ---
    have = lambda n: os.path.exists(os.path.join(G, n + ".png"))  # noqa: E731
    if not have("gill_axo"):
        AX.draw_gill(os.path.join(G, "gill_axo.png"))
    gc, _, _ = P.load(G, "gill_axo")
    ga = np.asarray(gc).astype(np.float32)                         # (muted, as DST's colours are)
    grey = ga[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    ga[..., :3] = (ga[..., :3] * 0.7 + grey[..., None] * 0.3) * 0.78
    gc = Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8), "RGBA")
    gill = C.scaled(gc, gc.width * P.GILL_H / gc.height)
    a = np.asarray(gill)[..., 3] > 128
    ys, xs = np.nonzero(a)
    base = (xs[ys >= ys.max() - 4].mean(), ys.max() - 4)
    P.save("gill", "near", gill, base, skin=False)
    P.save("gill", "far", P.darker(gill, 0.62), base, skin=False)
    for g, q in JOINTS.items():
        if g.startswith("gill"):
            joints[g] = world(q)
    P.PARTS["_gills"] = P.GILL_ANGLES
    P.PARTS["_jaw_open"] = P.JAW_OPEN
    for sym, w in (("heart", 44), ("note", 36), ("zzz", 80), ("vein", 100), ("bubble", 34)):
        p_ = os.path.join(G, f"fx_{sym}.png")
        if os.path.exists(p_):
            src = Image.open(p_)
            src = src.convert("RGBA") if src.mode == "RGBA" else C.cutout(src)
            im = C.scaled(src, w)
            P.save(sym, "0", im, (im.width / 2, im.height / 2), skin=False)
    # --- the front and the back (tools/gen/sal_views.py): the four-faced game's down and up views ---
    if os.environ.get("SAL_QUICK") and not os.environ.get("SAL_VIEWS"):    # (a concept: the side only)
        P.PARTS["_joints"] = joints
        json.dump(P.PARTS, open(os.path.join(P.OUT, "parts.json"), "w"), indent=1)
        return
    import sal_views as SV

    def vsave(sym, key, part, joint):
        img, (x0, y0) = part.image(k)
        P.save(sym, key, img, ((joint[0] - x0) * k, (joint[1] - y0) * k), skin=False)
    views = SV.draw(k, vsave, quick=bool(os.environ.get("SAL_QUICK")))
    P.PARTS["_views"] = {
        v: {"J": {j: [(q[0] - SV.MID) * k, (ground - q[1]) * k] for j, q in views[v].items()},
            "gill_rest": list(SV.F_GILL_REST if v == "front" else SV.B_GILL_REST), "eye_k": SV.F_EYE_K,
            "jaw_drop": SV.F_JAW_DROP * k} for v in views}
    P.PARTS["_joints"] = joints
    json.dump(P.PARTS, open(os.path.join(P.OUT, "parts.json"), "w"), indent=1)
    print("k", round(k, 3), "parts:", {s: list(v) for s, v in P.PARTS.items() if not s.startswith("_")})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(P.ROOT, "art", "source"))
