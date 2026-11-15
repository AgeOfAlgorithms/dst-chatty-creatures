"""The slime's parts, from the generated drawings (tools/gen/slime_jobs.py made them, with Qwen-Image-Edit on the
local ComfyUI) to the PNGs the rig builds from: art/parts/<symbol>/<key>.png and art/parts/parts.json ({symbol:
{key: [w, h, pivot x share, pivot y share, anchors]}}: the pivot from the top left as a share of the size, as Spriter
has it; the body's anchors in pixels from its foot, y up).

    python tools/gen/slime_parts.py [the generated PNGs' folder: art/source]

Cut out (cutout.py), scaled to the game's size (build pixels: the resting body 260 across, as big as the slime was),
the body's other shapes warped from the resting one (stretched, in the air, leaning, coiled) where the model drew
them badly, and the right eye the left one mirrored.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cutout as C  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "art", "parts")
BODY_W = 260


def cut_on_canvas(path):
    """cut out and cropped; with where the crop's top left was on the picture, and the picture's size (drawings
    edited from one picture stay lined up on it)"""
    im = Image.open(path).convert("RGB")
    cut, (x0, y0) = C.cutout(im, with_offset=True)
    return cut, (x0, y0), im.size


def scale(img, k):
    return C.scaled(img, max(1, img.width * k))


def save(sym, key, img, pivot, anchors=None):
    """pivot: (x, y) in img's pixels from its top left"""
    d = os.path.join(OUT, sym)
    os.makedirs(d, exist_ok=True)
    img.save(os.path.join(d, f"{key}.png"))
    w, h = img.size
    PARTS.setdefault(sym, {})[key] = [w, h, pivot[0] / w, pivot[1] / h, anchors or {}]


def foot_pivot(img):
    """the bottom middle of the opaque part (the body stands there)"""
    a = np.asarray(img)[..., 3] > 128
    ys, xs = np.nonzero(a)
    bottom = ys.max()
    row = np.nonzero(a[max(0, bottom - 6):bottom + 1].any(0))[0]
    return ((row.min() + row.max()) / 2, bottom + 1)


def body_anchors(img, piv):
    """from the foot, y up: H (its height), W (its width at 0.6 H), top (where the sprout grows), face (the middle of
    the face: forward of the middle, at 0.52 H), front (its front edge at 0.45 H)"""
    a = np.asarray(img)[..., 3] > 128
    h = a.shape[0]
    def row(yup):
        r = int(round(piv[1] - yup))
        r = min(max(r, 0), h - 1)
        xs = np.nonzero(a[r])[0]
        return (xs.min() - piv[0], xs.max() - piv[0]) if len(xs) else (0, 0)
    ys, xs = np.nonzero(a)
    H = piv[1] - ys.min()
    x0, x1 = row(0.6 * H)
    W = x1 - x0
    tx = xs[ys <= ys.min() + 3].mean() - piv[0]
    fx0, fx1 = row(0.5 * H)
    face = ((fx0 + fx1) / 2 + 0.2 * (fx1 - fx0), 0.52 * H)     # (forward of the seed: the design's three-quarter view)
    return dict(H=float(H), W=float(W), top=[float(tx), float(H)], face=[float(face[0]), float(face[1])],
                front=[float(row(0.45 * H)[1]), float(0.45 * H)])


def body(key, img):
    piv = foot_pivot(img)
    save("body", key, img, piv, body_anchors(img, piv))


def warped(rest, k_of_v, sy=1.0, bend=0.0, sx=1.0):
    """rest's drawing warped: across scaled by k_of_v(v) * sx (v its height share, 0 at the foot), up by sy, its top bent
    forward by bend x its height (as v squared)"""
    piv = foot_pivot(rest)
    a = np.asarray(rest)[..., 3] > 128
    H = piv[1] - np.nonzero(a)[0].min()
    # (the rest's pixels about its foot)
    pad = Image.new("RGBA", (rest.width * 2, rest.height), (0, 0, 0, 0))
    ox = int(rest.width - piv[0])
    pad.paste(rest, (ox, 0))
    pad = pad.crop((0, 0, pad.width, int(math.ceil(piv[1]))))
    Ho = H * sy

    def inv(X, Y):
        v = np.clip(Y / max(Ho, 1), 0, 1.2)
        yy = Y / sy
        xx = (X - bend * Ho * v * v) / (k_of_v(v) * sx)
        return xx, yy
    W = int(pad.width * max(1.0, sx) + abs(bend) * Ho * 2 + 20)
    out = C.warp(pad, inv, (W, int(Ho + 30)), (W / 2, 0))
    bb = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return out.crop(bb)


