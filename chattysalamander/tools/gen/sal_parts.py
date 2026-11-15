"""(Superseded for the parts by tools/gen/sal_vector.py, 2026-11-05: it draws every part as its own vector shape, and
uses this file's helpers - the eye's frames, the mouth's inside, the joints. This cut them out of the painted design.)

The salamander's parts, from the generated drawings (tools/gen/sal_jobs.py made them with Qwen-Image-Edit on the
local ComfyUI: a design drawing, then each part kept alone from it, in place) to the PNGs the rig builds from:
art/parts/<symbol>/<key>.png and art/parts/parts.json ({symbol: {key: [w, h, pivot x share, pivot y share]}}: the
pivot, from the top left, is the joint the part turns about; "_joints": where each joint is at rest, in build pixels
from the ground below the body's middle, y up).

    python tools/gen/sal_parts.py [the generated PNGs' folder: art/source]

All the drawings are on one canvas (the design's): JOINTS are on it, in its pixels. Scaled so that the salamander
is LENGTH build pixels long (a person, Wilson, is 375 tall; a beefalo 780 long). The far legs: the near ones,
darker; the tail cut in three overlapping pieces (each feathered at its tip end, under the one before); the eye cut
from the head (its ring, its white, its pupil) and drawn in its states, lids of the salamander's skin.

An axolotl (tools/gen/axolotl.py): every skin part recoloured pink as it is saved (the cutting is done on the design's
own colours: the eye's white is found by its brightness); the gills drawn there (art/source/gill_axo.png), three a
side from the back of the head, fanned back over the neck's seam. The legs cut along their own ink outlines (LEGS:
their round thigh / shoulder about the joint, so a leg turning stays whole), soft only where they lie over the body.
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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "art", "parts")
LENGTH = 900

# (the design's canvas, 1328 x 800: where the joints are)
JOINTS = {
    "body": (690, 440),
    "head": (1010, 415),
    "eye": (1095, 372),
    "jaw": (978, 452),
    "leg_fn": (785, 488), "leg_bn": (487, 486),
    "tail1": (425, 468), "tail2": (290, 480), "tail3": (160, 495),
    "gill_n0": (1004, 300), "gill_n1": (996, 346), "gill_n2": (990, 392),
    "gill_f0": (984, 278), "gill_f1": (972, 318), "gill_f2": (962, 358),
}
FAR = {"leg_ff": ("leg_fn", (125, -28)), "leg_bf": ("leg_bn", (110, -24))}   # (behind, a little further on)
GILL_ANGLES = {"0": 28, "1": 68, "2": 106}        # (the stalks' rest angles: fanned up and back, + anticlockwise)
GILL_H = 150                  # (a gill's height, build pixels)
SKIN = {"body", "leg_front", "leg_back", "tail1", "tail2", "tail3", "head", "jaw", "eye"}   # (recoloured pink)
NECK_X = 1060                 # (the body: the legless drawing before this, the headless one after)
GROUND_Y = 700                # (the feet, on the design's canvas)
TAIL_X = (425, 470)           # (the body fades out over the tail's root between these)
INK = (22, 20, 18)
PARTS = {}


def load(G, name, keep_largest=True):
    """cut out, the biggest piece only; with where its top left is on the picture, and the picture's size"""
    p = os.path.join(G, name + ".png")
    im = Image.open(p).convert("RGB")
    cut, (x0, y0) = C.cutout(im, with_offset=True)
    if keep_largest:
        cut, (dx, dy) = C.largest(cut, with_offset=True)
        x0, y0 = x0 + dx, y0 + dy
    return cut, (x0, y0), im.size


def save(sym, key, img, pivot, skin=None):
    d = os.path.join(OUT, sym)
    os.makedirs(d, exist_ok=True)
    if sym in SKIN if skin is None else skin:
        img = AX.recolor(img)
    img.save(os.path.join(d, f"{key}.png"))
    PARTS.setdefault(sym, {})[key] = [img.width, img.height, pivot[0] / img.width, pivot[1] / img.height]


