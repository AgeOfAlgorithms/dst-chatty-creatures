"""The slime's rig and animations, baked into the game's own animation file.

    python tools/anim/rig.py [--preview]      (conda env pcvoice: Pillow, numpy, scipy; Windows, for scml.exe)

The parts are drawings (art/parts: tools/gen made them, an image model drawing in the game's style from the game's
own creatures, then cut out and sized), as Klei's creatures are built: a body drawn in a few shapes (resting,
squashed, stretched, in the air, leaning, coiled, splatted) swapped frame by frame and fine-tuned by a full matrix
(scale, rotation and shear), the face's parts on it (eyes with lids, pupils that look about, mouths), a sprout on its
head (a damped spring its head's motion swings), effects (goo drops thrown off under gravity, splashes, hearts,
notes, Zs). Each animation is a function of time giving a Pose; timed the way the game's are (read from its own
anim files with tools/gen/dstref.py: 30 frames a second, a strong anticipation, a quick move, a held extreme, one
overshoot settling), not a constant wobble.

Out: anim/chattyslime.zip. The build (the parts' atlas) is the Mod Tools' scml.exe's, from a Spriter file listing
every part; the animations are written here (animbin.py), replacing the one scml.exe wrote. The game is four-faced:
every animation has a side version (its face turned toward where it goes, the far eye smaller), a down one (facing
us: its face in the middle, both eyes alike) and an up one (its back to us: no face); hopping and attacking move
differently in each, the rest are posed the same and seen from each side (viewed()).
--preview: build/preview: a GIF of each animation and sheet.png, drawn from the very matrices the game gets."""
import json
import math
import os
import random
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import animbin  # noqa: E402

NAME = "chattyslime"
FPS = 30
ROOT = os.path.dirname(os.path.dirname(HERE))
ART = os.path.join(ROOT, "art", "parts")
EXPORT = os.path.join(ROOT, "exported", NAME)
PREVIEW = os.path.join(ROOT, "build", "preview")
SCML = r"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe"

SIDE, UP, DOWN, ALL = 5, 2, 8, 255

# --- the parts ------------------------------------------------------------------------------------------------------

PARTS = json.load(open(os.path.join(ART, "parts.json")))
for _gone in ("sprout", "seed"):          # (no sprout or seed: just a slime - the user's call; their drawings stay in art)
    PARTS.pop(_gone, None)
FRAME = {s: {k: i for i, k in enumerate(v)} for s, v in PARTS.items()}
SHAPES = {k: v[4] for k, v in PARTS["body"].items()}       # anchors: H, W, top, face, front (from the foot, y up)
REST = SHAPES["rest"]
LADDER = [k for k in ("squash2", "squash", "rest", "stretch", "stretch2") if k in SHAPES]
ALIAS = {"ball": "air", "lunge": "lean", "sag": "squash", "puff": "rest", "puddle_mid": "splat", "puddle": "splat"}
EYE_ALIAS = {"fierce": "angry"}
PUPIL = {"open": 1.0, "wide": 0.62}                        # (the eyes with a pupil of their own: how big)


def draw_parts():
    """every part's drawings copied to exported/chattyslime/<symbol>/<symbol>-<i>.png (for scml.exe);
    {symbol: [(file, w, h, pivot x, y shares)]}"""
    syms = {}
    for s, frames in PARTS.items():
        os.makedirs(os.path.join(EXPORT, s), exist_ok=True)
        syms[s] = []
        for i, (key, (w, h, px, py, _)) in enumerate(frames.items()):
            name = f"{s}/{s}-{i}.png"
            shutil.copyfile(os.path.join(ART, s, f"{key}.png"), os.path.join(EXPORT, name))
            syms[s].append((name, w, h, px, py))
    return syms


# --- a pose and where its parts go ----------------------------------------------------------------------------------

EYE_DX, EYE_DY, MOUTH_DY = 29, 8, -26     # (the face's parts, about the face's middle, on the resting body)
FAR_EYE = 0.9                             # (the far eye - the one on the side it faces, eye_r - smaller: three-quarter)
LOOK = (6.5, 5.0)                         # (how far the pupils go)
TOP_DIP = 6                               # (the sprout's foot, down into the top of its head)


@dataclass
class Pose:
    x: float = 0.0                 # its foot (y up; y > 0 in the air)
    y: float = 0.0
    s: float = 1.0                 # how tall, a share of resting (squashed < 1 < stretched)
    w: float = None                # how wide (left out: what keeps it about as big, s ** -0.6)
    shear: float = 0.0             # the top moved forward by shear x its height (its foot stays)
    rot: float = 0.0               # degrees, anticlockwise ...
    rot_h: float = 90.0            # ... about this high up it
    shape: str = None              # a body drawing (left out: by s, from LADDER)
    eyes: str = "open"
    eyes_r: str = None             # (the near eye, when not the same)
    look: tuple = (0.0, 0.0)       # where it looks (-1..1 across, down..up)
    mouth: str = "smile"
    face: bool = True              # (False: its back to us)
    face_dx: float = 0.0
    far_eye: float = None          # (the far eye's size: left out, FAR_EYE - the three-quarter view the art is in)
    turn: tuple = (1.0, 1.0, 1.0)  # (how far out the near eye and the far eye sit (shares of EYE_DX), the mouth's width:
    #                                 turned toward profile, they close up and the mouth narrows)
    face_dy: float = 0.0
    seed_dx: float = 0.0           # (the seed moved across: facing us or from behind it is in the middle)
    sprout: float = 0.0            # degrees more on the sprout
    wilt: bool = False
    sprout_free: tuple = None      # (x, y, degrees): come off, lying there
    fx: list = field(default_factory=list)


def fx(sym, frame=0, x=0.0, y=0.0, a=0.0, sx=1.0, sy=None, layer="front", local=False, name=None):
    """an effect: symbol and frame at (x, y) (local: on the body, moving with it); layer front, mid (on the body
    under the face) or back"""
    return dict(sym=sym, f=frame, x=x, y=y, a=a, sx=sx, sy=sx if sy is None else sy, layer=layer, local=local,
                name=name or sym)


