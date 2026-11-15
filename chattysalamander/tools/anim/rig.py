"""The giant salamander's rig and animations, baked into the game's own animation file.

    python tools/anim/rig.py [--preview]      (conda env pcvoice: Pillow, numpy; Windows, for scml.exe)

The parts are drawings (art/parts: tools/gen made them - an image model drawing in the game's style from the game's
own creatures, each part isolated in place from one design drawing, cut out and sized; art/parts/parts.json has each
part's pivot, the joint it turns about, and where that joint is in the resting pose). A skeleton, as Klei's big
creatures are built: the body; on it the head (its jaw, cut off it along the lip, turning down to open the mouth,
the mouth's inside drawn behind it), the eye on the head (with lids, a pupil that looks about), an axolotl's three
fringed gill stalks each side of the head (springs its head's motion swings, fluttering), four legs (the far two behind the body, darker), and the tail: one drawing, its frames bent to 17
curvatures (tools/gen/sal_vector.py), the pose's three tail angles and its tip's spring summed to choose one - no
pieces, so no seams. Drawn from the side only (the prefab is two-faced:
the game mirrors it to face left).

Each animation is a function of time giving a Pose (joint angles and the like), timed the way the game's own are
(30 frames a second; read from its anim files with tools/gen/dstref.py): an anticipation, a quick move, a held
extreme, one overshoot settling. Out: anim/chattysalamander.zip - the build from the Mod Tools' scml.exe (a Spriter
file listing every part), the animations written here (animbin.py). --preview: build/preview, a GIF of each and
sheet.png, drawn from the very matrices the game gets."""
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

NAME = "chattysalamander"
FPS = 30
ROOT = os.path.dirname(os.path.dirname(HERE))
ART = os.path.join(ROOT, "art", os.environ.get("SAL_ART", "parts3d"))   # (parts3d: rendered from the 3D model,
#                                                                          tools/blender; parts: the old drawings)
EXPORT = os.path.join(ROOT, "exported", NAME)
PREVIEW = os.path.join(ROOT, "build", "preview")
SCML = r"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe"
ALL = 255

PARTS = json.load(open(os.path.join(ART, "parts.json")))
GILL_REST = PARTS.pop("_gills")
TAIL = PARTS.pop("_tail", {"n": 1, "bend": 1.0})   # (the tail: one symbol, its frames bent -bend .. +bend at the tip)
BROW_OF = PARTS.pop("_brow_of", {})        # (the brow's frame for each eye's state: the mood)
JAW_OPEN = PARTS.pop("_jaw_open")        # (the mouth's inside is drawn for the jaw this far down: squashed to fit)
J = {k: np.array(v, float) for k, v in PARTS.pop("_joints").items()}   # joints at rest (from the ground below
#                                                                          the body's middle, y up)
# (the back half drawn at each bend: BINS, degrees the hips have swung off the front's line; its joints at each)
BINS = PARTS.pop("_bins", [0.0])
REAR_J = {v: {int(b): {k: np.array(q, float) for k, q in d.items()} for b, d in bd.items()}
          for v, bd in PARTS.pop("_rear", {}).items()}
MID = BINS.index(0.0) if 0.0 in BINS else len(BINS) // 2
THREE_D = bool(REAR_J)

# --- two halves -----------------------------------------------------------------------------------------------------
# (the game has it as two: the front half (head, forelegs, chest: the creature itself, its bank NAME) and the back half
#  (hips, hind legs, tail: REAR_BANK, a piece each player's game draws, following the front like a snake). They meet at
#  the waist - x 0, the body's middle, where both have their origin - so they stay joined however the back bends. The
#  body's one drawing is cut there: the front's half fading out over the waist, the back's going on under it.)
REAR_BANK = NAME + "_rear"
WAIST_FADE = (-34.0, 30.0)     # (px either side of the waist the front's body fades out over)
REAR_REACH = 96.0              # (the back's body goes on under the front's this far forward, fading out)


def split_body():
    w, h, px, py, *rest = PARTS["body"]["rest"]
    img = Image.open(os.path.join(ART, "body", "rest.png")).convert("RGBA")
    a = np.asarray(img).astype(np.float32)
    k = img.width / w
    x = np.arange(img.width) / k - px * w           # (px from the body's pivot, J["body"]: x 0, the waist)

    def smooth(u):
        u = np.clip(u, 0, 1)
        return u * u * (3 - 2 * u)
    for key, f in (("front", smooth((x - WAIST_FADE[0]) / (WAIST_FADE[1] - WAIST_FADE[0]))),
                   ("rear", 1 - smooth((x - WAIST_FADE[1]) / (REAR_REACH - WAIST_FADE[1])))):
        b = a.copy()
        b[..., 3] *= f[None, :]
        Image.fromarray(np.clip(b + 0.5, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(ART, "body", f"{key}.png"))
        PARTS["body"][key] = [w, h, px, py, *rest]


def closed_symbols():
    """each half's waist closed - a round inked end of its own (sal_vector.closed_body, sal_views.back_halves) - as a
    symbol of its own, its frames as the open one's: the game swaps it in (OverrideSymbol) when the other half shows
    another view (chattysalamander/body.lua)"""
    def copy(sym, frames):
        os.makedirs(os.path.join(ART, sym + "c"), exist_ok=True)
        PARTS[sym + "c"] = {}
        for key, src in frames.items():
            shutil.copyfile(os.path.join(ART, sym, f"{src}.png"), os.path.join(ART, sym + "c", f"{key}.png"))
            PARTS[sym + "c"][key] = PARTS[sym][src]
    copy("body", {"rest": "rest", "front": "front_closed", "rear": "rear_closed"})
    PARTS["body"].pop("front_closed")
    PARTS["body"].pop("rear_closed")
    for sym in ("bshoulder", "bhips"):
        if sym in PARTS:
            copy(sym, {"0": "closed"})
            PARTS[sym].pop("closed")


if not THREE_D:
    split_body()
    closed_symbols()
FRAME = {s: {k: i for i, k in enumerate(v)} for s, v in PARTS.items()}  # the body's middle, y up)
GILLS = [k for k in J if k.startswith("gill")]                          # gill_n0.. (near), gill_f0.. (far)


# (the builds: the game draws a build from two atlases at most (none of Klei's ~3600 has more; a third shows other
#  parts' pictures) - so the back half, drawn at every bend, is builds of its own, one for each view: its piece
#  takes the one for the view it shows (chattysalamander/body.lua); the dropped tail one more)
BUILD_OF = {}
if THREE_D:
    for _b, _syms in {NAME + "_rear_side": ("bodyr", "bodyrs", "tail", "leg_back"),
                      NAME + "_rear_down": ("fhips", "fhipss", "ftail", "fhind"),
                      NAME + "_rear_up": ("bhips", "bhipss", "btail", "bhind"),
                      NAME + "_tail": ("decoy",)}.items():
        for _s in _syms:
            BUILD_OF[_s] = _b


def build_of(sym):
    return BUILD_OF.get(sym, NAME)


def draw_parts():
    syms = {}
    for s, frames in PARTS.items():
        d = os.path.join(ROOT, "exported", build_of(s))
        os.makedirs(os.path.join(d, s), exist_ok=True)
        syms[s] = []
        for i, (key, (w, h, px, py, *_)) in enumerate(frames.items()):
            name = f"{s}/{s}-{i}.png"
            shutil.copyfile(os.path.join(ART, s, f"{key}.png"), os.path.join(d, name))
            syms[s].append((name, w, h, px, py))
    return syms


# --- a pose ---------------------------------------------------------------------------------------------------------

LEGS = ("leg_fn", "leg_ff", "leg_bn", "leg_bf")    # front near, front far, back near, back far


@dataclass
class Pose:
    x: float = 0.0                 # the whole body moved (y up)
    y: float = 0.0
    rot: float = 0.0               # the body's tilt (degrees, anticlockwise: its head up), about its middle
    sy: float = 1.0                # the body squashed (< 1) or stretched, about its belly
    head: float = 0.0              # the head's angle on the neck (up +)
    head_dx: float = 0.0           # (the head pushed forward / back along the body)
    mouth: str = "shut"            # shut, open, wide, smile: how far the jaw drops (JAW) ...
    jaw: float = 0.0               # ... and this many degrees more
    eyes: str = "open"
    look: tuple = (0.0, 0.0)       # where the pupil looks (-1..1: back..forward, down..up)
    gills: float = 0.0             # the fronds spread (+) or folded flat (-), degrees
    flutter: float = 0.4           # how much they flutter
    legs: dict = field(default_factory=dict)   # leg -> (angle, lift): angle + swings the foot forward, lift 0..1
    tail: tuple = (0.0, 0.0, 0.0)  # each piece's own angle (up +)
    fx: list = field(default_factory=list)


def fx(sym, frame=0, x=0.0, y=0.0, a=0.0, sx=1.0, sy=None, layer="front", name=None):
    return dict(sym=sym, f=frame, x=x, y=y, a=a, sx=sx, sy=sx if sy is None else sy, layer=layer, name=name or sym)


# --- 2D affine helpers (3 x 3, y up) --------------------------------------------------------------------------------

def T(x, y):
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], float)