def darker(img, k=0.62):
    a = np.asarray(img).astype(np.float32)
    a[..., :3] *= k
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def feather_left(img, x_from, x_to):
    """alpha ramps from 0 at x_from to 1 at x_to (pixels of img)"""
    a = np.asarray(img).astype(np.float32)
    xs = np.arange(a.shape[1])
    ramp = np.clip((xs - x_from) / max(1, x_to - x_from), 0, 1)
    a[..., 3] *= ramp[None, :]
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def ink_stroke(size, pts, width, seed=0, passes=4):
    rnd = np.random.default_rng(abs(int(seed)))
    k = 4
    im = Image.new("L", (size[0] * k, size[1] * k), 0)
    d = ImageDraw.Draw(im)
    P = np.array(pts, float) * k
    d.line([tuple(p) for p in P], fill=255, width=int(width * k * 0.75), joint="curve")
    for _ in range(passes):
        Jt = P + rnd.normal(0, width * k * 0.18, P.shape)
        d.line([tuple(p) for p in Jt], fill=255, width=max(1, int(width * k * rnd.uniform(0.18, 0.35))), joint="curve")
    for p in (P[0], P[-1]):
        r = width * k * 0.36
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=255)
    al = np.asarray(im.resize(size, Image.BOX)).astype(np.float32) / 255
    out = np.zeros((size[1], size[0], 4), np.float32)
    out[..., :3] = np.array(INK) / 255
    out[..., 3] = al
    return out


def over(dst, src):
    sa, da = src[..., 3:4], dst[..., 3:4]
    oa = sa + da * (1 - sa)
    rgb = (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-4)
    return np.concatenate([rgb, oa], -1)


def to_img(a):
    return C.unpremul(np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], -1))


