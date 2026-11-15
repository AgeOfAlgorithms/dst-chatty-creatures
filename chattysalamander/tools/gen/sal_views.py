"""The salamander from the front (facing down: toward us) and from behind (facing up), drawn as sal_vector.py draws
its side: each part its own vector shape in DST's mob style (sketched ink over a dusty, countershaded fill with a
wet sheen - no hatching: its skin is smooth), the same heavy axolotl - small glowing eyes in dark sockets under a
heavy brow, two fangs, thick clawed legs, big gills. The game is four-faced: these are the "_down" and "_up" views of
every animation (tools/anim/rig.py poses them).

Called by sal_vector.main (it has the scale and the parts' writer): draw(k, save, quick) -> {"front": joints,
"back": joints} (canvas pixels; a canvas as the side's, 1328 x 800, y down, the creature's middle at x = MID, the
ground at y = 700).

The front: the head (a broad face: the side's eye frames - mirrored for the other eye - a wide mouth, fangs,
nostrils, the brows), its jaw dropping straight down to open the mouth, the mouth's inside, the gills fanned out both
sides, the front legs either side of the chest (one drawing, mirrored), the chest, the hind feet peeking out behind,
the tail's tip curling out behind. The back: the back of the head, the gills, the broad back with its fin along the
spine, the hind legs nearest us, the front feet peeking out, and the tail coming toward us, bent from side to side
as one drawing (its frames), like the side's.
"""
import math

import numpy as np
from scipy import ndimage

import sal_vector as V
from sal_vector import Part, spline, INK, SKIN_T, SKIN, SKIN_B, BELLY_T, BELLY_B, SPOT, SPOT2, W_INK, SS, DEEP

MID = 664


def mir(pts):
    return [(2 * MID - x, y) for x, y in pts]


def tooth(p, c, hw, ln, s, up=False):
    """one tooth: a rounded cone from its root c (hw: half its width, ln: its length; s: which side - its tip leans
    a little toward the middle; up: pointing up, from the lower jaw); its mask and outline"""
    d = -1 if up else 1
    tip = (c[0] - s * hw * 0.3, c[1] + d * ln)
    pts = [(c[0] - hw, c[1] - d * 5), (c[0] - hw * 0.95, c[1] + d * ln * 0.25), (c[0] - hw * 0.6, c[1] + d * ln * 0.62),
           tip, (c[0] + hw * 0.45, c[1] + d * ln * 0.62), (c[0] + hw * 0.85, c[1] + d * ln * 0.25),
           (c[0] + hw, c[1] - d * 5)]
    q = spline(pts, closed=True, n=6)
    fm = p.poly(q, blur=0.5, smooth=False)
    p.paint(fm, V.FANG)
    p.paint(ndimage.gaussian_filter(fm * (1 - p.shift(fm, s * 4, 0)), 2 * SS) * fm, (206, 192, 176), 0.8)  # (its shade)
    return fm, q


def fangs(p, m, at, hw, ln):
    """two white fangs hanging from the upper lip (at: the left one's root; the right mirrored); m grown by them"""
    polys = []
    for c in (at, (2 * MID - at[0], at[1])):
        fm, q = tooth(p, c, hw, ln, 1 if c[0] > MID else -1)
        polys.append(q)
        m = np.maximum(m, fm)
    return m, polys


# --- the front ------------------------------------------------------------------------------------------------------
# (almost a dragon, as a giant salamander faces you: a broad flat wedge of a head carried low, its smile wrapping the
#  whole width, small eyes on brow bumps at its top corners under heavy ridges, fangs; the gills swept up and back
#  like a crown of horns; massive shoulders, the forelegs splayed out sideways with the elbows out, big hands planted
#  wide)

F_LIP = [(436, 452), (480, 467), (540, 479), (600, 485), (664, 487), (728, 485), (788, 479), (848, 467), (892, 452)]
_F_HALF = [(664, 232), (618, 236), (592, 234), (572, 228), (548, 225), (522, 231), (488, 250), (452, 278),
           (424, 322), (412, 380), (420, 424), (436, 452)]          # (a big domed skull)          # (top middle -> the left corner of the mouth)