INK = (22, 20, 18)
LID = ((36, 70, 36), (74, 116, 60))         # (the lid's jelly: dark at its top, lighter at its edge)


def ink_stroke(size, pts, width, seed=0, passes=4):
    """a scratchy ink stroke along pts (pixels, from the top left): a few jittered thinner lines over a core, drawn 4x
    and boxed down; an RGBA numpy array"""
    from PIL import ImageDraw
    rnd = np.random.default_rng(abs(int(seed)))
    k = 4
    im = Image.new("L", (size[0] * k, size[1] * k), 0)
    d = ImageDraw.Draw(im)
    P = np.array(pts, float) * k
    d.line([tuple(p) for p in P], fill=255, width=int(width * k * 0.75), joint="curve")
    for i in range(passes):
        J = P + rnd.normal(0, width * k * 0.18, P.shape)
        d.line([tuple(p) for p in J], fill=255, width=max(1, int(width * k * rnd.uniform(0.18, 0.35))), joint="curve")
    for p in (P[0], P[-1]):
        r = width * k * 0.36
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=255)
    al = np.asarray(im.resize(size, Image.BOX)).astype(np.float32) / 255
    out = np.zeros((size[1], size[0], 4), np.float32)
    out[..., :3] = np.array(INK) / 255
    out[..., 3] = al
    return out


SPLASH_W = 280                   # (the ring's width at scale 1: about the slime's foot, the rig spreads it wider)
SPLASH_THICK = (0.30, 0.23, 0.17, 0.14)   # (its frames: the goo thinning as the ring spreads, the last ones breaking up)
SPLASH_BREAK = (0.0, 0.0, 0.25, 0.55)