def eye_states(head, centre, lid):
    """the eye cut from the head drawing (its white joined to centre, its ring of ink, its pupil): {key: image},
    pupil image, and the head with the eye's place painted over in skin (lid colour)"""
    a = np.asarray(head).astype(np.float32) / 255
    h, w = a.shape[:2]
    cx, cy = centre
    white = (a[..., :3].min(-1) > 0.68) & (a[..., 3] > 0.5)
    dark = (a[..., :3].max(-1) < 0.3) & (a[..., 3] > 0.5)
    lab, _ = ndimage.label(white | dark)
    # (the white: the light component nearest the centre)
    wl, _ = ndimage.label(white)
    yy, xx = np.mgrid[0:h, 0:w]
    near = (xx - cx) ** 2 + (yy - cy) ** 2 < 60 ** 2
    ids = [i for i in np.unique(wl[near & white]) if i]
    inner = np.isin(wl, ids)
    ys, xs = np.nonzero(inner)
    cx, cy = xs.mean() + 0.5, ys.mean() + 0.5
    Rw = math.sqrt(inner.sum() / math.pi)                     # (the white's radius)
    inner_f = ndimage.binary_fill_holes(inner)                # (the pupil, inside the white)
    pupil_m = inner_f & ~inner
    ring_m = dark & ((xx - cx) ** 2 + (yy - cy) ** 2 < (Rw * 1.45) ** 2) & ~inner_f
    ring_m = ndimage.binary_closing(ring_m, iterations=2) & ~inner_f
    disc = ring_m | inner_f
    X, Y = xx + 0.5 - cx, cy - (yy + 0.5)
    rgba = a.copy()
    ring = np.zeros_like(a)
    ring[ring_m] = a[ring_m]
    ring[..., 3] = ring_m.astype(np.float32) * a[..., 3]
    base = np.zeros_like(a)
    base[inner_f] = (1, 1, 1, 1)
    pup = np.zeros_like(a)
    pup[pupil_m] = a[pupil_m]
    pup[..., 3] = pupil_m.astype(np.float32)
    lid_rgb = np.array(lid) / 255
    out = {}
    R = Rw

    def lidded(lo, hi, pdy=None):
        img = base.copy()
        if pdy is not None:
            sh = np.roll(pup, int(round(-pdy * R)), axis=0)
            sh[..., 3] *= inner_f
            img = over(img, sh)
        line = (lo + (X / R + 1) / 2 * (hi - lo)) * R
        cover = inner_f & (Y > line)
        u = np.clip((Y - line) / (R * 1.4), 0, 1)[..., None]
        col = lid_rgb * (1.08 - 0.3 * u)
        img = over(img, np.concatenate([np.clip(col, 0, 1), cover[..., None].astype(np.float32)], -1))
        if lo > -1.0 or hi > -1.0:
            pts = [(cx + x, cy - (lo + (x / R + 1) / 2 * (hi - lo)) * R) for x in np.linspace(-R, R, 10)]
            img = over(img, ink_stroke((w, h), pts, R * 0.2, seed=int(lo * 10 + hi * 100)))
        return img

    def shut(curve):
        """the eye shut: the lid all over it, its edge a line (curve: + a smile, - an arch)"""
        img = base.copy()
        img = over(img, np.concatenate([np.broadcast_to(lid_rgb, a[..., :3].shape),
                                        inner_f[..., None].astype(np.float32)], -1))
        pts = [(cx + x, cy + 0.1 * R - curve * R * (1 - (x / R) ** 2)) for x in np.linspace(-R * 0.95, R * 0.95, 12)]
        return over(img, ink_stroke((w, h), pts, R * 0.2, seed=int(curve * 10) + 5))

    out["open"] = over(base, ring)
    out["wide"] = out["open"]
    out["half"] = over(lidded(-0.1, -0.1, -0.35), ring)
    out["angry"] = over(lidded(0.85, -0.35, -0.4), ring)        # (for a right-facing eye: low at its front)
    out["sad"] = over(lidded(-0.35, 0.85, -0.45), ring)
    out["closed"] = over(shut(0.35), ring)
    out["happy"] = over(shut(-0.45), ring)
    sq = base.copy()
    sq = over(sq, np.concatenate([np.broadcast_to(lid_rgb, a[..., :3].shape), inner_f[..., None].astype(np.float32)], -1))
    sq = over(sq, ink_stroke((w, h), [(cx - R * 0.7, cy - R * 0.55), (cx + R * 0.45, cy), (cx - R * 0.7, cy + R * 0.55)],
                             R * 0.22, seed=9))
    out["squeeze"] = over(sq, ring)
    dd = over(base, ring)
    dd = over(dd, ink_stroke((w, h), [(cx - R * 0.6, cy - R * 0.6), (cx + R * 0.6, cy + R * 0.6)], R * 0.22, seed=3))
    dd = over(dd, ink_stroke((w, h), [(cx - R * 0.6, cy + R * 0.6), (cx + R * 0.6, cy - R * 0.6)], R * 0.22, seed=4))
    out["dead"] = dd
    # (the head with the eye's place filled with skin: the eye's frames cover it)
    hd = rgba.copy()
    grow = ndimage.binary_dilation(disc, iterations=2)
    hd[grow, :3] = lid_rgb
    box = (int(cx - Rw * 1.6), int(cy - Rw * 1.6), int(cx + Rw * 1.6) + 1, int(cy + Rw * 1.6) + 1)
    imgs = {k: to_img(v).crop(box) for k, v in out.items()}
    wide = imgs["wide"]
    imgs["wide"] = wide.resize((round(wide.width * 1.12), round(wide.height * 1.12)), Image.LANCZOS)
    pup_img = to_img(pup).crop(box)
    pbb = pup_img.getbbox()
    return imgs, pup_img.crop(pbb) if pbb else pup_img, to_img(hd), (cx - box[0], cy - box[1])