F_HEAD = _F_HALF + F_LIP[1:-1] + mir(_F_HALF)[::-1][:-1]
F_EYE_L, F_EYE_R, F_EYE_K = (552, 378), (776, 378), 1.0      # (the side's eye frames; 102 px over the mouth, as
#  the side's eye is)
F_HEAD_DY = 34                 # (the head's parts placed this much lower than drawn)
F_FANG = (606, 485)                                          # (the left fang's root)
F_JAW = [(436, 450)] + [(x, y + 2) for x, y in F_LIP[1:-1]] + [(892, 450), (894, 482), (878, 522), (836, 554),
                                                               (762, 574), (664, 580), (566, 574), (492, 554),
                                                               (450, 522), (434, 482)]     # (a big heavy lower jaw:
#  the head's own taper carried on down - one wedge of a face, not a second bun)
F_LOW_TEETH = [(500, 470), (828, 470)]                      # (small teeth up from the lower jaw, by its corners)
F_JAW_DROP = 2.4               # (canvas px the jaw drops a degree of the side's jaw)
F_BODY = [(664, 390), (784, 400), (866, 444), (892, 520), (882, 600), (846, 660), (764, 694), (664, 702), (564, 694),
          (482, 660), (446, 600), (436, 520), (462, 444), (544, 400)]
F_GILLS = [(452, 296), (430, 338), (420, 384)]          # (the left side's roots; the right's mirrored)
F_GILL_REST = (18, 50, 86)                               # (swept up and back: a crown)
_ARM = [((476, 494), 62), ((400, 572), 52), ((376, 640), 44), ((370, 666), 40)]
F_LEG = dict(  # (the front leg on the left, splayed out: the right is it mirrored)
    outline=[tuple(q) for q in V.capsule_outline(_ARM)],
    toes=[((340, 682), (302, 702)), ((358, 692), (334, 718)), ((382, 696), (376, 724)), ((404, 690), (416, 716))],
    pivot=(476, 494), fade=(432, 470))
F_HIND = dict(
    outline=[(470, 610), (520, 618), (532, 660), (524, 690), (500, 704), (466, 706), (446, 694), (450, 664),
             (456, 636)],
    toes=[((462, 698), (452, 714)), ((486, 702), (484, 718)), ((510, 698), (518, 713))],
    pivot=(494, 640))
F_TAIL = [((664, 560), 70), ((790, 524), 54), ((900, 476), 32), ((968, 438), 15), ((996, 420), 5)]


def leg_spec(d, hatch=None, crease=None):
    return dict(outline=d["outline"], toes=d["toes"], crease=crease, hatch=hatch or [], fade=d.get("fade"))