def R(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def S(sx, sy):
    return np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1]], float)


def about(p, A):
    """A done about the point p"""
    return T(*p) @ A @ T(-p[0], -p[1])


def apply(A, p):
    return (A @ np.array([p[0], p[1], 1.0]))[:2]


# --- easing and keys ------------------------------------------------------------------------------------------------

def ease(kind, x):
    x = min(max(x, 0.0), 1.0)
    if kind == "lin":
        return x
    if kind == "in":
        return x * x
    if kind == "out":
        return 1 - (1 - x) ** 2
    if kind == "back":
        c = 1.6
        return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
    if kind == "hold":
        return 0.0 if x < 1 else 1.0
    return x * x * (3 - 2 * x)


def keys(t, *ks):
    if t <= ks[0][0]:
        return ks[0][1]
    for a, b in zip(ks, ks[1:]):
        if t <= b[0]:
            e = b[2] if len(b) > 2 else "io"
            return a[1] + (b[1] - a[1]) * ease(e, (t - a[0]) / (b[0] - a[0]))
    return ks[-1][1]


def settle(t, t0, amp, period=0.3):
    if t < t0:
        return 0.0
    u = (t - t0) / period
    return amp * math.exp(-2.2 * u) * math.cos(math.pi * u) if u < 2.5 else 0.0


def blink(t, t0, base="open"):
    u = t - t0
    if 0 <= u < 0.034 or 0.134 <= u < 0.167:
        return "half"
    if 0.034 <= u < 0.134:
        return "closed"
    return base


def pop(t, t0, t1, grow=0.12, shrink=0.12):
    if t < t0 or t > t1:
        return 0.0
    return ease("back", (t - t0) / grow) * (1 - ease("in", (t - (t1 - shrink)) / shrink) if t > t1 - shrink else 1)


def wave(t, period, amp, lag=0.9, phase=0.0):
    """a wave down the tail: each piece's angle"""
    return tuple(amp * (0.6 + 0.4 * i) * math.sin(2 * math.pi * t / period - lag * i + phase) for i in range(3))


def stand(lift=0.0):
    return {k: (0.0, lift) for k in LEGS}


# --- the animations -------------------------------------------------------------------------------------------------

def idle(t):
    br = math.sin(2 * math.pi * t / 3.0)
    return Pose(sy=1 + 0.012 * br, y=-1.5 * br, head=1.2 * math.sin(2 * math.pi * t / 3.0 - 0.6), eyes=blink(t, 2.1),
                tail=wave(t, 3.0, 2.5), gills=2 * br, flutter=0.35, legs=stand())


def idle_look(t):
    head = keys(t, (0, 0), (0.3, 9, "out"), (1.1, 9), (1.35, -10, "io"), (2.2, -10), (2.5, 0, "io"))
    look_down = 1.35 <= t < 2.2
    return Pose(head=head + settle(t, 2.5, 2), rot=keys(t, (0, 0), (0.3, 1.5), (1.1, 1.5), (1.35, -1.5), (2.2, -1.5),
                                                        (2.5, 0)),
                eyes=blink(t, 0.9, blink(t, 2.35)), mouth="smile" if look_down else "shut",
                gills=keys(t, (0, 0), (0.3, 6), (1.1, 6), (1.35, -2), (2.2, -2), (2.5, 0)), tail=wave(t, 1.5, 3.5),
                legs=stand())


WALK = 1.4                     # (the walk loop: each foot once)
STANCE = 0.62                  # (the share of it a foot is down)
STRIDE = 21.0                  # (degrees a leg swings either way)
PHASE = {"leg_fn": 0.0, "leg_bf": 0.0, "leg_ff": 0.5, "leg_bn": 0.5}   # (diagonal pairs together)
STEPS = (0.0, 0.5)             # (when the near feet come down, shares of the loop: the stategraph's STEPS, x WALK)


def leg_cycle(u):
    """a leg's (angle, lift) at u (0..1 of its own cycle; 0: the foot comes down, forward)"""
    if u < STANCE:
        k = u / STANCE
        return STRIDE * (1 - 2 * k), 0.0                       # (down: swept back, steadily)
    k = (u - STANCE) / (1 - STANCE)
    return STRIDE * (-1 + 2 * ease("io", k)), math.sin(math.pi * k)   # (up: swung forward, lifted)


def walk_pose(t, amount=1.0):
    u = (t / WALK) % 1.0
    legs = {}
    for k, ph in PHASE.items():
        a, lift = leg_cycle((u + ph) % 1.0)
        legs[k] = (a * amount, lift * amount)
    bob = math.cos(4 * math.pi * u)
    return Pose(y=-3 * bob * amount, rot=1.6 * math.sin(2 * math.pi * u) * amount,
                head=-1.4 * math.sin(2 * math.pi * u) * amount + 1.5 * bob * amount,
                tail=wave(t, WALK, 7 * amount, lag=1.0), gills=-4 * amount, flutter=0.6, legs=legs,
                eyes=blink(t, 0.9))


def walk_loop(t):
    return walk_pose(t)


def walk_pre(t):
    k = ease("io", t / 0.3)
    p = walk_pose(t + WALK - 0.3, k)
    p.rot += -2 * math.sin(math.pi * k)
    return p


def walk_pst(t):
    k = 1 - ease("out", t / 0.4)
    p = walk_pose(t, k)
    p.head += settle(t, 0.2, -2.5)
    return p


TALK = ["open", "smile", "open", "shut", "wide", "open", "smile", "shut", "open", "wide", "smile", "shut"]


def talk(t):
    i = int(t / 0.1) % len(TALK)
    m = TALK[i]
    u = t - int(t / 0.1) * 0.1
    nod = {"open": 2.5, "wide": 4.0, "smile": 1.5, "shut": 0.0}[m] * math.exp(-u * 18)
    return Pose(head=2 + nod + 1.5 * math.sin(2 * math.pi * t / 1.2), mouth=m, eyes=blink(t, 0.77),
                gills=4 + 3 * math.sin(2 * math.pi * t / 0.6), flutter=0.6, tail=wave(t, 2.4, 3), legs=stand(),
                sy=1 + 0.008 * math.sin(2 * math.pi * t / 1.2))