# (masks on the design's canvas: a generous outline round each part; the joint's side feathered - (x0, x1): alpha
#  0 at x0 rising to 1 at x1, along x; ("y", y0, y1) the same along y)
MASKS = {
    "head": ([(966, 150), (1330, 150), (1330, 560), (966, 560)], ("x", 968, 998)),
    "tail": ([(0, 300), (495, 260), (495, 600), (0, 600)], None),
}
# (each near leg, traced just outside its own ink outline on the design: the back leg's round thigh whole, the front
#  leg's shoulder rounded about its joint; below the body they stop at the leg's own edge, not taking in the belly,
#  the shadow under it or the far legs)
LEGS = {
    "leg_bn": [(386, 428), (405, 400), (440, 388), (480, 384), (522, 389), (560, 405), (585, 438), (597, 480),
               (596, 522), (583, 556), (572, 578), (580, 600), (592, 622), (597, 652), (582, 694), (540, 704),
               (470, 699), (406, 684), (386, 652), (389, 612), (378, 580), (372, 540), (373, 480)],
    "leg_fn": [(690, 480), (705, 452), (740, 436), (785, 432), (828, 440), (858, 462), (870, 492), (868, 525),
               (866, 560), (870, 592), (888, 618), (910, 638), (921, 662), (915, 700), (840, 707), (770, 703),
               (742, 692), (722, 668), (700, 642), (692, 600), (686, 540)],
}
LEG_SOFT = 5.0                # (how soft a leg's edge is where it lies over the body: px, a blur)


def leg_mask(size, poly, body, img):
    """a leg's alpha on the canvas: crisp along its outline where it is its own silhouette (below the body), soft
    where it lies over the body (its thigh / shoulder: a seam on matching skin), the soft edge just outside it - and
    skin only there: the body's own ink lines (the belly's outline, hatching) left to the body, or they would smear
    as the leg moves"""
    crisp = poly_mask(size, poly, 1.0)
    grown = ndimage.binary_dilation(crisp > 0.5, iterations=int(LEG_SOFT))
    soft = ndimage.gaussian_filter(grown.astype(np.float32), LEG_SOFT)
    rgb = np.asarray(img).astype(np.float32)[..., :3] / 255
    skin = np.clip((rgb @ np.array([0.299, 0.587, 0.114], np.float32) - 0.22) / 0.15, 0, 1)
    skin = ndimage.minimum_filter(skin, 3)                    # (and the ink's anti-aliased edge with it)
    margin = crisp + np.maximum(soft - crisp, 0) * skin
    inner = np.minimum(soft, crisp) + (crisp - np.minimum(soft, crisp)) * (1 - skin)   # (its own ink: kept whole)
    blend = np.where(soft > crisp, margin, inner)
    over_body = ndimage.gaussian_filter(ndimage.binary_erosion(body, iterations=4).astype(np.float32), 2.0)
    return blend * over_body + crisp * (1 - over_body)


def cut(img, alpha):
    """img with its alpha times alpha (canvas-sized), cropped: and where the crop's top left was"""
    arr = np.asarray(img).astype(np.float32)
    arr[..., 3] *= alpha
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    bb = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return out.crop(bb), bb[:2]


def full(G, name):
    """the drawing cut out, on its whole canvas"""
    im = Image.open(os.path.join(G, name + ".png")).convert("RGB")
    cut, off = C.cutout(im, with_offset=True)
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    canvas.paste(cut, off)
    return canvas


def masked(img, mask, extra=None):
    poly, fe = mask
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    a = np.asarray(m).astype(np.float32) / 255
    if fe:
        axis, f0, f1 = fe
        n = img.size[0] if axis == "x" else img.size[1]
        ramp = np.clip((np.arange(n) - f0) / (f1 - f0), 0, 1)
        a *= ramp[None, :] if axis == "x" else ramp[:, None]
    if extra is not None:
        a = a * extra
    arr = np.asarray(img).astype(np.float32)
    arr[..., 3] *= a
    out = Image.fromarray(arr.astype(np.uint8), "RGBA")
    bb = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return out.crop(bb), bb[:2]


# (the mouth: its line on the design (the upper lip's ink), the jaw below it turning about its corner)
MOUTH = [(975, 447), (1000, 456), (1040, 466), (1080, 473), (1120, 476), (1160, 475), (1200, 471), (1240, 463),
         (1272, 455), (1300, 440)]