def draw_front(k, save, quick=False):
    J = {"body": (664, 540), "head": (664, 440), "lip": (664, 480), "eye_l": F_EYE_L, "eye_r": F_EYE_R,
         "leg_fn": F_LEG["pivot"], "leg_ff": (2 * MID - F_LEG["pivot"][0], F_LEG["pivot"][1]),
         "leg_bn": F_HIND["pivot"], "leg_bf": (2 * MID - F_HIND["pivot"][0], F_HIND["pivot"][1]),
         "tail": F_TAIL[0][0]}
    for i, g in enumerate(F_GILLS):
        J[f"gill_l{i}"] = g
        J[f"gill_r{i}"] = (2 * MID - g[0], g[1])
    # --- the head: one silhouette down to the mouth's line (the jaw continues it under the lip) ---
    p = Part((390, 190, 940, 540), seed=31)
    m = p.poly(F_HEAD)
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B, split=0.62)
    p.mottle(m)
    sockets = np.maximum(p.ellipse(F_EYE_L, (47, 40), 2.5), p.ellipse(F_EYE_R, (47, 40), 2.5))
    p.paint(ndimage.gaussian_filter(sockets, 6 * SS) * m, V.SOCKET_RIM, 0.6)
    area = m * (p.shift(m, 0, 16) > 0.5) * (1 - ndimage.gaussian_filter(sockets, 9 * SS))
    p.blobs(area * (np.abs(np.arange(p.W)[None, :] / SS + p.x0 - MID) > 40), 18, 4, 12, (SPOT, SPOT2))
    p.sheen(m)
    # (a shadow down the middle of the snout and under the brows: it is broad and flat, not a ball)
    p.paint(ndimage.gaussian_filter(p.ellipse((MID, 420), (70, 36), 1), 14 * SS) * m, SKIN_B, 0.25)
    for s in (1, -1):
        ex = F_EYE_R[0] if s > 0 else F_EYE_L[0]
        # (the brows: their own symbol, by the mood - placed with the eyes by the rig)
        p.paint(p.ellipse((MID + s * 30, 440), (8, 6), rot=s * 25), INK)                  # (nostrils)
        cx = 892 if s > 0 else 436
        p.paint(p.stroke([(cx - s * 10, 448), (cx + s * 6, 450), (cx + s * 12, 436)], 4.6), INK)  # (its corners up)
    m, fpolys = fangs(p, m, F_FANG, 14, 34)
    p.paint(p.flicks(F_HEAD, m, 4, length=(5, 11), facing=0.5), INK, 0.8)
    p.paint(p.sketch([spline(F_HEAD)], m, weight=0.35), INK)
    p.paint(p.sketch(fpolys, m, w=W_INK * 0.45, weight=0.2), INK)
    save("fhead", "0", p, J["head"])
    # --- the jaw: the head's lower half (no line along its top: that is under the lip), dropping straight down ---
    p = Part((400, 430, 930, 610), seed=32)
    m = p.poly(F_JAW)
    p.grad_fill(m, SKIN_B, SKIN_B, DEEP, split=0.4)                # (the head's underside, darker down to the chin)
    p.mottle(m)
    p.blobs(m * (p.shift(m, 0, 20) > 0.5) * (p.shift(m, 0, -18) > 0.5), 8, 4, 10, (SPOT, SPOT2))
    yy = (np.arange(p.H) / SS + p.y0)[:, None]
    tpolys = []
    for c in F_LOW_TEETH:
        fm, q = tooth(p, c, 8, 18, 1 if c[0] > MID else -1, up=True)
        tpolys.append(q)
        m = np.maximum(m, fm)
    p.paint(p.sketch([spline(F_JAW)], m, w=W_INK * 0.95, weight=0.7) * np.clip((yy - 470) / 14, 0, 1), INK)
    p.paint(p.sketch(tpolys, m, w=W_INK * 0.4, weight=0.2), INK)
    save("fjaw", "0", p, J["lip"])
    p = Part((410, 440, 920, 580), seed=33)
    inside = [(x, y - 6) for x, y in F_LIP] + [(900, 470), (880, 500), (800, 530), (664, 540), (528, 530),
                                                (448, 500), (428, 470)]
    m = p.poly(inside, blur=1.2)
    p.grad_fill(m, (34, 8, 14), (70, 16, 26), (104, 24, 38), split=0.5)
    tongue = p.ellipse((664, 520), (130, 20), blur=1.2) * m
    p.paint(tongue, (180, 58, 80))
    p.paint(p.ellipse((664, 514), (70, 7), blur=2) * tongue, (214, 104, 120), 0.7)
    save("fmouth", "0", p, J["lip"])
    # --- the chest and shoulders (behind the head and legs) ---
    p = Part((360, 330, 970, 720), seed=34)
    m = p.poly(F_BODY)
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B, split=0.45)
    belly = ndimage.gaussian_filter(p.ellipse((664, 640), (100, 52), blur=1), 14 * SS) * m
    p.paint(belly, BELLY_T, 0.4)
    p.paint(ndimage.gaussian_filter(p.ellipse((664, 560), (90, 36), 1), 10 * SS) * m, SKIN_B, 0.35)  # (under the chin)
    p.mottle(m)
    side = m * (1 - belly) * (p.shift(m, 0, 16) > 0.5) * (p.shift(m, 0, -24) > 0.5)
    p.blobs(side, 22, 5, 14, (SPOT, SPOT2))
    p.sheen(m, alpha=0.35)
    p.paint(p.flicks(F_BODY, m, 4), INK, 0.9)
    p.paint(p.sketch([spline(F_BODY)], m), INK)
    save("fbody", "0", p, J["body"])
    # --- the legs: the front (left, splayed; mirrored for the right), the hind peeking out behind (darker) ---
    save("fleg", "0", V.draw_leg(leg_spec(F_LEG), 35), F_LEG["pivot"])
    hind = V.draw_leg(leg_spec(F_HIND), 36)
    hind.a[..., :3] *= np.array([0.74, 0.6, 0.66], np.float32)
    save("fhind", "0", hind, F_HIND["pivot"])
    # --- the tail's tip, behind: curling out to one side, its fin over it ---
    p = Part((600, 360, 1030, 640), seed=37)
    m = p.capsule(F_TAIL)
    top = [(x, y - w + 4) for (x, y), w in F_TAIL]
    edge = [(x, y - w - 26 * min(1, w / 30)) for (x, y), w in F_TAIL]
    fin = p.poly(top + edge[::-1], blur=1) * (1 - m)
    p.grad_fill(fin, V.FIN_T, V.FIN, V.FIN_B)
    p.paint(p.sketch([p.resample(edge, closed=False)], fin, w=W_INK * 0.5, weight=0.2) * (1 - m), INK)
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B)
    p.mottle(m)
    p.sheen(m, alpha=0.35)
    p.paint(p.sketch([V.capsule_outline(F_TAIL)], m, w=W_INK * 0.8), INK)
    save("ftail", "0", p, J["tail"])
    draw_hips_front(save, J)
    # (the head carried low, sunk between the shoulders: its parts drawn where they are, placed lower)
    for key in [q for q in J if q in ("head", "lip", "eye_l", "eye_r") or q.startswith("gill")]:
        J[key] = (J[key][0], J[key][1] + F_HEAD_DY)
    return J