def think(t):
    # (no thinking bubbles rising from it - the user, 2026-11-06: "remove the green bubbles coming from gilbert, I
    # dunno what they're for"; the game hides the symbol until the next rebuild: prefabs/chattysalamander.lua)
    return Pose(head=7 + 1.5 * math.sin(2 * math.pi * t / 1.6), eyes=blink(t, 1.1, "half" if t > 0.8 else "open"),
                mouth="shut", gills=2 + 2 * math.sin(2 * math.pi * t / 1.6), tail=wave(t, 1.6, 2.5), legs=stand())


def happy(t):
    b = [arc for arc in ((0.1, 0.4), (0.5, 0.8))]
    y = sum(18 * math.sin(math.pi * min(1, max(0, (t - a) / (e - a)))) for a, e in b)
    sy = 1 + 0.06 * sum(math.sin(math.pi * min(1, max(0, (t - a) / (e - a)))) for a, e in b) \
        - 0.07 * sum(math.exp(-((t - e) / 0.05) ** 2) for _, e in b)
    hearts = []
    hx, hy = J["eye"]
    for k, (t0, dx) in enumerate(((0.45, 30), (0.8, -30))):
        sc = pop(t, t0, 1.55)
        if sc > 0:
            u = t - t0
            hearts.append(fx("heart", 0, hx + dx + 20 * u, hy + 80 + 90 * u, a=-10 * (dx > 0) + 6, sx=sc * 1.3,
                             name=f"heart{k}"))
    lift = 0.6 if y > 4 else 0.0
    return Pose(y=y, sy=sy, head=keys(t, (0, 0), (0.15, 10, "out"), (1.2, 10), (1.6, 0)), mouth="smile",
                eyes="happy" if 0.1 < t < 1.4 else "open", gills=keys(t, (0, 0), (0.15, 14, "out"), (1.2, 14), (1.6, 0)),
                flutter=1.0, tail=wave(t, 0.45, 14, lag=0.8), legs=stand(lift), fx=hearts)


def sad(t):
    k = keys(t, (0, 0), (0.6, 1), (1.6, 1), (2.0, 0))
    return Pose(head=-12 * k + settle(t, 0.6, -1.5), y=-6 * k, sy=1 - 0.03 * k, eyes="sad" if 0.1 < t < 1.85 else "open",
                mouth="shut", gills=-22 * k, flutter=0.15, tail=tuple(-4 * k * (1 + i) for i in range(3)),
                legs={g: (0.0, 0.0) for g in LEGS})


def surprised(t):
    back = keys(t, (0, 0), (0.1, 1, "out"), (0.7, 1), (1.1, 0))
    return Pose(x=-22 * back, y=keys(t, (0, 0), (0.1, 14, "out"), (0.25, 4, "in"), (1.1, 0)) + settle(t, 0.25, -3),
                rot=6 * back + settle(t, 0.1, 2), head=10 * back, mouth="open" if 0.05 < t < 0.9 else "shut",
                eyes="wide" if 0.05 < t < 0.95 else blink(t, 1.0), gills=24 * back, flutter=1.0,
                tail=(8 * back + settle(t, 0.1, 6), 6 * back, 4 * back), legs=stand(0.3 * back))


def vein(t, t0, t1, x, y, size=1.0, beat=0.36):
    """the anger mark popping on, throbbing (a sharp swell each beat, easing back), off"""
    sc = pop(t, t0, t1)
    if sc <= 0:
        return []
    ph = ((t - t0) % beat) / beat
    throb = 0.94 + 0.24 * math.exp(-ph * 7) * (t - t0 > 0.1)
    return [fx("vein", 0, x, y, a=-6 + 3 * math.sin(t * 23), sx=sc * throb * size)]


def angry(t):
    k = keys(t, (0, 0), (0.2, 1, "out"), (1.3, 1), (1.6, 0))
    shake = 2.5 * math.sin(2 * math.pi * 14 * t) * (0.2 < t < 1.3)
    hx, hy = J["eye"]
    scr = vein(t, 0.2, 1.35, hx + 8 + shake, hy + 88 - 4 * k)
    return Pose(x=shake, head=-8 * k, y=-4 * k, sy=1 + 0.02 * k, mouth="wide" if 0.3 < t < 1.2 else "shut",
                eyes="angry" if 0.05 < t < 1.5 else "open", gills=26 * k, flutter=1.0 + 1.5 * k,
                tail=wave(t, 0.25, 8 * k), legs=stand(), fx=scr)


def dance(t):
    b = t / 0.6
    p = b - int(b)
    n = int(b)
    sway = math.sin(math.pi * b)
    legs = stand()
    side = "leg_fn" if n % 2 == 0 else "leg_ff"
    legs[side] = (12.0 * math.sin(math.pi * p), math.sin(math.pi * p))
    notes = []
    hx, hy = J["eye"]
    for k, t0 in enumerate((0.0, 0.8, 1.6)):
        sc = pop(t, t0 + 0.05, t0 + 0.85)
        if sc > 0:
            u = t - t0
            sgn = 1 if k % 2 == 0 else -1
            notes.append(fx("note", 0, hx + sgn * (60 + 18 * u), hy + 100 + 70 * u, a=-sgn * 10 + 12 * math.sin(u * 8),
                            sx=sc * 1.3, name=f"note{k}"))
    return Pose(rot=4 * sway, y=6 * abs(math.sin(math.pi * b)), head=-5 * sway + 4, mouth="smile", eyes="happy",
                gills=10 + 6 * abs(sway), flutter=1.0, tail=wave(t, 0.6, 12, lag=0.7), legs=legs, fx=notes)


def eat(t):
    head = keys(t, (0, 0), (0.35, -22, "io"), (0.55, -24), (0.75, -4, "out"), (1.3, 4), (1.6, 0))
    if t < 0.4:
        mouth = "open" if t > 0.15 else "shut"
    elif t < 0.55:
        mouth = "wide"
    elif t < 1.2:
        mouth = "shut" if int((t - 0.55) / 0.12) % 2 == 0 else "open"
    else:
        mouth = "smile"
    hearts = []
    sc = pop(t, 1.15, 1.6)
    hx, hy = J["eye"]
    if sc > 0:
        hearts = [fx("heart", 0, hx + 30, hy + 80 + 60 * (t - 1.15), a=-8, sx=sc * 1.2)]
    return Pose(head=head, head_dx=keys(t, (0, 0), (0.35, 10), (0.75, 0)), rot=keys(t, (0, 0), (0.35, -3), (0.75, 0)),
                mouth=mouth, eyes="squeeze" if 0.55 <= t < 0.7 else ("happy" if t >= 1.2 else "open"),
                gills=keys(t, (0, 0), (0.35, -6), (0.75, 6), (1.6, 0)), tail=wave(t, 1.6, 3), legs=stand(), fx=hearts)


ATK_HIT = 0.6