def splash_ring(thick, broken=0.0, seed=0):
    """the landing splash: a flat ring of goo on the ground round the slime's foot, seen from the game's angle: lumpy,
    uneven, inked, the puddle's greens, beads on its rim; broken into blobs as it thins. Drawn 4x and boxed down.
    (back half, front half) as images, cut at the ring's middle row (the back half goes behind the body, the front
    one before it)"""
    from scipy.ndimage import distance_transform_edt as edt
    k = 4
    rx = SPLASH_W / 2
    ry = rx * 0.36
    pad = 16
    w, h = int(2 * (rx + pad)), int(2 * (ry + pad))
    w += w % 2
    h += h % 2
    W, H = w * k, h * k
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32) / k
    X -= w / 2
    Y -= h / 2
    rnd = np.random.default_rng(seed)
    rho = np.sqrt((X / rx) ** 2 + (Y / ry) ** 2)
    th = np.arctan2(Y / ry, X / rx)

    def wobble(amp, n=(2, 3, 5, 7)):
        out = np.zeros_like(th)
        for m in n:
            out += rnd.uniform(0.4, 1.0) / m * np.sin(m * th + rnd.uniform(0, 2 * math.pi))
        return amp * out
    outer = 1 + wobble(0.10)
    inner = 1 - thick * (1 + wobble(0.8)) - 0.02
    ring = (rho <= outer) & (rho >= inner)
    if broken:
        gaps = wobble(1.0, (4, 6, 9, 13))
        ring &= gaps > (broken - 0.5) * 0.6
        # (the broken ends rounded off, slivers gone: blurred and cut again)
        from scipy.ndimage import gaussian_filter
        ring = gaussian_filter(ring.astype(np.float32), 3.0 * k) > 0.5
    ink_w = (2.2 + 4 * thick) * k
    d_in = edt(ring)
    core = d_in > ink_w
    # (no bits of bare ink: a piece too thin to have goo in it goes)
    from scipy.ndimage import label
    lab, n = label(ring)
    keep = np.bincount(lab[core], minlength=n + 1) > 40 * k * k
    keep[0] = False
    ring = keep[lab]
    INK_C = np.array(INK) / 255
    FILL = np.array((108, 150, 92)) / 255
    DARK = np.array((66, 100, 50)) / 255
    LIGHT = np.array((178, 216, 152)) / 255
    rgb = np.zeros((H, W, 3), np.float32)
    al = np.zeros((H, W), np.float32)
    rgb[ring] = INK_C
    al[ring] = 1
    rgb[core] = FILL
    # (shadow along the near side of each lump's outer edge; a gleam along the middle of the goo, facing up)
    d_out = edt(rho <= outer)
    rgb[core & (Y > 0) & (d_out < ink_w + ry * thick * 0.55 * k)] = DARK
    mid = (inner + outer) / 2
    gleam = core & (np.abs(rho - mid + thick * 0.12) < thick * 0.13) & (np.sin(th * 3 + seed) > 0.1)
    rgb[gleam] = LIGHT
    # (beads of goo on the rim)
    for i in range(6):
        ang = (i + rnd.uniform(-0.35, 0.35)) / 6 * 2 * math.pi
        m = (1 + 0.04 * rnd.uniform(-1, 1)) * (1 - thick * 0.3)
        bx, by = math.cos(ang) * rx * m, math.sin(ang) * ry * m - 2
        r = rnd.uniform(5, 8) * (0.55 + thick * 1.5)
        d2 = (X - bx) ** 2 + ((Y - by) * 1.15) ** 2
        bead = d2 <= r ** 2
        rgb[bead] = INK_C
        al[bead] = 1
        inside = d2 <= (r - 2.2) ** 2
        rgb[inside] = FILL
        dot = (X - bx + r * 0.3) ** 2 + (Y - by + r * 0.35) ** 2 <= (r * 0.3) ** 2
        rgb[dot & inside] = LIGHT
    img = np.concatenate([rgb * al[..., None], al[..., None]], -1)
    img = np.clip(img.reshape(h, k, w, k, 4).mean((1, 3)), 0, 1)
    return C.unpremul(img[:h // 2]), C.unpremul(img[h // 2:])


def premul_a(a):
    return np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], -1)


def over(dst, src):
    """straight-alpha src over dst (numpy RGBA 0..1)"""
    sa = src[..., 3:4]
    da = dst[..., 3:4]
    oa = sa + da * (1 - sa)
    rgb = (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-4)
    return np.concatenate([rgb, oa], -1)