# --- the back -------------------------------------------------------------------------------------------------------

B_HEAD = [(664, 186), (770, 194), (852, 222), (896, 268), (908, 330), (892, 392), (852, 430), (664, 442), (476, 430),
          (436, 392), (420, 330), (432, 268), (476, 222), (558, 194)]
B_BODY = [(664, 300), (772, 312), (862, 350), (912, 420), (920, 500), (902, 580), (852, 640), (762, 676), (664, 684),
          (566, 676), (476, 640), (426, 580), (408, 500), (416, 420), (466, 350), (556, 312)]
B_GILLS = [(446, 266), (430, 314), (434, 362)]
B_GILL_REST = (30, 68, 104)
B_HIND = dict(
    outline=[(416, 546), (466, 538), (508, 566), (514, 616), (498, 656), (484, 688), (468, 708), (430, 716),
             (396, 708), (384, 690), (398, 666), (404, 628), (398, 590)],
    toes=[((402, 700), (390, 716)), ((428, 708), (424, 724)), ((456, 704), (462, 720))],
    pivot=(464, 596), crease=[(404, 612), (440, 630), (482, 628), (508, 612)])
B_FORE = dict(
    outline=[(424, 398), (462, 404), (470, 452), (458, 506), (446, 546), (426, 562), (398, 560), (382, 548),
             (392, 526), (404, 490), (408, 446)],
    toes=[((392, 552), (380, 566)), ((414, 558), (410, 574))],
    pivot=(444, 420))
B_TAIL_ROOT, B_TAIL_TIP = (664, 600), (664, 850)
B_TAIL = [((664, 600), 104), ((664, 670), 86), ((664, 740), 62), ((664, 800), 40), ((664, 838), 24)]


B_WAIST = 512                  # (the waist's line across the back: shoulders above it, hips below)
B_CAP = 46                     # (a closed end's bulge)
B_HALF_W = 252                 # (the back's half width there)


def back_halves(p0, m):
    import copy
    ys = (np.arange(p0.H) / SS + p0.y0)[:, None]
    xs = (np.arange(p0.W) / SS + p0.x0)[None, :]
    out = {}
    cap = B_CAP * np.sqrt(np.clip(1 - ((xs - MID) / B_HALF_W) ** 2, 0, 1))
    for sym, sgn in (("bshoulder", 1), ("bhips", -1)):
        # (open)
        q = copy.deepcopy(p0)
        if sym == "bshoulder":
            f = np.clip((B_WAIST + 70 - ys) / 50, 0, 1)            # (on under the hips a way, then gone)
        else:
            f = np.clip((ys - (B_WAIST - 40)) / 56, 0, 1)          # (its top fading into the shoulders)
        q.a = q.a * f[..., None]
        out[(sym, "0")] = q
        # (closed: the shoulders' end bulging down, the hips' up)
        q = copy.deepcopy(p0)
        edge = B_WAIST + sgn * cap
        d = sgn * (edge - ys)                                      # (px inside the kept side)
        q.paint(np.clip(1 - d / 80, 0, 1) ** 1.6 * m, SKIN_B, 0.5)
        q.a = q.a * np.clip(d * SS / 1.2 + 0.5, 0, 1)[..., None]
        pts = [(x, B_WAIST + sgn * B_CAP * math.sqrt(max(0.0, 1 - ((x - MID) / B_HALF_W) ** 2)))
               for x in np.linspace(MID - B_HALF_W + 6, MID + B_HALF_W - 6, 26)]
        q.paint(q.stroke(pts, W_INK * 0.85, passes=3) * m, INK)
        out[(sym, "closed")] = q
    return out