def attack(t):
    # (reared back, jaws open; a lunge; the snap at ATK_HIT, held; back)
    reach = keys(t, (0, 0), (0.35, -0.35, "out"), (0.42, -0.35), (0.6, 1.0, "out"), (0.75, 1.0), (1.2, 0.0))
    up = keys(t, (0, 0), (0.35, 1, "out"), (0.45, 1), (0.6, -0.4, "out"), (0.8, -0.4), (1.2, 0))
    if t < 0.2:
        mouth = "shut"
    elif t < ATK_HIT:
        mouth = "wide"
    elif t < 1.0:
        mouth = "shut"
    else:
        mouth = "smile"
    legs = stand()
    legs["leg_fn"] = (14 * max(reach, 0), 0.4 * (0.45 < t < 0.6))
    legs["leg_ff"] = (10 * max(reach, 0), 0.0)
    legs["leg_bn"] = (-8 * max(reach, 0), 0.0)
    legs["leg_bf"] = (-6 * max(reach, 0), 0.0)
    return Pose(x=60 * reach, rot=4 * up, y=6 * max(up, 0), head=14 * up + settle(t, ATK_HIT, -4, 0.2),
                head_dx=16 * max(reach, 0), mouth=mouth, eyes="angry" if t < 1.0 else "open", gills=20 * max(up, 0) + 6,
                flutter=1.2, tail=(10 * up + settle(t, ATK_HIT, 8, 0.25), 6 * up, 3 * up), legs=legs)


def hit(t):
    k = keys(t, (0, 1), (0.25, 0, "out"))
    return Pose(x=-14 * k, rot=-3 * k, head=8 * k + settle(t, 0.1, -3, 0.2), eyes="squeeze" if t < 0.3 else "open",
                mouth="open" if t < 0.3 else "shut", gills=16 * k, flutter=1.0, tail=(6 * k, 4 * k, 2 * k), legs=stand())


def lying(k):
    """legs folded under, belly on the ground: share k"""
    legs = {g: ((18 if g.startswith("leg_f") else -18) * k, -0.9 * k) for g in LEGS}
    return dict(y=-38 * k, legs=legs)


def death(t):
    k = keys(t, (0.2, 0), (0.7, 1, "in"))
    jolt = 2.5 * math.sin(2 * math.pi * 12 * t) * (t < 0.3)
    p = Pose(x=jolt, rot=keys(t, (0, 0), (0.25, 5, "out"), (0.7, -2, "in")), head=keys(t, (0, 0), (0.25, 12, "out"),
                                                                                         (0.75, -14, "in")) + settle(t, 0.75, 2),
             mouth="open" if t < 0.6 else "shut", eyes="squeeze" if t < 0.5 else "dead",
             gills=keys(t, (0, 0), (0.25, 18), (0.8, -30)), flutter=0.0 if t > 0.8 else 0.8,
             tail=tuple(keys(t, (0, 0), (0.3, 8), (0.9, -6 - 3 * i)) for i in range(3)), **lying(k))
    return p


def sleep_pre(t):
    k = ease("io", t / 0.8)
    return Pose(head=-10 * k, eyes="open" if t < 0.2 else ("half" if t < 0.5 else "closed"), gills=-12 * k,
                flutter=0.3, tail=tuple(-2 * k * (1 + i) for i in range(3)), **lying(k))


def sleep_loop(t):
    br = math.sin(2 * math.pi * t / 3.0)
    zs = []
    hx, hy = J["eye"]
    for k in range(3):
        u = ((t - k * 1.0) % 3.0) / 2.0
        if u <= 1:
            sc = (0.6 + 0.6 * u) * min(1, u / 0.12) * min(1, (1 - u) / 0.15)
            zs.append(fx("zzz", 0, hx + 40 + 40 * u + 8 * math.sin(u * 7), hy + 40 + 110 * u, a=-10 + 14 * math.sin(u * 5),
                         sx=sc * 1.1, name=f"zzz{k}"))
    p = Pose(head=-10 + 1.5 * br, eyes="closed", gills=-12 + 3 * br, flutter=0.2, sy=1 + 0.015 * br,
             tail=(-2, -4, -6), fx=zs, **lying(1.0))
    return p


def sleep_pst(t):
    k = 1 - ease("io", t / 0.8)
    yawn = 0.15 < t < 0.5
    return Pose(head=-10 * k + 12 * math.sin(math.pi * min(1, max(0, (t - 0.15) / 0.4))),
                mouth="wide" if yawn else "shut", eyes="closed" if t < 0.4 else ("half" if t < 0.55 else "open"),
                gills=-12 * k + settle(t, 0.5, 6), tail=tuple(-2 * k * (1 + i) for i in range(3)), **lying(k))


# name: (length, looping, pose function)
ANIMS = {
    "idle": (3.0, True, idle),
    "idle_look": (3.0, False, idle_look),
    "walk_pre": (0.3, False, walk_pre),
    "walk_loop": (WALK, True, walk_loop),
    "walk_pst": (0.4, False, walk_pst),
    "talk": (1.2, True, talk),
    "think": (1.6, True, think),
    "happy": (1.6, False, happy),
    "sad": (2.0, False, sad),
    "surprised": (1.2, False, surprised),
    "angry": (1.6, False, angry),
    "dance": (2.4, False, dance),
    "eat": (1.6, False, eat),
    "attack": (1.2, False, attack),
    "hit": (0.5, False, hit),
    "death": (2.0, False, death),
    "sleep_pre": (0.8, False, sleep_pre),
    "sleep_loop": (3.0, True, sleep_loop),
    "sleep_pst": (0.8, False, sleep_pst),
}

# --- baking ---------------------------------------------------------------------------------------------------------


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


LEG_LIFT = 16.0        # (px a foot comes up at the top of its swing)
JAW = {"shut": 0.0, "smile": 0.0, "open": 10.0, "wide": 18.0}    # (the jaw dropped, degrees, for each mouth)
GILL_SCALE = {"0": 1.0, "1": 1.08, "2": 0.9}   # (the middle stalk the longest, as an axolotl's)
GILL_FAR = -14.0                       # (the far side's fanned less: up, over the head and back, where they show)
PUPIL = {"open": 1.0, "wide": 1.12}    # (the eyes with highlights of their own (the "pupil" symbol), how big)
LOOK = (5.0, 4.0)                      # (how far it goes)


def hips(view, k, b, default):
    """a hind leg's hip in a view at bend b (the back half's own, as rendered)"""
    d = REAR_J.get(view, {}).get(b)
    return d[k] if d and k in d else default


def skeleton(p, b=MID):
    """each part's affine (3 x 3, rest -> now); b: the back half's bend"""
    A = {}
    Bd = T(p.x, p.y) @ about(J["body"], R(p.rot)) @ about((J["body"][0], 0), S(1, p.sy))
    A["body"] = Bd
    neck = J["head"]
    A["head"] = Bd @ T(p.head_dx, 0) @ about(neck, R(p.head))
    A["eye"] = A["head"]
    for g in GILLS:
        A[g] = A["head"]
    for k in LEGS:
        ang, lift = p.legs.get(k, (0.0, 0.0))
        hip = hips("side", k, b, J[k]) if k.startswith("leg_b") else J[k]
        sq = 1 - 0.18 * max(lift, 0) if lift >= 0 else 1 + 0.45 * lift      # (folded under when lying: lift < 0)
        A[k] = Bd @ T(0, LEG_LIFT * max(lift, 0)) @ about(hip, R(ang) @ S(1, sq))
    tA = Bd
    for i, a in enumerate(p.tail):
        tA = tA @ about(J[f"tail{i + 1}"], R(a))
        A[f"tail{i + 1}"] = tA
    return A