JAW_OPEN = 20                 # (the mouth's inside is drawn for the jaw down this far, degrees)
# (the jaw: below the lip line, back to the mouth's corner, down past the chin's outline; its back edge a line out
#  from the corner, so the jaw turning about the corner slides along the throat, leaving no hole)
JAW_POLY = [(972, 449)] + [(x, y + 3) for x, y in MOUTH[1:]] + [(1314, 440), (1314, 545), (1150, 545), (1040, 545),
                                                                 (1000, 530), (984, 500)]
CHEEK = ((976, 452), 20)      # (the head keeps a round cheek over the mouth's corner: the jaw turns under it)


def poly_mask(size, poly, blur=1.0):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    return ndimage.gaussian_filter(np.asarray(m).astype(np.float32) / 255, blur)


def disc_mask(size, centre, r, blur=1.5):
    yy, xx = np.mgrid[0:size[1], 0:size[0]]
    m = ((xx + 0.5 - centre[0]) ** 2 + (yy + 0.5 - centre[1]) ** 2 < r * r).astype(np.float32)
    return ndimage.gaussian_filter(m, blur)


def mouth_inside(size, hinge):
    """the inside of the mouth (canvas pixels), between the lip line and the jaw's lip opened JAW_OPEN: a throat
    dark at its back, lighter toward the front, and a tongue lying on the jaw's floor (turned with it)"""
    th = math.radians(JAW_OPEN)

    def turn(x, y, a=th):
        return (hinge[0] + (x - hinge[0]) * math.cos(a) - (y - hinge[1]) * math.sin(a),
                hinge[1] + (x - hinge[0]) * math.sin(a) + (y - hinge[1]) * math.cos(a))
    lip = [p for p in MOUTH if p[0] <= 1262]          # (not out to the snout's tip: the inside ends behind it)
    rot = [turn(x, y) for x, y in lip]
    poly = [(x, y - 5) for x, y in lip] + [(x, y + 5) for x, y in reversed(rot)]
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # (colour: from the throat (back, near the corner) to the front, and darker up under the palate)
    u = np.clip((xx - hinge[0]) / (1250 - hinge[0]), 0, 1)
    back, front = np.array([34, 8, 14], np.float32), np.array([104, 24, 38], np.float32)
    col = back + (front - back) * (u ** 0.7)[..., None]
    # (the tongue: a fat rounded lump on the jaw's floor, its tip toward the front, turned with the jaw)
    k = 3
    tg = Image.new("L", (w * k, h * k), 0)
    hl = Image.new("L", (w * k, h * k), 0)
    pts, pts2 = [], []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        x = 1150 + 72 * math.cos(a)
        y = 482 - 15 * max(0.0, math.sin(-a)) ** 0.8 + 6 * max(0.0, math.sin(a))  # (domed on top, flat below)
        pts.append(turn(x, y))
        pts2.append(turn(1138 + 40 * math.cos(a), 474 - 5 * max(0.0, math.sin(-a)) + 2 * max(0.0, math.sin(a))))
    ImageDraw.Draw(tg).polygon([(x * k, y * k) for x, y in pts], fill=255)
    ImageDraw.Draw(hl).polygon([(x * k, y * k) for x, y in pts2], fill=255)
    tm = ndimage.gaussian_filter(np.asarray(tg.resize(size, Image.BOX)).astype(np.float32) / 255, 1.0)
    hm = ndimage.gaussian_filter(np.asarray(hl.resize(size, Image.BOX)).astype(np.float32) / 255, 2.5)
    # (a dark line where the tongue meets the throat: its outline)
    edge = np.clip(tm * (1 - tm) * 4, 0, 1) * 0.7
    col = col * (1 - tm[..., None]) + np.array([192, 58, 82], np.float32) * tm[..., None]
    col = col * (1 - hm[..., None] * 0.7) + np.array([228, 110, 128], np.float32) * (hm[..., None] * 0.7)
    col = col * (1 - edge[..., None]) + np.array([60, 14, 24], np.float32) * edge[..., None]
    mask = poly_mask(size, poly, 1.5)
    out = np.concatenate([col, 255 * mask[..., None]], -1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def main(G):
    hero = full(G, "clean531")
    bb = hero.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    k = LENGTH / (bb[2] - bb[0])
    ground = GROUND_Y
    ox = JOINTS["body"][0]

    def world(p):
        return [(p[0] - ox) * k, (ground - p[1]) * k]

    def put(sym, key, img, off, joint):
        sc = C.scaled(img, img.width * k)
        jx, jy = JOINTS[joint] if isinstance(joint, str) else joint
        save(sym, key, sc, ((jx - off[0]) * k, (jy - off[1]) * k))
        return sc

    joints = {j: world(p) for j, p in JOINTS.items() if not j.startswith("gill")}
    have = lambda n: os.path.exists(os.path.join(G, n + ".png"))  # noqa: E731
    nolegs = full(G, "r_nolegs") if have("r_nolegs") else hero
    # --- the body: legs, head and tail taken off (the model's), so nothing shows twice as they move ---
    # (r_nolegs: the legs off, the head and tail on; r_core: the head off at its neck, x ~1050, the rest on. The body:
    #  the first up to NECK_X, the second's rounded neck after; its tail end faded over the tail, which is behind)
    core = full(G, "r_core") if have("r_core") else nolegs
    a1, a2 = np.asarray(nolegs).astype(np.float32), np.asarray(core).astype(np.float32)
    xs = np.arange(a1.shape[1])[None, :, None]
    w = np.clip((xs - (NECK_X - 20)) / 40.0, 0, 1)
    body = a1 * (1 - w) + a2 * w
    body[..., 3:4] *= np.clip((xs - TAIL_X[0]) / (TAIL_X[1] - TAIL_X[0]), 0, 1)
    img, off = C.largest(Image.fromarray(np.clip(body, 0, 255).astype(np.uint8), "RGBA"), with_offset=True)
    put("body", "rest", img, off, "body")
    # --- the legs (cut along their outlines on the design; soft only where over the body), the far ones the near
    #     ones darker ---
    body_sil = np.asarray(nolegs)[..., 3] > 128
    for sym, j in (("leg_front", "leg_fn"), ("leg_back", "leg_bn")):
        img, off = cut(hero, leg_mask(hero.size, LEGS[j], body_sil, hero))
        sc = put(sym, "near", img, off, j)
        # (the far one: darker, its top faded - only its lower leg and foot show, below the body, which is in front)
        fa = np.asarray(AX.recolor(sc)).astype(np.float32)
        fa[..., :3] *= np.array([0.74, 0.6, 0.66], np.float32)          # (in shadow: a deeper rose, not grey)
        rows = np.arange(fa.shape[0])[:, None]
        fa[..., 3] *= np.clip((rows - fa.shape[0] * 0.3) / (fa.shape[0] * 0.2), 0, 1)
        save(sym, "far", Image.fromarray(fa.astype(np.uint8), "RGBA"),
             (PARTS[sym]["near"][2] * sc.width, PARTS[sym]["near"][3] * sc.height), skin=False)
    for far, (near, (dx, dy)) in FAR.items():
        jx, jy = JOINTS[near]
        joints[far] = world((jx + dx, jy + dy))
    # --- the tail, in three (from the drawing without legs: the back leg is not on it) ---
    timg, (tx0, ty0) = masked(nolegs, MASKS["tail"])
    t = C.scaled(timg, timg.width * k)
    cuts = [(JOINTS["tail2"][0] - tx0) * k, (JOINTS["tail3"][0] - tx0) * k]
    ov = 14
    segs = [("tail1", cuts[0] - ov, t.width), ("tail2", cuts[1] - ov, cuts[0] + ov), ("tail3", 0, cuts[1] + ov)]
    for sym, xa, xb in segs:
        xa, xb = int(max(0, xa)), int(min(t.width, xb))
        seg = t.crop((xa, 0, xb, t.height))
        if sym != "tail3":
            seg = feather_left(seg, 0, 2 * ov)
        jx, jy = JOINTS[sym]
        piv = ((jx - tx0) * k - xa, (jy - ty0) * k)
        sb = seg.getbbox()
        seg = seg.crop((0, sb[1], seg.width, sb[3]))
        save(sym, "0", seg, (piv[0], piv[1] - sb[1]))
    # --- the head (cut at the neck, feathered), its mouths; the eye cut from it ---
    lid = (104, 118, 66)
    # (the head without its jaw: everything above the lip line; the jaw: below it, its lip inked)
    jaw_m = poly_mask(hero.size, JAW_POLY, 1.0)
    cheek = disc_mask(hero.size, *CHEEK)
    himg, hoff = masked(hero, MASKS["head"], np.maximum(1 - jaw_m, cheek))
    head = C.scaled(himg, himg.width * k)
    ec = ((JOINTS["eye"][0] - hoff[0]) * k, (JOINTS["eye"][1] - hoff[1]) * k)
    eyes, pupil, head_noeye, epiv = eye_states(head, ec, lid)
    save("head", "shut", head_noeye, ((JOINTS["head"][0] - hoff[0]) * k, (JOINTS["head"][1] - hoff[1]) * k))
    # (the jaw whole, to its corner: not faded at the neck as the head is - its back end goes under the cheek)
    jimg, joff = cut(hero, jaw_m)
    ja = np.asarray(jimg).astype(np.float32) / 255
    lip = ink_stroke(jimg.size, [(x - joff[0], y + 2 - joff[1]) for x, y in MOUTH[1:-1]], 5, seed=7)
    ja = over(ja, lip * np.array([1, 1, 1, 1]) * (ja[..., 3:4] > 0.05))
    jimg = to_img(ja)
    put("jaw", "0", jimg, joff, "jaw")
    inside = mouth_inside(hero.size, JOINTS["jaw"])
    iimg, ioff = C.largest(inside, with_offset=True)
    put("mouth", "0", iimg, ioff, "jaw")
    for key, img in eyes.items():
        piv = (epiv[0] * (img.width / eyes["open"].width), epiv[1] * (img.height / eyes["open"].height))
        save("eye", key, img, piv)
    save("pupil", "0", pupil, (pupil.width / 2, pupil.height / 2))
    # --- the gills: an axolotl's (tools/gen/axolotl.py drew one: art/source/gill_axo.png), its base the joint ---
    if not have("gill_axo"):
        AX.draw_gill(os.path.join(G, "gill_axo.png"))
    gc, _, _ = load(G, "gill_axo")
    gill = C.scaled(gc, gc.width * GILL_H / gc.height)
    a = np.asarray(gill)[..., 3] > 128
    ys, xs = np.nonzero(a)
    base = (xs[ys >= ys.max() - 4].mean(), ys.max() - 4)
    save("gill", "near", gill, base)
    save("gill", "far", darker(gill, 0.62), base)
    for g, p in JOINTS.items():
        if g.startswith("gill"):
            joints[g] = world(p)
    PARTS["_gills"] = GILL_ANGLES
    PARTS["_jaw_open"] = JAW_OPEN
    # --- effects (the Chatty Slime's: art/source/fx_*.png, cut already; the anger vein drawn on white by
    #     tools/gen/vein.py, cut here) ---
    for sym, w in (("heart", 44), ("note", 36), ("zzz", 80), ("vein", 100), ("bubble", 34)):
        p = os.path.join(G, f"fx_{sym}.png")
        if os.path.exists(p):
            src = Image.open(p)
            src = src.convert("RGBA") if src.mode == "RGBA" else C.cutout(src)
            im = C.scaled(src, w)
            save(sym, "0", im, (im.width / 2, im.height / 2))
    PARTS["_joints"] = joints
    json.dump(PARTS, open(os.path.join(OUT, "parts.json"), "w"), indent=1)
    print("k", round(k, 3), "parts:", {s: list(v) for s, v in PARTS.items() if not s.startswith("_")})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "art", "source"))