def draw_hips_front(save, J):
    """the hips from the front: the back half facing us, behind the chest - its back rising there, darker (further, in
    the chest's shadow), the fin along its spine; the hind legs either side of it and the tail behind are their own"""
    p = Part((400, 330, 930, 700), seed=38)
    pts = [(664, 330), (752, 338), (828, 366), (880, 416), (902, 488), (896, 566), (858, 628), (664, 664),
           (470, 628), (432, 566), (426, 488), (448, 416), (500, 366), (576, 338)]
    m = p.poly(pts)
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B, split=0.4)
    xs = np.arange(p.W)[None, :] / SS + p.x0
    p.paint(m * np.clip((np.abs(xs - MID) - 110) / 120, 0, 1) ** 1.5, SKIN_B, 0.5)
    p.mottle(m)
    p.blobs(m * (p.shift(m, 0, 16) > 0.5) * (np.abs(xs - MID) > 50), 20, 5, 13, (SPOT, SPOT2))
    p.sheen(m, alpha=0.3)
    fin = p.poly([(MID - 8, 334), (MID + 8, 334), (MID + 10, 450), (MID + 6, 560), (MID - 6, 560), (MID - 10, 450)],
                 blur=1.2) * m
    p.grad_fill(fin, V.FIN_T, V.FIN, V.FIN_B)
    for s_ in (-1, 1):
        p.paint(p.stroke([(MID + s_ * 9, 338), (MID + s_ * 11, 450), (MID + s_ * 7, 556)], 2.0, passes=2) * m, INK, 0.8)
    p.paint(p.flicks(pts, m, 4), INK, 0.9)
    p.paint(p.sketch([spline(pts)], m), INK)
    p.a[..., :3] *= np.array([0.86, 0.8, 0.84], np.float32)            # (further back: a little in shade)
    save("fhips", "0", p, J["body"])