def elements(p, A, st):
    """front first: (symbol, frame, layer, M 2 x 2, t)"""
    def el(sym, key, layer, Ap, joint, extra=None):
        M = Ap[:2, :2] if extra is None else Ap[:2, :2] @ extra
        return (sym, FRAME[sym][key], layer, M, apply(Ap, joint))
    front, back = [], []
    for e in p.fx:
        if e["sym"] not in FRAME:
            continue
        M = R(e["a"])[:2, :2] @ np.diag([e["sx"], e["sy"]])
        (front if e["layer"] == "front" else back).append((e["sym"], e["f"], e["name"], M, np.array([e["x"], e["y"]])))
    out = list(front)
    gill_ang = {}
    for i, g in enumerate(GILLS):
        base = p.gills * (1.0 if g[5] == "n" else 0.8) * (0.7 + 0.3 * int(g[-1]))
        fl = p.flutter * 3.0 * math.sin(st["t"] * 2 * math.pi * 1.7 + i * 1.3)
        spring = float(st["gill"].x[0]) * (1 + 0.25 * int(g[-1]))
        gill_ang[g] = GILL_REST[g[-1]] + base + fl + spring + (GILL_FAR if g[5] == "f" else 0.0)
    near = [g for g in GILLS if g[5] == "n"]
    far = [g for g in GILLS if g[5] == "f"]
    for g in near:
        out.append(el("gill", "near", g, A[g] @ about(J[g], R(gill_ang[g]) @ S(GILL_SCALE[g[-1]], GILL_SCALE[g[-1]])),
                      J[g]))
    b = st.get("bin", MID)
    if p.eyes in PUPIL and "pupil" in FRAME:
        Ae = A["eye"]
        off = Ae[:2, :2] @ np.array([p.look[0] * LOOK[0], p.look[1] * LOOK[1]])
        out.append(("pupil", 0, "pupil", Ae[:2, :2] * PUPIL[p.eyes], apply(Ae, J["eye"]) + off))
    if "brow" in FRAME:
        out.append(el("brow", BROW_OF.get(p.eyes, "neutral"), "brow", A["eye"], J["eye"]))
    out.append(el("eye", p.eyes, "eye", A["eye"], J["eye"]))
    out.append(el("head", "shut", "head", A["head"], J["head"]))
    jaw = JAW.get(p.mouth, 0.0) + p.jaw
    Aj = A["head"] @ about(J["jaw"], R(-jaw))
    out.append(el("jaw", "0", "jaw", Aj, J["jaw"]))
    # (the inside shows in the gap only: squashed up to the lip line as the jaw closes)
    out.append(el("mouth", "0", "mouth", A["head"] @ about(J["jaw"], S(1, max(jaw, 0.3) / JAW_OPEN)), J["jaw"]))
    out.append(el("leg_front", "near", "leg_fn", A["leg_fn"], J["leg_fn"]))
    if THREE_D:
        out.append(el("leg_back", f"near{b}", "leg_bn", A["leg_bn"], hips("side", "leg_bn", b, J["leg_bn"])))
        out.append(el("body", "front", "body_f", A["body"], J["body"]))
        out.append(el("bodyr", f"rear{b}", "body_r", A["body"], J["body"]))
    else:
        out.append(el("leg_back", "near", "leg_bn", A["leg_bn"], J["leg_bn"]))
        out.append(el("body", "front", "body_f", A["body"], J["body"]))
        out.append(el("body", "rear", "body_r", A["body"], J["body"]))
    # (the tail: its pieces' angles and the tip's spring, summed, choose how far its one drawing is bent)
    tip = float(st["tail"].x[0])
    bend = (sum(p.tail) + tip) / TAIL["bend"]
    f = int(round((min(1.0, max(-1.0, bend)) + 1) / 2 * (TAIL["n"] - 1)))
    if THREE_D:
        out.append(el("tail", f"{b}_{f}", "tail", A["body"], J["body"]))
    else:
        out.append(el("tail", str(f), "tail", A["body"], J["tail"]))
    out.append(el("leg_front", "far", "leg_ff", A["leg_ff"], J["leg_ff"]))
    if THREE_D:
        out.append(el("leg_back", f"far{b}", "leg_bf", A["leg_bf"], hips("side", "leg_bf", b, J["leg_bf"])))
    else:
        out.append(el("leg_back", "far", "leg_bf", A["leg_bf"], J["leg_bf"]))
    for g in far:
        out.append(el("gill", "far", g, A[g] @ about(J[g], R(gill_ang[g]) @ S(GILL_SCALE[g[-1]], GILL_SCALE[g[-1]])),
                      J[g]))
    out += back
    return out


# --- the front and the back: the four-faced game's down and up views ---------------------------------------------
# (the same pose, seen from in front or behind: what moves forward comes toward us (down the screen, a little bigger)
#  or goes away; the head's tilt is its rising and falling; the jaw drops straight down; the legs' swing is their feet
#  coming toward us or going away; the tail bends side to side (behind) or swings out (in front); the gills fan out
#  both sides. The art: tools/gen/sal_views.py)

SIDE, UP, DOWN = 5, 2, 8
VIEWS = PARTS.pop("_views", {})
VJ = {v: {k: np.array(q, float) for k, q in d["J"].items()} for v, d in VIEWS.items()}
MOUTH_OPEN_H = 58.0            # (canvas px the front mouth's inside is drawn tall: squashed to the jaw's drop)


def view_body(p, toward):
    sc = 1 + 0.0007 * p.x * toward
    sq = p.sy
    return T(0, p.y - 0.45 * p.x * toward) @ S(sc * (1 + (1 - sq) * 0.6), sc * sq)


def view_fx(p, head_y):
    """the effects, placed as the side places them about its eye, about the head's middle"""
    front, back = [], []
    ex, ey = J["eye"]
    for e in p.fx:
        if e["sym"] not in FRAME:
            continue
        M = R(e["a"])[:2, :2] @ np.diag([e["sx"], e["sy"]])
        pos = np.array([(e["x"] - ex) * 0.5, head_y + (e["y"] - ey)])
        (front if e["layer"] == "front" else back).append((e["sym"], e["f"], e["name"], M, pos))
    return front, back


def view_gills(p, st, Ah, V, rest, sym="gill"):
    out = []
    sym = sym if sym in FRAME else "gill"
    for side in ("l", "r"):
        for i in range(3):
            base = rest[i] + p.gills * (0.7 + 0.3 * i)
            fl = p.flutter * 3.0 * math.sin(st["t"] * 2 * math.pi * 1.7 + i * 1.3 + (side == "r") * 2.1)
            ang = base + fl + float(st["gill"].x[0]) * (1 + 0.25 * i)
            sc = GILL_SCALE[str(i)]
            root = V[f"gill_{side}{i}"]
            M = R(ang) @ S(sc, sc) if side == "l" else R(-ang) @ S(-sc, sc)
            Ag = Ah @ about(root, M)
            out.append((sym, FRAME[sym]["near"], f"gill_{side}{i}", Ag[:2, :2], apply(Ag, root)))
    return out


def view_leg(p, Bd, k, joint, toward):
    ang, lift = p.legs.get(k, (0.0, 0.0))
    sq = (1 - 0.18 * max(lift, 0) if lift >= 0 else 1 + 0.45 * lift) * (1 + 0.004 * ang * toward)
    return Bd @ T(0, LEG_LIFT * max(lift, 0) - 0.9 * ang * toward) @ about(joint, S(1, sq))


def tail_frame(p, st, n):
    tip = float(st["tail"].x[0])
    bend = (sum(p.tail) + tip) / TAIL["bend"]
    return int(round((min(1.0, max(-1.0, bend)) + 1) / 2 * (n - 1)))