def eye_set(open_img, pupil_img, pupil_share=0.38):
    """the eye's lidded states from its open drawing: {key: RGBA image}, all on its canvas (lined up). A lid: the
    eye's white covered above a line (lo..hi: where it crosses the left and right of the eye, a share of its radius,
    y up), dark jelly with a gloss, a scratchy ink edge; the pupil under it, low"""
    from scipy import ndimage
    a = np.asarray(open_img).astype(np.float32) / 255
    h, w = a.shape[:2]
    cx, cy = w / 2, h / 2
    white = (a[..., :3].min(-1) > 0.7) & (a[..., 3] > 0.5)
    lab, _ = ndimage.label(white)
    inner = lab == lab[int(cy), int(cx)]
    ys, xs = np.nonzero(inner)
    cx, cy = xs.mean() + 0.5, ys.mean() + 0.5
    R = math.sqrt(inner.sum() / math.pi)
    inner_d = ndimage.binary_dilation(inner, iterations=3)
    yy, xx = np.mgrid[0:h, 0:w]
    X, Y = xx + 0.5 - cx, cy - (yy + 0.5)
    ring = a.copy()
    ring[..., 3] *= ~inner_d
    base = np.zeros_like(a)
    base[inner_d] = (1, 1, 1, 1)
    pd = pupil_share * open_img.width
    pup = C.scaled(pupil_img, pd)
    out = {}

    def with_pupil(dy, dx=0.0):
        img = base.copy()
        layer = np.zeros_like(a)
        px, py = int(cx + dx * R - pup.width / 2), int(cy - dy * R - pup.height / 2)
        pa = np.asarray(pup).astype(np.float32) / 255
        y0, x0 = max(py, 0), max(px, 0)
        y1, x1 = min(py + pup.height, h), min(px + pup.width, w)
        layer[y0:y1, x0:x1] = pa[y0 - py:y1 - py, x0 - px:x1 - px]
        layer[..., 3] *= inner_d
        return over(img, layer)

    for key, (lo, hi), pdy, pdx in (("half", (-0.12, -0.12), -0.45, 0.0), ("angry", (0.8, -0.4), -0.45, 0.12),
                                    ("sad", (-0.4, 0.8), -0.5, -0.08)):
        img = with_pupil(pdy, pdx)
        line = (lo + (X / R + 1) / 2 * (hi - lo)) * R
        cover = inner_d & (Y > line)
        u = np.clip((Y - line) / (R * 1.2), 0, 1)[..., None]
        col = np.array(LID[1]) / 255 * (1 - u) + np.array(LID[0]) / 255 * u
        lidl = np.concatenate([col, cover[..., None].astype(np.float32)], -1)
        # (a gloss: a soft light streak along the top of the lid)
        g = np.exp(-(((X + 0.15 * R) / (0.55 * R)) ** 2 + ((Y - line - 0.55 * (R + 0) * 0.6 - 0.25 * R) / (0.12 * R)) ** 2))
        lidl[..., :3] = lidl[..., :3] * (1 - 0.45 * g[..., None]) + 0.45 * g[..., None] * np.array([0.72, 0.85, 0.6])
        img = over(img, lidl)
        x_end = R * 1.04
        pts = [(cx + x, cy - (lo + (x / R + 1) / 2 * (hi - lo)) * R) for x in np.linspace(-x_end, x_end, 12)]
        img = over(img, ink_stroke((w, h), pts, R * 0.16, seed=len(key)))
        out[key] = over(img, ring)
    out["open"] = over(base, ring)
    return {k: C.unpremul(np.concatenate([v[..., :3] * v[..., 3:4], v[..., 3:4]], -1)) for k, v in out.items()}


SEED_FADE = 0.6               # (how much of the jelly's colour is over the seed: it is inside, seen through the goo)


def seed_through_jelly(path, lift=False):
    """the seed drawn in the body, toned down: found as the biggest grey-black blob inside the jelly (the jelly's own
    darks are green; its ink is at its edge), its colour mixed with the jelly's round it. lift: the seed taken out of
    the body instead (jelly where it was) and returned - (its picture, its middle in the body's pixels) - so the rig
    draws it rigid inside the body, not squashed and stretched with it"""
    from scipy import ndimage
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im).astype(np.float32) / 255
    rgb = a[..., :3]
    L = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    chroma = rgb.max(-1) - rgb.min(-1)
    din = ndimage.distance_transform_edt(a[..., 3] > 0.9)
    lab, n = ndimage.label(ndimage.binary_closing((chroma < 0.09) & (L < 0.55) & (din > 8), iterations=2))
    if not n:
        return None
    sizes = ndimage.sum(np.ones_like(L), lab, range(1, n + 1))
    seed = ndimage.binary_fill_holes(lab == int(np.argmax(sizes)) + 1)
    seed = ndimage.binary_dilation(seed, iterations=2)
    w = ndimage.gaussian_filter(seed.astype(np.float32), 1.5)[..., None]
    # (the jelly's colour there: the body blurred with the seed left out)
    keep = (~seed & (din > 4)).astype(np.float32)
    num = np.stack([ndimage.gaussian_filter(rgb[..., c] * keep, 14) for c in range(3)], -1)
    jelly = num / np.maximum(ndimage.gaussian_filter(keep, 14), 1e-4)[..., None]
    faded = rgb * (1 - w * SEED_FADE) + jelly * (w * SEED_FADE)
    ys, xs = np.nonzero(seed)
    mid = (float(xs.mean()), float(ys.mean()))
    cut = None
    if lift:
        # (its picture: the faded seed, its edge soft; the body: the jelly where it was, a little wider)
        wide = ndimage.gaussian_filter(ndimage.binary_dilation(seed, iterations=3).astype(np.float32), 2.0)[..., None]
        y0, y1, x0, x1 = ys.min() - 4, ys.max() + 5, xs.min() - 4, xs.max() + 5
        pic = np.concatenate([np.clip(faded, 0, 1), w], -1)[y0:y1, x0:x1]
        cut = (Image.fromarray((pic * 255 + 0.5).astype(np.uint8), "RGBA"), (mid[0] - x0, mid[1] - y0))
        out_rgb = rgb * (1 - wide) + jelly * wide
    else:
        out_rgb = faded
    out = np.concatenate([np.clip(out_rgb, 0, 1), a[..., 3:4]], -1)
    Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA").save(path)
    return cut, mid