def draw_back(k, save, quick=False):
    J = {"body": (664, 500), "head": (664, 420), "leg_bn": B_HIND["pivot"],
         "leg_bf": (2 * MID - B_HIND["pivot"][0], B_HIND["pivot"][1]), "leg_fn": B_FORE["pivot"],
         "leg_ff": (2 * MID - B_FORE["pivot"][0], B_FORE["pivot"][1]), "tail": B_TAIL_ROOT}
    for i, g in enumerate(B_GILLS):
        J[f"gill_l{i}"] = g
        J[f"gill_r{i}"] = (2 * MID - g[0], g[1])
    # --- the back of the head: its eyes' bumps at the top ---
    p = Part((400, 160, 930, 470), seed=41)
    m = p.poly(B_HEAD)
    for s in (1, -1):
        m = np.maximum(m, p.ellipse((MID + s * 150, 214), (44, 30), blur=0.8))
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B, split=0.5)
    p.mottle(m)
    p.blobs(m * (p.shift(m, 0, 14) > 0.5) * (p.shift(m, 0, -20) > 0.5), 12, 4, 10, (SPOT, SPOT2))
    p.sheen(m)
    bumps = [[(MID + s * 150 + 44 * math.cos(a), 214 + 30 * math.sin(a))
              for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)] for s in (1, -1)]
    p.paint(p.sketch([spline(B_HEAD)] + bumps, m, weight=0.3), INK)
    save("bhead", "0", p, J["head"])
    # --- the back: rounder at its sides (darker there), its fin along the spine ---
    p = Part((380, 280, 950, 720), seed=42)
    m = p.poly(B_BODY)
    p.grad_fill(m, SKIN_T, SKIN, SKIN_B, split=0.55)
    xs = np.arange(p.W)[None, :] / SS + p.x0
    p.paint(m * np.clip((np.abs(xs - MID) - 120) / 140, 0, 1) ** 1.5, SKIN_B, 0.55)
    p.mottle(m)
    p.blobs(m * (p.shift(m, 0, 18) > 0.5) * (p.shift(m, 0, -20) > 0.5) * (np.abs(xs - MID) > 70), 30, 5, 14,
            (SPOT, SPOT2))
    p.sheen(m, alpha=0.4)
    fin = p.poly([(MID - 9, 304), (MID + 9, 304), (MID + 13, 500), (MID + 9, 690), (MID - 9, 690), (MID - 13, 500)],
                 blur=1.2)
    p.grad_fill(fin * m, V.FIN_T, V.FIN, V.FIN_B)
    for y in range(320, 680, 22):
        p.paint(p.stroke([(MID - 8, y), (MID, y + 6), (MID + 8, y)], 1.3, passes=1) * fin, V.FIN_RAY, 0.6)
    for s in (-1, 1):
        p.paint(p.stroke([(MID + s * 11, 306), (MID + s * 14, 500), (MID + s * 10, 690)], 2.2, passes=2), INK, 0.85)
    p.paint(p.flicks(B_BODY, m, 5), INK, 0.9)
    p.paint(p.sketch([spline(B_BODY)], m), INK)
    # (cut at the waist: the shoulders (the front half's, going away - higher) and the hips (the back half's, nearer
    #  us - lower, over them). Open: the hips' top fading into the shoulders. Closed: each a round end of its own,
    #  inked - for when the other half has turned to another view)
    for key, part in back_halves(p, m).items():
        sym, var = key
        save(sym, var, part, J["body"])
    # --- the legs: the hind nearest us (left; mirrored), the front peeking out up the sides (darker) ---
    save("bhind", "0", V.draw_leg(leg_spec(B_HIND, crease=B_HIND["crease"]), 43), B_HIND["pivot"])
    fore = V.draw_leg(leg_spec(B_FORE), 44)
    fore.a[..., :3] *= np.array([0.74, 0.6, 0.66], np.float32)
    save("bfore", "0", fore, B_FORE["pivot"])
    # --- the tail, coming toward us: one drawing, bent side to side (its frames) ---
    p = Part((520, 560, 810, 880), seed=45)
    m = p.capsule(B_TAIL)
    yy = (np.arange(p.H) / SS + p.y0)[:, None]
    m = m * np.clip(yy - 600, 0, 1)
    p.grad_fill(m, SKIN, SKIN, SKIN_B, split=0.4)
    xs = np.arange(p.W)[None, :] / SS + p.x0
    p.paint(m * np.clip((np.abs(xs - MID) - 30) / 70, 0, 1), SKIN_B, 0.45)
    p.mottle(m)
    p.blobs(m * (np.abs(xs - MID) > 22) * (p.shift(m, 0, -16) > 0.5), 12, 4, 10, (SPOT, SPOT2))
    fin = p.poly([(MID - 8, 600), (MID + 8, 600), (MID + 6, 840), (MID, 856), (MID - 6, 840)], blur=1.0) * m
    p.grad_fill(fin, V.FIN_T, V.FIN, V.FIN_B)
    for s in (-1, 1):
        p.paint(p.stroke([(MID + s * 9, 610), (MID + s * 7, 740), (MID + s * 3, 850)], 2.0, passes=2) * m, INK, 0.8)
    ink = p.sketch([V.capsule_outline(B_TAIL)], m, w=W_INK * 0.9)
    p.paint(ink * np.clip((yy - 640) / 30, 0, 1), INK)          # (its root: under the back)
    p.a = p.a * np.clip((yy[..., None] - 604) / 36, 0, 1)
    for i, c in enumerate(np.linspace(-1, 1, V.TAIL_N)):
        c = 0.0 if quick else c
        save("btail", str(i), V.bent(p, -c * V.TAIL_BEND * 1.6, root=B_TAIL_ROOT, tip=B_TAIL_TIP, bend_from=70),
             B_TAIL_ROOT)
    return J


def draw(k, save, quick=False):
    return {"front": draw_front(k, save, quick), "back": draw_back(k, save, quick)}