def front_elements(p, A, st):
    if THREE_D:
        return front_elements_3d(p, A, st)
    V = VJ["front"]
    Bd = view_body(p, 1)
    Ah = Bd @ T(0, 1.5 * p.head + 1.0 * p.rot - 0.4 * p.head_dx) @ about(V["head"], S(1, 1 + 0.004 * p.head))
    fxf, fxb = view_fx(p, V["eye_l"][1])
    out = list(fxf)
    ek = VIEWS["front"]["eye_k"]
    eyes = "stern" if p.eyes == "open" and "stern" in FRAME["eye"] else p.eyes   # (facing you: a stern glare)
    if eyes in PUPIL:
        for e in ("eye_l", "eye_r"):
            off = Ah[:2, :2] @ np.array([0.0, p.look[1] * LOOK[1]])
            out.append(("pupil", 0, f"pupil_{e}", Ah[:2, :2] * PUPIL[eyes] * ek, apply(Ah, V[e]) + off))
    for e, mx in (("eye_l", 1), ("eye_r", -1)):                     # (the right: the side's eye, mirrored)
        if "brow" in FRAME:
            out.append(("brow", FRAME["brow"][BROW_OF.get(eyes, "neutral")], f"brow_{e}",
                        Ah[:2, :2] @ np.diag([ek * mx, ek]), apply(Ah, V[e])))
        out.append(("eye", FRAME["eye"][eyes], e, Ah[:2, :2] @ np.diag([ek * mx, ek]), apply(Ah, V[e])))
    out.append(("fhead", 0, "fhead", Ah[:2, :2], apply(Ah, V["head"])))
    drop = max(0.0, JAW.get(p.mouth, 0.0) + p.jaw) * VIEWS["front"]["jaw_drop"]
    Aj = Ah @ T(0, -drop)
    out.append(("fjaw", 0, "fjaw", Aj[:2, :2], apply(Aj, V["lip"])))
    Am = Ah @ about(V["lip"], S(1, max(drop, 0.05) / (MOUTH_OPEN_H * VIEWS["front"]["jaw_drop"] / 2.6)))
    out.append(("fmouth", 0, "fmouth", Am[:2, :2], apply(Am, V["lip"])))
    out += view_gills(p, st, Ah, V, VIEWS["front"]["gill_rest"])
    for k, mx in (("leg_fn", 1), ("leg_ff", -1)):
        Al = view_leg(p, Bd, k, V[k], 1)
        out.append(("fleg", 0, k, Al[:2, :2] @ np.diag([mx, 1]), apply(Al, V[k])))
    out.append(("fbody", 0, "fbody", Bd[:2, :2], apply(Bd, V["body"])))
    for k, mx in (("leg_bn", 1), ("leg_bf", -1)):
        Al = view_leg(p, Bd, k, V[k], 1)
        out.append(("fhind", 0, k, Al[:2, :2] @ np.diag([mx, 1]), apply(Al, V[k])))
    tip = float(st["tail"].x[0])
    At = Bd @ about(V["tail"], R(0.45 * (sum(p.tail) + tip)))
    out.append(("ftail", 0, "ftail", At[:2, :2], apply(At, V["tail"])))
    # (the back half's hips, behind the chest: hidden facing us, there when it turns)
    out.append(("fhips", 0, "fhips", Bd[:2, :2], apply(Bd, V["body"])))
    return out + fxb


def front_elements_3d(p, A, st):
    """the front view from the 3D renders: each side's own drawing (not one mirrored), the back half at its bend"""
    V = VJ["front"]
    b = st.get("bin", MID)
    Bd = view_body(p, 1)
    Ah = Bd @ T(0, 1.5 * p.head + 1.0 * p.rot - 0.4 * p.head_dx) @ about(V["head"], S(1, 1 + 0.004 * p.head))
    fxf, fxb = view_fx(p, V["eye_l"][1])
    out = list(fxf)
    eyes = "stern" if p.eyes == "open" and f"stern_l" in FRAME["feye"] else p.eyes   # (facing you: a stern glare)
    for e in ("l", "r"):
        out.append(("feye", FRAME["feye"][f"{eyes}_{e}"], f"eye_{e}", Ah[:2, :2], apply(Ah, V[f"eye_{e}"])))
    out.append(("fhead", 0, "fhead", Ah[:2, :2], apply(Ah, V["head"])))
    drop = max(0.0, JAW.get(p.mouth, 0.0) + p.jaw) * VIEWS["front"]["jaw_drop"]
    Aj = Ah @ T(0, -drop)
    out.append(("fjaw", 0, "fjaw", Aj[:2, :2], apply(Aj, V["lip"])))
    Am = Ah @ about(V["lip"], S(1, max(drop, 0.05) / VIEWS["front"].get("mouth_h", 40.0)))
    out.append(("fmouth", 0, "fmouth", Am[:2, :2], apply(Am, V["lip"])))
    out += view_gills(p, st, Ah, V, VIEWS["front"]["gill_rest"], "fgill")
    for k, e in (("leg_fn", "l"), ("leg_ff", "r")):
        Al = view_leg(p, Bd, k, V[k], 1)
        out.append(("fleg", FRAME["fleg"][e], k, Al[:2, :2], apply(Al, V[k])))
    out.append(("fbody", 0, "fbody", Bd[:2, :2], apply(Bd, V["body"])))
    for k, e in (("leg_bn", "l"), ("leg_bf", "r")):
        hip = hips("front", k, b, V[k])
        Al = view_leg(p, Bd, k, hip, 1)
        out.append(("fhind", FRAME["fhind"][f"{e}{b}"], k, Al[:2, :2], apply(Al, hip)))
    tf = tail_frame(p, st, TAIL["n"])
    out.append(("ftail", FRAME["ftail"][f"{b}_{tf}"], "ftail", Bd[:2, :2], apply(Bd, V["body"])))
    out.append(("fhips", FRAME["fhips"][str(b)], "fhips", Bd[:2, :2], apply(Bd, V["body"])))
    return out + fxb


def back_elements_3d(p, A, st):
    V = VJ["back"]
    b = st.get("bin", MID)
    Bd = view_body(p, -1)
    Ah = Bd @ T(0, 1.2 * p.head + 1.0 * p.rot + 0.4 * p.head_dx)
    fxf, fxb = view_fx(p, V["head"][1] + 40)
    out = list(fxf)
    tf = tail_frame(p, st, TAIL["n"])
    out.append(("btail", FRAME["btail"][f"{b}_{tf}"], "btail", Bd[:2, :2], apply(Bd, V["body"])))
    for k, e in (("leg_bn", "l"), ("leg_bf", "r")):
        hip = hips("back", k, b, V[k])
        Al = view_leg(p, Bd, k, hip, -1)
        out.append(("bhind", FRAME["bhind"][f"{e}{b}"], k, Al[:2, :2], apply(Al, hip)))
    out.append(("bhips", FRAME["bhips"][str(b)], "bhips", Bd[:2, :2], apply(Bd, V["body"])))
    for k, e in (("leg_fn", "l"), ("leg_ff", "r")):
        Al = view_leg(p, Bd, k, V[k], -1)
        out.append(("bfore", FRAME["bfore"][e], k, Al[:2, :2], apply(Al, V[k])))
    out.append(("bshoulder", 0, "bshoulder", Bd[:2, :2], apply(Bd, V["body"])))
    out += view_gills(p, st, Ah, V, VIEWS["back"]["gill_rest"], "bgill")
    out.append(("bhead", 0, "bhead", Ah[:2, :2], apply(Ah, V["head"])))
    return out + fxb