def rot2(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


def shape_of(p):
    if p.shape:
        return ALIAS.get(p.shape, p.shape)
    return min(LADDER, key=lambda n: abs(math.log(SHAPES[n]["H"] / REST["H"] / max(p.s, 0.05))))


@dataclass
class Body:
    shape: str
    M: np.ndarray
    t: np.ndarray
    V: np.ndarray                  # (the body's posture without the drawing's own size: for things on it)
    face: np.ndarray
    F: np.ndarray
    top: np.ndarray
    top_angle: float
    front: np.ndarray


def body_of(p):
    name = shape_of(p)
    b = SHAPES[name]
    w = p.w if p.w is not None else max(p.s, 0.05) ** -0.6
    sx, sy = w * REST["W"] / b["W"], p.s * REST["H"] / b["H"]
    R = rot2(p.rot)
    Sh = np.array([[1, p.shear], [0, 1]])
    M = R @ Sh @ np.diag([sx, sy])
    piv = np.array([0, p.rot_h * p.s])
    t = np.array([p.x, p.y]) + piv - R @ piv
    V = R @ Sh @ np.diag([w, p.s])
    face = M @ np.array(b["face"]) + t
    fs, fw = 1 + (p.s - 1) * 0.55, 1 + (w - 1) * 0.5
    F = R @ np.array([[1, p.shear * 0.85], [0, 1]]) @ np.diag([fw, fs])
    up = M @ np.array([0.0, 1.0])
    top_angle = math.degrees(math.atan2(-up[0], up[1]))
    top = M @ np.array(b["top"]) + t - up / np.linalg.norm(up) * TOP_DIP
    front = M @ np.array(b["front"]) + t
    return Body(name, M, t, V, face, F, top, top_angle, front)


# --- easing and keys ------------------------------------------------------------------------------------------------

def ease(kind, x):
    x = min(max(x, 0.0), 1.0)
    if kind == "lin":
        return x
    if kind == "in":
        return x * x
    if kind == "out":
        return 1 - (1 - x) ** 2
    if kind == "out3":
        return 1 - (1 - x) ** 3
    if kind == "back":                                   # (out, overshooting a little)
        c = 1.7
        return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
    if kind == "hold":
        return 0.0 if x < 1 else 1.0
    return x * x * (3 - 2 * x)                           # io


def keys(t, *ks):
    """keys (time, value[, easing into it]): the value at t"""
    if t <= ks[0][0]:
        return ks[0][1]
    for a, b in zip(ks, ks[1:]):
        if t <= b[0]:
            e = b[2] if len(b) > 2 else "io"
            return a[1] + (b[1] - a[1]) * ease(e, (t - a[0]) / (b[0] - a[0]))
    return ks[-1][1]


def settle(t, t0, amp, period=0.22):
    """one overshoot and back from t0 (the game's way: a bounce or two, not a buzz)"""
    if t < t0:
        return 0.0
    u = (t - t0) / period
    return amp * math.exp(-2.2 * u) * math.cos(math.pi * u) if u < 2.5 else 0.0


def blink(t, t0, base="open"):
    u = t - t0
    if 0 <= u < 0.034 or 0.1 <= u < 0.134:
        return "half"
    if 0.034 <= u < 0.1:
        return "closed"
    return base


def arc_y(t, t0, t1, h):
    if t <= t0 or t >= t1:
        return 0.0
    u = (t - t0) / (t1 - t0)
    return 4 * h * u * (1 - u)


def pop(t, t0, t1, grow=0.12, shrink=0.12):
    """an effect's size: popping in at t0, out by t1"""
    if t < t0 or t > t1:
        return 0.0
    return ease("back", (t - t0) / grow) * (1 - ease("in", (t - (t1 - shrink)) / shrink) if t > t1 - shrink else 1)


def splash_fx(t, t0, x=0.0, life=0.3, size=1.0):
    """the landing splash: a ring of goo round its foot (back half behind the body, front half before it), spreading
    out from under it and thinning to blobs (its frames); the droplets flung off its rim are RIM emits"""
    life *= 1.4
    if t < t0 or t > t0 + life or "splash" not in FRAME:
        return []
    u = (t - t0) / life
    sc = size * (1.0 + 0.5 * ease("out", u))
    f = min(3, int(u * 4))
    sy = sc * (0.75 + 0.25 * ease("out", min(1.0, u / 0.25)))
    return [fx("splash", f, x, 0, sx=sc, sy=sy, layer="back"),
            fx("splash_front", f, x, 0, sx=sc, sy=sy, layer="front")]


def rim_emits(t0, n=4, v=(170, 280)):
    """droplets flung low off the splash's rim, half each way"""
    return [(t0 + 0.01, n - n // 2, "rim", (12, 40), v), (t0 + 0.01, n // 2, "rim", (140, 168), v)]


# --- the animations ---------------------------------------------------------------------------------------------------

def breath(t, period, amp=0.025):
    return 1 + amp * math.sin(2 * math.pi * t / period)


def idle(t):
    ph = 2 * math.pi * t / 2.4
    return Pose(s=breath(t, 2.4), shear=0.018 * math.sin(ph + 0.8), eyes=blink(t, 1.7))


def idle_look(t):
    lx = keys(t, (0, 0), (0.17, -1, "out"), (1.0, -1), (1.13, 0, "in"), (1.3, 0), (1.47, 1, "out"), (2.3, 1),
              (2.47, 0, "in"))
    ly = keys(t, (0, 0), (0.17, 0.25, "out"), (1.0, 0.25), (1.13, 0), (1.47, -0.2), (2.3, -0.2), (2.47, 0))
    eyes = blink(t, 1.2, blink(t, 2.55))
    return Pose(s=breath(t, 1.5, 0.015) + settle(t, 2.5, 0.05), shear=0.05 * lx, look=(lx, ly),
                face_dx=6 * lx, eyes=eyes, mouth="smile" if abs(lx) < 0.5 else "flat")


HOP_LIFT, HOP_LAND = 0.15, 0.52


def hop(view):
    def f(t):
        side = view == SIDE
        s = keys(t, (0, 1), (0.1, 0.72, "out"), (0.133, 0.72), (0.18, 1.3, "out"), (0.27, 1.02), (0.47, 1.1, "in"),
                 (0.533, 0.68, "out"), (0.567, 0.68), (0.633, 1.07, "out"), (0.7, 1.0))
        sh = keys(t, (0, 0), (0.1, -0.07), (0.18, 0.12, "out"), (0.3, 0.02), (0.47, -0.03), (0.533, 0.06, "out"),
                  (0.633, -0.02), (0.7, 0))
        y = arc_y(t, HOP_LIFT, HOP_LAND, 56)
        eyes = "half" if t < 0.14 else ("squeeze" if 0.52 <= t < 0.6 else "open")
        mouth = "flat" if t < 0.14 else ("o" if t < 0.5 else "smile")
        shape = None
        if 0.21 <= t < 0.45:
            shape = "air"
        elif 0.15 <= t < 0.21 or 0.45 <= t < 0.52:
            shape = "stretch"
        p = Pose(s=s, y=y, shear=sh if side else 0.0, rot=keys(t, (0.15, 0), (0.3, -7), (0.5, 0)) if side else 0,
                 eyes=eyes, mouth=mouth, face=view != UP, shape=shape,
                 look=(0.4, -0.3) if side and 0.3 < t < 0.5 else (0, 0))
        if view == DOWN:
            p.face_dy = keys(t, (0, 0), (0.1, -4), (0.3, -2), (0.533, -5), (0.7, 0))
        return p
    return f


HOP_EMITS = rim_emits(HOP_LAND)

TALK = ["talk", "talk_wide", "smile", "o", "talk", "grin", "talk", "smile", "talk_wide", "talk", "o", "smile"]
TALK_AMP = {"talk": 0.03, "talk_wide": 0.05, "o": 0.035, "grin": 0.045, "smile": 0.0}


def talk(t):
    i = int(t / 0.1) % len(TALK)
    m = TALK[i]
    u = t - int(t / 0.1) * 0.1
    s = breath(t, 1.2, 0.012) + TALK_AMP[m] * math.exp(-u * 20) - 0.01
    eyes = "happy" if m == "grin" else blink(t, 0.77)
    return Pose(s=s, shear=0.025 * math.sin(2 * math.pi * t / 1.2), mouth=m, eyes=eyes)


def think(t):
    bub = []
    for k, (x0, y0, x1, y1) in enumerate(((-34, 150, -24, 250), (38, 140, 46, 236))):
        u = ((t / 1.6) + k * 0.5) % 1.0
        sc = (0.6 + 0.6 * u) * min(1, u / 0.1) * min(1, (1 - u) / 0.12)
        bub.append(fx("bubble", 0, x0 + (x1 - x0) * u + 3 * math.sin(u * 9), y0 + (y1 - y0) * u, sx=sc,
                      name=f"bubble{k}"))
    return Pose(s=breath(t, 1.6, 0.015), shear=0.03 * math.sin(2 * math.pi * t / 1.6), look=(0.6, 0.8), face_dx=3,
                face_dy=2, eyes=blink(t, 1.1), mouth="flat" if t < 0.8 else "wavy", fx=bub)


def happy(t):
    s = keys(t, (0, 1), (0.1, 0.72, "out"), (0.133, 0.72), (0.18, 1.32, "out"), (0.3, 1.0), (0.53, 1.1, "in"),
             (0.6, 0.7, "out"), (0.633, 0.7), (0.7, 1.08, "out"), (0.8, 1.0), (0.9, 0.86, "out"), (0.97, 1.08, "out"),
             (1.1, 1.0))
    y = arc_y(t, 0.14, 0.6, 80) + arc_y(t, 0.93, 1.12, 18)
    rot = -360 * ease("io", (t - 0.2) / 0.33) if t > 0.2 else 0
    hearts = []
    for k, (t0, x0, y0, dx) in enumerate(((0.62, 40, 230, 24), (0.78, -44, 220, -22))):
        sc = pop(t, t0, 1.4)
        if sc > 0:
            u = t - t0
            hearts.append(fx("heart", 0, x0 + dx * u, y0 + 80 * u, a=-12 * (dx > 0) + 8, sx=sc, name=f"heart{k}"))
    shape = "air" if 0.21 <= t < 0.53 else ("stretch" if 0.15 <= t < 0.21 else None)
    return Pose(s=s, y=y, rot=rot % 360 if rot else 0, eyes="happy" if t < 1.32 else "open", mouth="grin",
                shape=shape, fx=hearts)                    # (no landing splash: it lands soft, 2026-11-05)


def sad(t):
    s = keys(t, (0, 1), (0.5, 0.84), (1.5, 0.84), (2.0, 1.0)) + settle(t, 0.9, -0.03) + settle(t, 1.25, -0.025)
    w = keys(t, (0, 1), (0.5, 1.1), (1.5, 1.1), (2.0, 1.0))
    return Pose(s=s, w=w, shape="squash" if 0.3 <= t < 1.7 else None, eyes="sad" if 0.1 <= t < 1.8 else "open",
                mouth="frown" if 0.1 <= t < 1.85 else "smile", wilt=0.3 <= t < 1.72,
                face_dy=keys(t, (0, 0), (0.5, -6), (1.5, -6), (2.0, 0)),
                look=(0, keys(t, (0, 0), (0.5, -0.6), (1.5, -0.6), (2.0, 0))))


def surprised(t):
    s = keys(t, (0, 1), (0.067, 0.84, "out"), (0.167, 1.4, "out"), (0.3, 1.18), (0.367, 0.8, "in"))
    if t > 0.367:
        s = 1 + settle(t, 0.367, -0.2, 0.25)
    y = keys(t, (0, 0), (0.067, 0), (0.18, 26, "out"), (0.34, 0, "in"))
    eyes = "wide" if 0.05 <= t < 0.9 else blink(t, 1.0)
    shape = "stretch" if 0.1 <= t < 0.3 else None
    return Pose(s=s, y=y, eyes=eyes, mouth="o" if 0.05 <= t < 0.95 else "smile", shape=shape,
                fx=splash_fx(t, 0.34, life=0.25))


def angry(t):
    s = keys(t, (0, 1), (0.2, 1.06), (1.3, 1.06), (1.55, 1.0)) + settle(t, 0.55, -0.07, 0.15) + settle(t, 0.95, -0.07, 0.15)
    w = keys(t, (0, 1), (0.2, 1.14), (1.3, 1.14), (1.55, 1.0))
    x = 2.5 * math.sin(2 * math.pi * 15 * t) if 0.2 < t < 1.25 else 0
    sc = pop(t, 0.2, 1.32)
    # (the anger mark - the comic popping vein - on its brow, throbbing: a sharp swell each beat, easing back)
    ph = ((t - 0.2) % 0.36) / 0.36
    throb = 0.94 + 0.24 * math.exp(-ph * 7) * (t > 0.3)
    scr = [fx("vein", 0, 46 + x, 232, a=-6 + 3 * math.sin(t * 23), sx=sc * throb)] if sc > 0 else []
    return Pose(s=s, w=w, x=x, eyes="angry" if 0.08 <= t < 1.45 else "open",
                mouth="wavy" if 0.3 <= t < 1.2 else ("frown" if 0.08 <= t < 1.45 else "smile"), fx=scr)


def dance(t):
    b = t / 0.4
    p = b - int(b)
    n = int(b)
    s = 1 - 0.13 * math.exp(-p * 12) + 0.05 * math.sin(math.pi * p)
    y = 14 * math.sin(math.pi * p) ** 1.5
    rot = 6 * math.sin(math.pi * b)
    if 1.6 <= t < 2.0:
        u = (t - 1.6) / 0.4
        rot += -360 * ease("io", u)
        y += 40 * math.sin(math.pi * u)
    notes = []
    for k, t0 in enumerate((0.0, 0.8, 1.6)):
        sc = pop(t, t0 + 0.05, t0 + 0.85)
        if sc > 0:
            u = t - t0
            sgn = 1 if k % 2 == 0 else -1
            notes.append(fx("note", 0, sgn * (60 + 18 * u), 210 + 70 * u, a=-sgn * 10 + 12 * math.sin(u * 8),
                            sx=sc, name=f"note{k}"))
    return Pose(s=s, y=y, shear=0.12 * math.sin(math.pi * b), rot=rot % 360, eyes="happy",
                shape="air" if 1.64 <= t < 1.96 else None, mouth="grin" if n % 2 == 0 else "smile", fx=notes)


def eat(t):
    s = keys(t, (0, 1), (0.233, 1.12), (0.267, 1.12), (0.333, 0.8, "out"), (0.433, 1.0))
    if 0.433 <= t < 1.0:
        s = 1 + 0.03 * math.sin(2 * math.pi * (t - 0.433) / 0.167)
    if t >= 1.0:
        s = 1 + settle(t, 1.0, 0.05)
    sh = keys(t, (0, 0), (0.233, -0.05), (0.333, 0.03), (0.5, 0))
    if t < 0.3:
        mouth = "gape" if t >= 0.067 else "o"
    elif t < 1.0:
        mouth = "chomp" if int((t - 0.3) / 0.1) % 2 == 0 else "wavy"
    else:
        mouth = "smile"
    eyes = "open" if t < 0.3 else ("squeeze" if t < 0.433 else "happy")
    lump = []
    if 0.31 <= t < 1.4:
        u = (t - 0.31) / 1.0
        sc = keys(t, (0.31, 0.6), (0.36, 1.0, "out"), (1.25, 0.55), (1.4, 0.0, "in"))
        lump = [fx("lump", 0, 2 * math.sin(u * 6), keys(t, (0.31, 75), (1.3, 30)), sx=sc, layer="back", local=True)]
    hearts = []
    sc = pop(t, 1.1, 1.6)
    if sc > 0:
        hearts = [fx("heart", 0, 36, 230 + 50 * (t - 1.1), a=-8, sx=sc * 0.9)]
    return Pose(s=s, shear=sh, mouth=mouth, eyes=eyes, look=(0, -0.7) if t < 0.3 else (0, 0), fx=lump + hearts)


def hit(t):
    s = keys(t, (0, 0.72), (0.1, 1.08, "out"), (0.2, 0.96), (0.3, 1.0))
    sh = keys(t, (0, -0.16), (0.1, 0.06, "out"), (0.2, -0.02), (0.3, 0))
    x = keys(t, (0, -10), (0.25, 0, "out"))
    return Pose(s=s, x=x, shear=sh, shape="squash" if t < 0.067 else None, eyes="squeeze" if t < 0.3 else "open",
                mouth="wavy" if t < 0.36 else "smile")


def death(t):
    if t < 0.3:
        s = 1 + 0.04 * math.sin(2 * math.pi * 9 * t)
        x = 3 * math.sin(2 * math.pi * 14 * t)
    else:
        s = keys(t, (0.3, 1.0), (0.433, 1.18, "out"), (0.6, 0.55, "in"), (0.75, 0.32, "out"), (1.0, 0.22))
        x = 0
    w = None if t < 0.433 else keys(t, (0.433, 0.92), (0.6, 1.25), (0.75, 1.4), (1.0, 1.5))
    shape = "stretch" if 0.36 <= t < 0.5 else ("splat" if t >= 0.6 else None)
    free = None
    if t >= 0.6:
        u = min(1.0, (t - 0.6) / 0.42)
        free = (10 + 64 * u, keys(t, (0.6, 140), (0.78, 210, "out"), (1.02, 14, "in")), -115 * ease("io", u))
    return Pose(s=s, w=w, x=x, shape=shape, eyes="squeeze" if t < 0.22 else "dead", mouth="wavy" if t < 0.7 else "flat",
                face_dy=keys(t, (0.6, 0), (1.0, -4)), face=t < 0.62, sprout_free=free,
                fx=splash_fx(t, 0.62, life=0.35, size=1.12))


def sleep_pre(t):
    return Pose(s=keys(t, (0, 1), (0.45, 0.88)), w=keys(t, (0, 1), (0.45, 1.06)),
                eyes="open" if t < 0.1 else ("half" if t < 0.3 else "closed"), mouth="smile" if t < 0.3 else "flat",
                wilt=t >= 0.4, face_dy=keys(t, (0, 0), (0.45, -4)))


def sleep_loop(t):
    ph = 2 * math.pi * t / 3.0
    zs = []
    for k in range(3):
        u = ((t - k * 1.0) % 3.0) / 2.0
        if u <= 1:
            sc = (0.45 + 0.55 * u) * min(1, u / 0.12) * min(1, (1 - u) / 0.15)
            zs.append(fx("zzz", 0, 50 + 30 * u + 6 * math.sin(u * 7), 190 + 90 * u, a=-10 + 14 * math.sin(u * 5),
                         sx=sc * 0.8, name=f"zzz{k}"))
    return Pose(s=0.88 + 0.03 * math.sin(ph), w=1.06 - 0.02 * math.sin(ph), eyes="closed", mouth="flat", wilt=True,
                face_dy=-4, fx=zs)


def sleep_pst(t):
    s = keys(t, (0, 0.88), (0.233, 1.2, "out"), (0.4, 0.95), (0.5, 1.02), (0.6, 1.0))
    w = None if t > 0.233 else keys(t, (0, 1.06), (0.233, 0.9))
    return Pose(s=s, w=w, eyes="closed" if t < 0.3 else ("half" if t < 0.42 else "open"),
                mouth="yawn" if 0.05 <= t < 0.36 else ("flat" if t < 0.05 else "smile"), wilt=t < 0.2,
                sprout=keys(t, (0.2, 18), (0.24, 0)), face_dy=keys(t, (0, -4), (0.233, 2), (0.6, 0)))


ATK_HIT = 0.42


def attack(view):
    def f(t):
        side = view == SIDE
        # (coiled back, trembling; a lunge, mouth gaping; the chomp at ATK_HIT, held; slid back)
        s = keys(t, (0, 1), (0.2, 0.8, "out"), (0.267, 0.8), (0.333, 1.14, "out"), (0.4, 1.06), (0.433, 0.76, "out"),
                 (0.5, 0.76))
        if t > 0.5:
            s = keys(t, (0.5, 0.76), (0.6, 1.05, "out"), (0.7, 0.98), (0.8, 1.0))
        reach = keys(t, (0, 0), (0.2, -0.15, "out"), (0.267, -0.15), (0.367, 1.0, "out"), (0.5, 1.0), (0.85, 0.0))
        tremble = 1.6 * math.sin(2 * math.pi * 18 * t) if 0.1 < t < 0.26 else 0
        y = arc_y(t, 0.27, 0.43, 22)
        if t < 0.27:
            mouth = "frown"
        elif t < ATK_HIT:
            mouth = "gape"
        elif t < 0.85:
            mouth = "chomp" if t < 0.6 else "frown"
        else:
            mouth = "smile"
        eyes = "angry" if t < 0.85 else "open"
        p = Pose(s=s, eyes=eyes, mouth=mouth, face=view != UP)
        if side:
            p.x = 66 * reach + tremble
            p.y = y
            p.shear = keys(t, (0, 0), (0.2, -0.12), (0.333, 0.18, "out"), (0.45, 0.18), (0.5, 0.08), (0.8, 0))
            if 0.08 <= t < 0.27:
                p.shape = "coil"
            elif 0.27 <= t < 0.433:
                p.shape = "lean"
            p.fx = splash_fx(t, 0.44, x=66)
            p.look = (1, 0)
        else:
            k = 1 if view == UP else -1
            p.x = tremble
            p.y = k * 30 * max(reach, 0) + (y if view == UP else 0)
            near = 1 + (-0.08 if view == UP else 0.12) * max(reach, 0)
            p.s *= near
            p.w = max(s, 0.05) ** -0.6 * near
            if view == DOWN:
                p.face_dy = -5 * max(reach, 0)
            p.fx = splash_fx(t, 0.44, x=0)
        return p
    return f


ATK_EMITS = {SIDE: [(ATK_HIT + 0.01, 3, "front", (5, 80), (180, 330))] + rim_emits(0.44),
             UP: [(ATK_HIT + 0.01, 3, "top", (40, 140), (180, 300))] + rim_emits(0.44),
             DOWN: [(ATK_HIT + 0.01, 3, "mouth", (20, 160), (180, 320))] + rim_emits(0.44)}

# (how each facing sees the same pose: the side turns its face toward where it goes; facing us, it is in the middle;
#  from behind there is none)
VIEW_FACE = {SIDE: dict(dx=26.0, far=0.0, turn=(0.75, 0.5, 0.74)),   # (in profile: the face at its front, one eye)
              DOWN: dict(dx=-34.0, far=1.0)}   # (the face sits 40 px right of the middle)


def viewed(fn, view):
    def f(t):
        p = fn(t)
        if view == UP:
            p.face = False
        elif view in VIEW_FACE:
            p.face_dx += VIEW_FACE[view]["dx"]
            p.far_eye = VIEW_FACE[view]["far"]
            p.turn = VIEW_FACE[view].get("turn", p.turn)
            if view == DOWN:
                p.shear *= 0.3                  # (it leans toward where it goes: less of that facing us)
        if view in (UP, DOWN):
            p.seed_dx = -REST.get("seed", (0, 0))[0]
        return p
    return f


FACE_EMITS = ("eye_l", "eye_r", "mouth", "pupil_l", "pupil_r")


def every_view(fn, emits):
    """the pose seen from each side; from behind, nothing comes from its face (tears, crumbs)"""
    return {v: (viewed(fn, v), [e for e in emits if v != UP or e[2] not in FACE_EMITS]) for v in (SIDE, UP, DOWN)}


# name: (length, looping, {facing: (pose function, emits)})
ANIMS = {
    "idle": (2.4, True, every_view(idle, [])),
    "idle_look": (3.0, False, every_view(idle_look, [])),
    "hop": (0.7, False, {v: (viewed(hop(v), v), HOP_EMITS) for v in (SIDE, UP, DOWN)}),
    "talk": (1.2, True, every_view(talk, [])),
    "think": (1.6, True, every_view(think, [])),
    "happy": (1.4, False, every_view(happy, [])),
    "sad": (2.0, False, every_view(sad, [(0.75, 1, "eye_l", (250, 290), (20, 50))])),
    "surprised": (1.2, False, every_view(surprised, [(0.13, 2, "top", (50, 130), (180, 300))] + rim_emits(0.34, 2))),
    "angry": (1.6, False, every_view(angry, [])),
    "dance": (2.4, False, every_view(dance, [])),
    "eat": (1.6, False, every_view(eat, [(0.32, 2, "mouth", (30, 150), (110, 200))])),
    "attack": (1.0, False, {v: (viewed(attack(v), v), ATK_EMITS[v]) for v in (SIDE, UP, DOWN)}),
    "hit": (0.5, False, every_view(hit, [(0.02, 4, "top", (95, 170), (200, 380))])),
    "death": (1.6, False, every_view(death, [(0.62, 4, "top", (20, 160), (220, 420))] + rim_emits(0.62, 4, (200, 320)))),
    "sleep_pre": (0.6, False, every_view(sleep_pre, [])),
    "sleep_loop": (3.0, True, every_view(sleep_loop, [])),
    "sleep_pst": (0.6, False, every_view(sleep_pst, [])),
}

# --- baking: the physics and the elements of each frame -------------------------------------------------------------

GRAVITY = 1900.0
RIM_X = 140.0                    # (the splash ring's half width, about, where its droplets fly from)


class Spring:
    def __init__(self, hz, damping, dims=1):
        self.k = (2 * math.pi * hz) ** 2
        self.d = 2 * damping * 2 * math.pi * hz
        self.x = np.zeros(dims)
        self.v = np.zeros(dims)

    def step(self, force, dt, sub=6):
        h = dt / sub
        for _ in range(sub):
            a = -self.k * self.x - self.d * self.v + force
            self.v = self.v + a * h
            self.x = self.x + self.v * h
        return self.x


def elements(p, b, st):
    """the frame's elements, front first: (symbol, frame, layer, M (2 x 2, y up), t)"""
    front, mid, back = [], [], []
    for e in p.fx:
        if e["sym"] not in FRAME:
            continue
        M = rot2(e["a"]) @ np.diag([e["sx"], e["sy"]])
        pos = np.array([e["x"], e["y"]])
        if e["local"]:
            pos = b.V @ pos + b.t
            M = b.V @ M
        {"front": front, "mid": mid, "back": back}[e["layer"]].append((e["sym"], e["f"], e["name"], M, pos))
    for i, d in enumerate(st["drops"]):
        sym = "drop" if d["f"] < 2 or "puddle" not in FRAME else "puddle"
        (front if d["front"] else back).append((sym, 0, f"drop{i % 12}", d["M"], d["p"]))
    out = list(front)
    if p.face:
        fpos = b.face + b.F @ np.array([p.face_dx, p.face_dy])
        lx, ly = p.look
        Fm = b.F @ np.diag([p.turn[2], 1.0])
        out.append(("mouth", FRAME["mouth"][p.mouth], "mouth", Fm, fpos + b.F @ np.array([lx * 3, MOUTH_DY + ly * 2])))
        eyes = []
        far = FAR_EYE if p.far_eye is None else p.far_eye
        # (turned to face right, the eye on its right is the far one: smaller, and narrowed as it turns away)
        for sym, sx, kind, size in (("eye_l", -1, p.eyes, 1.0), ("eye_r", 1, p.eyes_r or p.eyes, far)):
            if size <= 0:
                continue                   # (in profile the far eye is hidden behind the body)
            kind = EYE_ALIAS.get(kind, kind)
            pos = fpos + b.F @ np.array([sx * EYE_DX * (p.turn[0] if sx < 0 else p.turn[1]) + lx * 4, EYE_DY + ly * 3])
            Fe = b.F @ np.diag([size * (1 - 1.4 * (1 - size)), size]) if size < 1 else b.F
            if kind in PUPIL:
                out.append(("pupil", 0, f"pupil_{sym[-1]}", Fe * PUPIL[kind],
                            pos + Fe @ np.array([lx * LOOK[0], ly * LOOK[1]])))
            eyes.append((sym, FRAME[sym][kind], sym, Fe, pos))
        out += eyes
    out += mid
    seed_at = SHAPES[b.shape].get("seed")
    if seed_at and "seed" in FRAME:
        # (the seed: rigid inside the jelly - it turns with the body but is never squashed or stretched with it)
        out.append(("seed", 0, "seed", rot2(p.rot), b.M @ np.array([seed_at[0] + p.seed_dx, seed_at[1]]) + b.t))
    out.append(("body", FRAME["body"][b.shape], "body", b.M, b.t))
    sf = FRAME["sprout"]["wilt" if p.wilt else "up"] if "sprout" in FRAME else None
    if sf is None:
        pass
    elif p.sprout_free:
        x, y, a = p.sprout_free
        out.insert(0, ("sprout", sf, "sprout", rot2(a), np.array([x, y])))   # (come off: it lies over the puddle)
    else:
        ang = b.top_angle + p.sprout + float(st["sprout"].x[0])
        squish = 1 + float(np.clip(st["squish"].x[0], -0.2, 0.2))
        out.append(("sprout", sf, "sprout", rot2(ang) @ np.diag([1 / math.sqrt(squish), squish]), b.top))
    out += back
    return out


def emit_at(where, p, b, els):
    if where == "base":
        return np.array([p.x, p.y + 14])
    if where == "top":
        return b.top
    if where == "front":
        return b.front
    for sym, f, layer, M, t in els:
        if layer == where:
            return t
    return b.face


def bake(fn, length, looping, emits, seed=1):
    """the frames of an animation: [(pose, body, elements)]"""
    n = int(round(length * FPS))
    dt = 1.0 / FPS
    st = {"sprout": Spring(2.4, 0.25), "squish": Spring(4.0, 0.35), "drops": []}
    sprout_spr, squish_spr = st["sprout"], st["squish"]
    rnd = random.Random(seed)
    particles = []
    passes = 3 if looping else 1
    hist = []
    out = []
    for pas in range(passes):
        for i in range(n):
            t = i * dt
            p = fn(t)
            b = body_of(p)
            hist.append(b.top.copy())
            if len(hist) > 3:
                hist.pop(0)
            acc = (hist[-1] - 2 * hist[-2] + hist[-3]) / dt ** 2 if len(hist) == 3 else np.zeros(2)
            acc = np.clip(acc, -6000, 6000)
            if p.sprout_free:
                sprout_spr.x[:] = 0
                sprout_spr.v[:] = 0
            sprout_spr.step(np.array([0.006 * acc[0]]) * sprout_spr.k, dt)
            sprout_spr.x = np.clip(sprout_spr.x, -40, 40)
            squish_spr.step(np.array([-0.00005 * acc[1]]) * squish_spr.k, dt)
            if pas == passes - 1:
                for (te, cnt, where, (a0, a1), (v0, v1)) in emits:
                    if t - dt / 2 < te <= t + dt / 2:
                        els0 = elements(p, b, {**st, "drops": []})
                        origin = emit_at(where, p, b, els0)
                        for _ in range(cnt):
                            a = math.radians(rnd.uniform(a0, a1))
                            v = rnd.uniform(v0, v1)
                            o = origin
                            big = 1.0
                            if where == "rim":         # (off the ring's rim, on the side it flies to; fatter drops)
                                o = np.array([p.x + math.copysign(RIM_X, math.cos(a)), 6.0])
                                big = 1.5
                            particles.append(dict(p=o + np.array([rnd.uniform(-8, 8), rnd.uniform(-4, 4)]),
                                                  v=np.array([math.cos(a) * v, math.sin(a) * v]),
                                                  size=big * rnd.uniform(0.7, 1.1), front=rnd.random() < 0.6, splat=None))
            drops = []
            for d in particles:
                if d["splat"] is None:
                    d["v"][1] -= GRAVITY * dt
                    d["p"] = d["p"] + d["v"] * dt
                    if d["p"][1] <= 0 and d["v"][1] < 0:
                        d["p"][1] = 0
                        d["splat"] = 0.0
                if d["splat"] is not None:
                    d["splat"] += dt
                    k = max(0.0, 1 - d["splat"] / 0.35)
                    if k > 0:
                        drops.append(dict(f=2, p=d["p"].copy(),
                                          M=np.diag([d["size"] * 0.16 * (0.6 + 0.5 * k), d["size"] * 0.2 * k]),
                                          front=d["front"]))
                    continue
                sp = float(np.hypot(*d["v"]))
                stretch = min(1.8, 1 + sp / 1300)
                ang = math.degrees(math.atan2(-d["v"][0], d["v"][1]))
                M = rot2(ang + 180) @ np.diag([d["size"] / math.sqrt(stretch), d["size"] * stretch])
                drops.append(dict(f=1, p=d["p"].copy(), M=M, front=d["front"]))
            if pas == passes - 1:
                stf = {"sprout": sprout_spr, "squish": squish_spr, "drops": drops}
                out.append((p, b, elements(p, b, stf)))
    return out


def to_bin(els, syms):
    """elements as anim.bin wants them (y down) and the frame's bounding box"""
    rows = []
    xs, ys = [], []
    for sym, f, layer, M, t in els:
        a, c, b_, d = M[0, 0], -M[0, 1], -M[1, 0], M[1, 1]
        tx, ty = t[0], -t[1]
        rows.append((sym, int(f), layer, a, b_, c, d, tx, ty))
        _, w, h, px, py = syms[sym][f]
        for cx, cy in ((-px * w, (py - 1) * h), ((1 - px) * w, (py - 1) * h), (-px * w, py * h), ((1 - px) * w, py * h)):
            wx, wy = M @ np.array([cx, cy]) + t
            xs.append(wx)
            ys.append(-wy)
    if not xs:
        return (0, 0, 1, 1), rows
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return ((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0), rows


def all_baked():
    out = []
    for name, (length, looping, views) in ANIMS.items():
        for facing, (fn, emits) in views.items():
            out.append((name, facing, looping, bake(fn, length, looping, emits, seed=animbin.khash(name) % 1000)))
    return out


# --- the build (scml.exe) and the animations (ours) -----------------------------------------------------------------

def write_scml(syms):
    """a Spriter file listing every part (one throwaway animation showing them all): what scml.exe builds from.
    Spriter's pivot_y is from the bottom"""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<spriter_data scml_version="1.0" generator="BrashMonkey Spriter" generator_version="b5">']
    order = list(syms)
    for fi, s in enumerate(order):
        out.append(f'  <folder id="{fi}" name="{s}">')
        for i, (name, w, h, px, py) in enumerate(syms[s]):
            out.append(f'    <file id="{i}" name="{name}" width="{w}" height="{h}" pivot_x="{px:.6f}" '
                       f'pivot_y="{1 - py:.6f}"/>')
        out.append("  </folder>")
    n = max(len(v) for v in syms.values())
    out.append(f'  <entity id="0" name="{NAME}">')
    out.append(f'    <animation id="0" name="parts" length="{n * 25}" interval="25" looping="false">')
    out.append("      <mainline>")
    for k in range(n):
        out.append(f'        <key id="{k}" time="{k * 25}">')
        for ti, s in enumerate(order):
            out.append(f'          <object_ref id="{ti}" timeline="{ti}" key="{k}" z_index="{ti}"/>')
        out.append("        </key>")
    out.append("      </mainline>")
    for ti, s in enumerate(order):
        out.append(f'      <timeline id="{ti}" name="{s}">')
        for k in range(n):
            f = min(k, len(syms[s]) - 1)
            out.append(f'        <key id="{k}" time="{k * 25}"><object folder="{ti}" file="{f}" x="0" y="0" '
                       f'angle="0" scale_x="1" scale_y="1"/></key>')
        out.append("      </timeline>")
    out.append("    </animation>")
    out.append("  </entity>")
    out.append("</spriter_data>")
    path = os.path.join(EXPORT, f"{NAME}.scml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


def compile_anim(syms, baked):
    scml = write_scml(syms)
    r = subprocess.run([SCML, scml, ROOT], capture_output=True, text=True)
    log = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or "ERROR" in log or "WARNING" in log:
        raise SystemExit("scml.exe:\n" + log)
    zpath = os.path.join(ROOT, "anim", f"{NAME}.zip")
    tmp = os.path.join(ROOT, "build", "zip")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
        infos = {i.filename: i.compress_type for i in z.infolist()}
    anims = []
    for name, facing, looping, frames in baked:
        anims.append((name, facing, float(FPS), [to_bin(els, syms) for _, _, els in frames]))
    animbin.write(os.path.join(tmp, "anim.bin"), NAME, anims)
    with zipfile.ZipFile(zpath, "w") as z:
        for fn, ct in infos.items():
            z.write(os.path.join(tmp, fn), fn, compress_type=ct)
    return zpath


# --- previews -------------------------------------------------------------------------------------------------------

def render(els, syms, images, size=(320, 320), ground=40, scale=1.0, bg=(214, 200, 160, 255), shadow=True, cx=None):
    """a frame as the game draws it: each part through its matrix (y up here; the game's is the same flipped)"""
    im = Image.new("RGBA", size, bg)
    ox, oy = (size[0] / 2 if cx is None else cx), size[1] - ground
    if shadow:
        d = ImageDraw.Draw(im)
        d.ellipse((ox - 95 * scale, oy - 18 * scale, ox + 95 * scale, oy + 18 * scale), fill=(176, 160, 122, 255))
    for sym, f, layer, M, t in reversed(els):
        name, w, h, px, py = syms[sym][f]
        img = images[name]
        k = img.width / w
        # screen = S (M (J q + j0) + t) + o, q the image pixel (from the top left); PIL wants the inverse
        J = np.array([[1 / k, 0], [0, -1 / k]])
        j0 = np.array([-px * w, py * h])
        Sf = np.array([[scale, 0], [0, -scale]])
        A = Sf @ M @ J
        bvec = Sf @ (M @ j0 + t) + np.array([ox, oy])
        try:
            Ai = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            continue
        bi = -Ai @ bvec
        part = img.transform(size, Image.AFFINE, (Ai[0, 0], Ai[0, 1], bi[0], Ai[1, 0], Ai[1, 1], bi[1]),
                             resample=Image.BICUBIC)
        im.alpha_composite(part)
    return im


def previews(syms, baked):
    os.makedirs(PREVIEW, exist_ok=True)
    for f in os.listdir(PREVIEW):
        if f.endswith(".gif"):
            os.remove(os.path.join(PREVIEW, f))
    images = {name: Image.open(os.path.join(EXPORT, name)).convert("RGBA") for fs in syms.values() for name, *_ in fs}
    rows = []
    tag = {ALL: "", SIDE: "_side", UP: "_up", DOWN: "_down"}
    for name, facing, looping, frames in baked:
        gif = [render(els, syms, images, size=(500, 420), ground=60, cx=210) for _, _, els in frames]
        gif[0].save(os.path.join(PREVIEW, f"{name}{tag[facing]}.gif"), save_all=True, append_images=gif[1:],
                    duration=1000 // FPS, loop=0, disposal=2)
        pick = [gif[int(i * (len(gif) - 1) / 9)] for i in range(10)]
        rows.append((f"{name}{tag[facing]} ({len(frames) / FPS:.2f}s{', loop' if looping else ''})", pick))
    tw, th = 200, 168
    sheet = Image.new("RGBA", (tw * 10, (th + 16) * len(rows)), (236, 230, 214, 255))
    d = ImageDraw.Draw(sheet)
    for r, (label, pick) in enumerate(rows):
        y = r * (th + 16)
        d.text((4, y + 2), label, fill=(0, 0, 0, 255))
        for i, im in enumerate(pick):
            sheet.paste(im.resize((tw, th), Image.LANCZOS), (i * tw, y + 16))
    sheet.save(os.path.join(PREVIEW, "sheet.png"))
    rest = render(bake(idle, 0.1, False, [])[0][2], syms, images, size=(460, 420), ground=60, scale=1.2)
    rest.save(os.path.join(PREVIEW, "rest.png"))


def main():
    syms = draw_parts()
    baked = all_baked()
    z = compile_anim(syms, baked)
    print("wrote", z, os.path.getsize(z), "bytes;", sum(len(f) for *_, f in baked), "frames")
    if "--preview" in sys.argv:
        previews(syms, baked)
        print("previews in", PREVIEW)


if __name__ == "__main__":
    main()