def main(G):
    # --- the body ---
    src_rest = os.path.join(G, "p_body.png")
    rest_cut, _, _ = cut_on_canvas(src_rest)
    k = BODY_W / rest_cut.width
    rest = scale(rest_cut, k)
    body("rest", rest)
    for key, name in (("squash", "b_squash"), ("squash2", "b_squash2"), ("splat", "b_splat")):
        p = os.path.join(G, name + ".png")
        if os.path.exists(p):
            c, _, size = cut_on_canvas(p)
            src_size = Image.open(src_rest).size
            body(key, scale(c, k * src_size[0] / size[0]))
    smooth = lambda lo, hi, v: lo + (hi - lo) * np.clip(v, 0, 1) ** 0.7  # noqa: E731
    body("stretch", warped(rest, lambda v: smooth(0.62, 0.84, v / 0.5), sy=1.3))
    body("stretch2", warped(rest, lambda v: smooth(0.5, 0.74, v / 0.5), sy=1.55))
    body("air", warped(rest, lambda v: smooth(0.42, 1.0, v / 0.55), sy=1.08))
    body("lean", warped(rest, lambda v: smooth(0.8, 0.95, v / 0.5), sy=1.12, bend=0.3))
    body("coil", warped(rest, lambda v: smooth(1.0, 1.08, v / 0.5), sy=0.84, bend=-0.22))
    body("lean_back", warped(rest, lambda v: smooth(0.9, 1.0, v / 0.5), sy=1.04, bend=-0.16))

    # --- the eyes: one scale for all (the expressions were edited from one picture: lined up) ---
    E = 50
    base, _, _ = cut_on_canvas(os.path.join(G, "eye_open.png"))
    pupil, _, _ = cut_on_canvas(os.path.join(G, "eye_pupil.png"))
    lidded = eye_set(base, pupil)
    eyes = {}
    for key, img in lidded.items():
        eyes[key] = C.scaled(img, E)
    eyes["wide"] = C.scaled(lidded["open"], E * 1.12)
    for key, wk in (("closed", 0.9), ("happy", 0.9), ("squeeze", 0.72), ("dead", 0.7)):
        p = os.path.join(G, f"eye2_{key}.png")
        if os.path.exists(p):
            c, _, _ = cut_on_canvas(p)
            img = C.scaled(C.largest(c), E * wk)
            if key in ("closed", "happy"):            # (flatter: a lid's line, not a letter U)
                img = img.resize((img.width, max(1, round(img.height * 0.55))), Image.LANCZOS)
            eyes[key] = img
    for key in ("open", "wide", "half", "angry", "sad", "closed", "happy", "squeeze", "dead"):
        if key not in eyes:
            print("missing eye", key)
            continue
        img = eyes[key]
        cx, cy = img.width / 2, img.height / 2
        save("eye_l", key, img, (cx, cy))
        save("eye_r", key, ImageOps.mirror(img), (img.width - cx, cy))
    pup = C.scaled(pupil, E * 0.38)
    save("pupil", "0", pup, (pup.width / 2, pup.height / 2))

    # --- the mouths, sprout and effects: each to its size ---
    sizes = {"mouth_smile": 40, "mouth_talk": 38, "mouth_talk_wide": 46, "mouth_o": 22, "mouth_frown": 36,
             "mouth_flat": 26, "mouth_wavy": 38, "mouth_gape": 50, "mouth_chomp": 44, "mouth_grin": 50,
             "mouth_yawn": 30,
             "fx_drop": 15, "fx_puddle": 130, "fx_heart": 30, "fx_note": 24, "fx_zzz": 54,
             "fx_vein": 54, "fx_bubble": 22, "fx_lump": 28}
    for name, w in sizes.items():
        p = os.path.join(G, name + ".png")
        sym, key = name.split("_", 1)
        if sym == "fx":
            sym, key = key, "0"
        if name == "mouth_flat":                      # (the model drew a U for it: an ink stroke instead)
            sz = (int(w * 1.3), 14)
            img = C.unpremul(np.clip(premul_a(ink_stroke(sz, [(5, 7), (sz[0] * 0.5, 8), (sz[0] - 5, 7)], 5.5)), 0, 1))
            save(sym, key, img, (img.width / 2, img.height / 2))
            continue
        if name == "mouth_frown":                     # (and a U for this: the smile upside down)
            p = os.path.join(G, "mouth_smile.png")
        if not os.path.exists(p):
            print("missing", name)
            continue
        c, _, _ = cut_on_canvas(p)
        if name == "fx_splash":                       # (the model put a drop on top of its splash: the crown only)
            c = c.crop((0, int(c.height * 0.7), c.width, c.height))
            c = c.crop(c.getbbox())
        if name not in ("fx_zzz", "fx_splash", "fx_vein"):     # (the vein: four pieces, all kept)
            c = C.largest(c)
        if name == "mouth_frown":
            c = c.transpose(Image.FLIP_TOP_BOTTOM)
        img = C.scaled(c, w)
        piv = (img.width / 2, img.height / 2)
        if sym in ("splash", "puddle"):
            piv = (img.width / 2, img.height * 0.85)
        save(sym, key, img, piv)
    # (the landing splash: drawn, a ring of goo (the model's splash, cut to its crown, read as a fringe of hair);
    #  back and front halves, both pivoted on the ring's middle, so the rig places it at the foot)
    for i, th in enumerate(SPLASH_THICK):
        back, front = splash_ring(th, SPLASH_BREAK[i], seed=i + 3)
        save("splash", str(i), back, (back.width / 2, back.height))
        save("splash_front", str(i), front, (front.width / 2, 0))
    # (the sprout: the one on the design drawing, cut from it - the model drew a whole slime when asked for one; the
    #  wilted one the model's)
    hero = Image.open(os.path.join(G, "slime_c5.png")).convert("RGB")
    m = Image.new("L", hero.size, 0)
    from PIL import ImageDraw
    ImageDraw.Draw(m).polygon([(330, 30), (670, 30), (670, 215), (540, 225), (520, 242), (470, 242), (450, 225),
                               (330, 215)], fill=255)
    bg = Image.new("RGB", hero.size, (255, 255, 255))
    c = C.largest(C.cutout(Image.composite(hero, bg, m)))
    for key in ("up", "wilt"):
        if key == "wilt":
            p = os.path.join(G, "sprout_wilt.png")
            if not os.path.exists(p):
                print("missing sprout wilt")
                continue
            c, _, _ = cut_on_canvas(p)
            c = C.largest(c)
            img = C.scaled(c, c.width * PARTS["sprout"]["up"][1] * 0.85 / c.height)
        else:
            img = C.scaled(c, c.width * 62 / c.height)
        a = np.asarray(img)[..., 3] > 128
        ys, xs = np.nonzero(a)
        bx = xs[ys >= ys.max() - 3].mean()
        save("sprout", key, img, (bx, ys.max() - 2))
    # (the seed: lifted out of every body drawing (in the splat too: it lies in the puddle, whole), the resting one's kept as
    #  its own symbol; each body's anchors say where its seed sat (from the foot, y up), so the rig puts it there)
    for f in sorted(os.listdir(os.path.join(OUT, "body")), key=lambda f: f != "rest.png"):
        key = f[:-4]
        r = seed_through_jelly(os.path.join(OUT, "body", f), lift=True)
        if not r:
            continue
        (pic, piv), (mx, my) = r
        w, h, px, py, anchors = PARTS["body"][key]
        anchors["seed"] = [mx - px * w, py * h - my]
        if key == "rest":
            save("seed", "0", pic, piv)
    json.dump(PARTS, open(os.path.join(OUT, "parts.json"), "w"), indent=1)
    print("parts:", {s: list(v) for s, v in PARTS.items()})


PARTS = {}
if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "art", "source"))