def back_elements(p, A, st):
    if THREE_D:
        return back_elements_3d(p, A, st)
    V = VJ["back"]
    Bd = view_body(p, -1)
    Ah = Bd @ T(0, 1.2 * p.head + 1.0 * p.rot + 0.4 * p.head_dx)
    fxf, fxb = view_fx(p, V["head"][1] + 40)
    out = list(fxf)
    out.append(("btail", FRAME["btail"][str(tail_frame(p, st, len(FRAME["btail"])))], "btail", Bd[:2, :2],
                apply(Bd, V["tail"])))
    for k, mx in (("leg_bn", 1), ("leg_bf", -1)):
        Al = view_leg(p, Bd, k, V[k], -1)
        out.append(("bhind", 0, k, Al[:2, :2] @ np.diag([mx, 1]), apply(Al, V[k])))
    out.append(("bhips", 0, "bhips", Bd[:2, :2], apply(Bd, V["body"])))
    for k, mx in (("leg_fn", 1), ("leg_ff", -1)):
        Al = view_leg(p, Bd, k, V[k], -1)
        out.append(("bfore", 0, k, Al[:2, :2] @ np.diag([mx, 1]), apply(Al, V[k])))
    # (the front half's shoulders, under the hips: going away)
    out.append(("bshoulder", 0, "bshoulder", Bd[:2, :2], apply(Bd, V["body"])))
    out += view_gills(p, st, Ah, V, VIEWS["back"]["gill_rest"])
    out.append(("bhead", 0, "bhead", Ah[:2, :2], apply(Ah, V["head"])))
    return out + fxb


VIEW_ELEMENTS = {SIDE: lambda p, A, st: elements(p, A, st), DOWN: front_elements, UP: back_elements}
# (which elements are the back half's, in each view; the rest are the front's)
REAR_LAYERS = {SIDE: {"leg_bn", "leg_bf", "body_r", "tail"},
               DOWN: {"leg_bn", "leg_bf", "ftail", "fhips"},
               UP: {"btail", "leg_bn", "leg_bf", "bhips"}}


def split(els, view):
    rear = REAR_LAYERS[view]
    return [e for e in els if e[2] not in rear], [e for e in els if e[2] in rear]


def closed(els):
    """the elements with each half's waist closed (the symbols the game swaps in)"""
    return [((sym + "c") if (sym + "c") in FRAME else sym, f, layer, M, t) for sym, f, layer, M, t in els]


def moved(els, dx, dy):
    return [(sym, f, layer, M, t + np.array([dx, dy])) for sym, f, layer, M, t in els]


def bake(fn, length, looping, seed=1, view=SIDE, b=MID):
    n = int(round(length * FPS))
    dt = 1.0 / FPS
    st = {"gill": Spring(2.2, 0.25), "tail": Spring(1.8, 0.3), "t": 0.0, "bin": b}
    hist_h, hist_t = [], []
    out = []
    passes = 3 if looping else 1
    for pas in range(passes):
        for i in range(n):
            t = i * dt
            st["t"] = t
            p = fn(t)
            A = skeleton(p, b)
            hpos = apply(A["head"], J["eye"])
            tpos = apply(A["tail3"], J["tail3"])
            for h, pos in ((hist_h, hpos), (hist_t, tpos)):
                h.append(pos)
                if len(h) > 3:
                    h.pop(0)
            acc = lambda h: (h[-1] - 2 * h[-2] + h[-3]) / dt ** 2 if len(h) == 3 else np.zeros(2)  # noqa: E731
            ah, at_ = np.clip(acc(hist_h), -5000, 5000), np.clip(acc(hist_t), -5000, 5000)
            st["gill"].step(np.array([-0.004 * ah[1] + 0.002 * ah[0]]) * st["gill"].k, dt)
            st["gill"].x = np.clip(st["gill"].x, -25, 25)
            st["tail"].step(np.array([-0.004 * at_[1]]) * st["tail"].k, dt)
            st["tail"].x = np.clip(st["tail"].x, -20, 20)
            if pas == passes - 1:
                out.append((p, A, VIEW_ELEMENTS[view](p, A, st)))
    return out


def to_bin(els, syms):
    rows = []
    xs, ys = [], []
    for sym, f, layer, M, t in els:
        a, c, b_, d = M[0, 0], -M[0, 1], -M[1, 0], M[1, 1]
        rows.append((sym, int(f), layer, a, b_, c, d, t[0], -t[1]))
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
    """[(name, facing, looping, frames, bank)], frames [(pose, A, elements)]: each animation for each facing, the front
    half's and the back half's (and the back's diagonals)"""
    out = []
    for view in (SIDE, DOWN, UP):
        for name, (length, looping, fn) in ANIMS.items():
            for b in (range(len(BINS)) if THREE_D else [MID]):
                fr, rr = [], []
                for p, A, els in bake(fn, length, looping, seed=animbin.khash(name) % 1000, view=view, b=b):
                    f_, r_ = split(els, view)
                    fr.append((p, A, f_))
                    rr.append((p, A, r_))
                if b == MID:
                    out.append((name, view, looping, fr, NAME))
                # (the back half: one animation for each bend, "<name>_b<bin>" - the game plays the bend it has)
                out.append((rear_name(name, b), view, looping, rr, REAR_BANK))
    return out + decoy_baked()


def decoy_baked():
    """the dropped tail (scripts/chattysalamander/tail.lua), its own bank, no facing: wriggling, thrashing, still"""
    if "decoy" not in FRAME:
        return []
    n = sum(1 for k in FRAME["decoy"] if k.isdigit())

    def frames(length, hard, hop):
        out = []
        N = int(round(length * FPS))
        for i in range(N):
            u = i / N
            key = ("h" if hard else "") + str(int(u * n) % n)
            y = hop * abs(math.sin(2 * math.pi * u))
            out.append((None, None, [("decoy", FRAME["decoy"][key], "decoy", np.eye(2), np.array([0.0, y]))]))
        return out
    bank = NAME + "_tail"
    still = [(None, None, [("decoy", FRAME["decoy"]["0"], "decoy", np.eye(2), np.zeros(2))])]
    return [("flop", ALL, True, frames(0.6, False, 4.0), bank), ("flop_hard", ALL, False, frames(0.5, True, 14.0), bank),
            ("still", ALL, False, still, bank)]


def rear_name(name, b):
    return f"{name}_b{b}" if THREE_D else name


# --- the build and the animations -----------------------------------------------------------------------------------

def write_scml(syms, build=NAME):
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
    out.append(f'  <entity id="0" name="{build}">')
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
    path = os.path.join(ROOT, "exported", build, f"{build}.scml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


def compile_anim(syms, baked, only=None):
    """each build's zip (scml.exe); the animations into their zip's anim.bin: the dropped tail's into its own, the
    rest into NAME's. only: these builds alone (a quick round: the others as they were)"""
    builds = {}
    for sym in syms:
        builds.setdefault(build_of(sym), {})[sym] = syms[sym]
    for build, bsyms in builds.items():
        if only and build not in only:
            continue
        scml = write_scml(bsyms, build)
        r = subprocess.run([SCML, scml, ROOT], capture_output=True, text=True)
        log = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 or "ERROR" in log or "WARNING" in log:
            raise SystemExit(f"scml.exe ({build}):\n" + log)
        with zipfile.ZipFile(os.path.join(ROOT, "anim", f"{build}.zip")) as z:
            n = sum(1 for f in z.namelist() if f.endswith(".tex"))
        print(f"  build {build}: {len(bsyms)} symbols, {n} atlas(es)")
        if n > 2:
            raise SystemExit(f"{build}: {n} atlases - the game draws two at most")
    zips = {}
    for name, facing, looping, frames, bank in baked:
        zips.setdefault(NAME + "_tail" if bank == NAME + "_tail" else NAME, []).append(
            (name, facing, float(FPS), [to_bin(els, syms) for _, _, els in frames], bank))
    for zname, anims in zips.items():
        zpath = os.path.join(ROOT, "anim", f"{zname}.zip")
        tmp = os.path.join(ROOT, "build", "zip")
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tmp)
            infos = {i.filename: i.compress_type for i in z.infolist()}
        animbin.write(os.path.join(tmp, "anim.bin"), zname, anims)
        infos.setdefault("anim.bin", zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(zpath, "w") as z:
            for fn, ct in infos.items():
                z.write(os.path.join(tmp, fn), fn, compress_type=ct)
    return os.path.join(ROOT, "anim", f"{NAME}.zip")


# --- previews -------------------------------------------------------------------------------------------------------

def render(els, syms, images, size=(1100, 620), ground=80, scale=1.0, bg=(214, 200, 160, 255), shadow=True, cx=None):
    im = Image.new("RGBA", size, bg)
    ox, oy = (size[0] / 2 if cx is None else cx), size[1] - ground
    if shadow:
        ImageDraw.Draw(im).ellipse((ox - 330 * scale, oy - 26 * scale, ox + 300 * scale, oy + 26 * scale),
                                   fill=(176, 160, 122, 255))
    for sym, f, layer, M, t in reversed(els):
        name, w, h, px, py = syms[sym][f]
        img = images[name]
        k = img.width / w
        Jm = np.array([[1 / k, 0], [0, -1 / k]])
        j0 = np.array([-px * w, py * h])
        Sf = np.array([[scale, 0], [0, -scale]])
        Am = Sf @ M @ Jm
        bvec = Sf @ (M @ j0 + t) + np.array([ox, oy])
        try:
            Ai = np.linalg.inv(Am)
        except np.linalg.LinAlgError:
            continue
        bi = -Ai @ bvec
        part = img.transform(size, Image.AFFINE, (Ai[0, 0], Ai[0, 1], bi[0], Ai[1, 0], Ai[1, 1], bi[1]),
                             resample=Image.BICUBIC)
        im.alpha_composite(part)
    return im


# (front view, back half's view, where the back half is moved to (build px, y up): toward its hips)
JOINS = [(SIDE, SIDE, (0, 0)), (DOWN, DOWN, (0, 0)), (UP, UP, (0, 0)), (DOWN, SIDE, (-62, 18))]


def previews(syms, baked):
    os.makedirs(PREVIEW, exist_ok=True)
    for f in os.listdir(PREVIEW):
        if f.endswith(".gif"):
            os.remove(os.path.join(PREVIEW, f))
    images = {name: Image.open(os.path.join(ROOT, "exported", build_of(s), name)).convert("RGBA")
              for s, fs in syms.items() for name, *_ in fs}
    rows = []
    halves = {(name, facing, bank): (looping, frames) for name, facing, looping, frames, bank in baked}
    for (name, facing, bank), (looping, frames) in halves.items():
        if bank != NAME:
            continue
        rear = halves[(rear_name(name, MID), facing, REAR_BANK)][1]
        both = [(rf + ff) if facing == UP else (ff + rf) for (_, _, ff), (_, _, rf) in zip(frames, rear)]
        gif = [render(els, syms, images, scale=0.7, size=(840, 500), ground=60, cx=440) for els in both]
        tag = {SIDE: "", DOWN: "_down", UP: "_up"}.get(facing, "")
        gif[0].save(os.path.join(PREVIEW, f"{name}{tag}.gif"), save_all=True, append_images=gif[1:],
                    duration=1000 // FPS, loop=0, disposal=2)
        pick = [gif[int(i * (len(gif) - 1) / 7)] for i in range(8)]
        rows.append((f"{name}{tag} ({len(frames) / FPS:.2f}s{', loop' if looping else ''})", pick))
    tw, th = 252, 150
    sheet = Image.new("RGBA", (tw * 8, (th + 16) * len(rows)), (236, 230, 214, 255))
    d = ImageDraw.Draw(sheet)
    for r, (label, pick) in enumerate(rows):
        y = r * (th + 16)
        d.text((4, y + 2), label, fill=(0, 0, 0, 255))
        for i, im in enumerate(pick):
            sheet.paste(im.resize((tw, th), Image.LANCZOS), (i * tw, y + 16))
    sheet.save(os.path.join(PREVIEW, "sheet.png"))
    # (the joins: the halves in the same view, and turned - the back half in the view beside the front's, both
    #  closed, the back half moved toward where its hips are, as chattysalamander/body.lua has them)
    if THREE_D:
        # (the bends: each view (rows: side, down, up) with the back half at each bend, idle and mid-walk)
        tiles = []
        for facing in (SIDE, DOWN, UP):
            for b in range(len(BINS)):
                for name, i in (("idle", 0), ("walk_loop", 10)):
                    f = halves[(name, facing, NAME)][1][i][2]
                    r = halves[(rear_name(name, b), facing, REAR_BANK)][1][i][2]
                    els = (r + f) if facing == UP else (f + r)
                    tiles.append(render(els, syms, images, scale=0.4, size=(440, 330), ground=90, cx=230,
                                        shadow=False))
        cols = 2 * len(BINS)
        sheet = Image.new("RGBA", (440 * cols, 330 * 3))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % cols) * 440, (i // cols) * 330))
        sheet.save(os.path.join(PREVIEW, "bends.png"))
    else:
        tiles = []
        for name, i in (("idle", 0), ("walk_loop", 10)):
            for fv, rv, off in JOINS:
                f = halves[(name, fv, NAME)][1][i][2]
                r = halves[(name, rv, REAR_BANK)][1][i][2]
                if fv != rv:
                    f, r = closed(f), moved(closed(r), *off)
                els = (r + f) if UP in (fv, rv) else (f + r)
                tiles.append(render(els, syms, images, scale=0.5, size=(560, 400), ground=130, cx=290, shadow=False))
        sheet = Image.new("RGBA", (560 * len(JOINS), 400 * 2))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % len(JOINS)) * 560, (i // len(JOINS)) * 400))
        sheet.save(os.path.join(PREVIEW, "joins.png"))
    rest = render(bake(idle, 0.1, False)[0][2], syms, images)
    if THREE_D:
        # (all of it, as the game draws it: the front and the back half straight)
        rest = render(bake(idle, 0.1, False)[0][2], syms, images)
    rest.save(os.path.join(PREVIEW, "rest.png"))


def main():
    syms = draw_parts()
    if "--only" in sys.argv and sys.argv[sys.argv.index("--only") + 1] == "decoy":
        # (a quick round: the dropped tail alone - its build and its animations, nothing else touched)
        compile_anim(syms, decoy_baked(), only={NAME + "_tail"})
        print("wrote the dropped tail:", os.path.join(ROOT, "anim", NAME + "_tail.zip"))
        return
    baked = all_baked()
    z = compile_anim(syms, baked)
    print("wrote", z, os.path.getsize(z), "bytes;", sum(len(b[3]) for b in baked), "frames")
    if "--preview" in sys.argv:
        previews(syms, baked)
        print("previews in", PREVIEW)


if __name__ == "__main__":
    main()
