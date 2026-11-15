"""After tools/blender/sal_render.py: its renders shrunk to the build's size (from SS x), cropped to what's drawn,
into art/parts3d/<symbol>/<frame>.png, and art/parts3d/parts.json as tools/anim/rig.py reads it (each frame's
[w, h, pivot x, pivot y], pivot as shares of the picture from its top left; the joints, the views, the back half's
joints at each bend). The effects (hearts, notes...) come from art/parts.

    python tools/blender/sal_post.py        (conda env pcvoice)
"""
import json
import os
import shutil

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(ROOT, "art", "parts3d", "raw")
OUT = os.path.join(ROOT, "art", "parts3d")
OLD = os.path.join(ROOT, "art", "parts")
FX = ("heart", "note", "zzz", "vein", "bubble")
VIEW_NAME = {"down": "front", "up": "back"}


def shrink(im, k):
    """premultiplied, so the edges don't go dark; a box filter (an exact average - Lanczos rings at soft edges, a light
    halo where two parts meet); then the edge's colour spread into the clear pixels around it, so the game's texture
    filtering doesn't pull black into the edges"""
    w, h = max(1, round(im.width / k)), max(1, round(im.height / k))
    im = im.convert("RGBa").resize((w, h), Image.BOX).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[..., :3].copy(), a[..., 3]
    have = al > 0
    for _ in range(4):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(al.shape, np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sh = np.roll(np.roll(have, dy, 0), dx, 1)
            acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * sh[..., None]
            cnt += sh
        grow = (~have) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        have = have | grow
    a[..., :3] = rgb
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), "RGBA")


def main():
    man = json.load(open(os.path.join(RAW, "manifest.json")))
    ss = man["SS"]
    parts = {}
    for p in man["parts"]:
        im = Image.open(os.path.join(RAW, p["file"])).convert("RGBA")
        im = shrink(im, ss)
        px, py = p["pivot"][0] / ss, p["pivot"][1] / ss
        a = np.asarray(im)[..., 3]
        ys, xs = np.nonzero(a > 2)
        if len(xs):
            x0, x1 = max(0, xs.min() - 2), min(im.width, xs.max() + 3)
            y0, y1 = max(0, ys.min() - 2), min(im.height, ys.max() + 3)
            im = im.crop((x0, y0, x1, y1))
            px, py = px - x0, py - y0
        d = os.path.join(OUT, p["symbol"])
        os.makedirs(d, exist_ok=True)
        im.save(os.path.join(d, f"{p['frame']}.png"))
        parts.setdefault(p["symbol"], {})[p["frame"]] = [im.width, im.height, px / im.width, py / im.height]
    # (the stump - the tail dropped: the back half's body drawings as symbols of their own, "<symbol>s", their frames
    #  in the same order as the symbol's - the game swaps them in by frame number, OverrideSymbol - the frames they
    #  don't have the symbol's own)
    for sym in ("body", "fhips", "bhips"):
        if sym not in parts:
            continue
        stump = {k[:-1]: v for k, v in parts[sym].items() if k.endswith("s")}
        if not stump:
            continue
        parts[sym] = {k: v for k, v in parts[sym].items() if not k.endswith("s")}
        os.makedirs(os.path.join(OUT, sym + "s"), exist_ok=True)
        out = {}
        for k, v in parts[sym].items():
            src = os.path.join(OUT, sym, (k + "s" if k in stump else k) + ".png")
            shutil.copyfile(src, os.path.join(OUT, sym + "s", k + ".png"))
            out[k] = stump.get(k, v)
        for k in stump:
            os.remove(os.path.join(OUT, sym, k + "s.png"))
        parts[sym + "s"] = out
    # (the side's body: the front half's drawing ("body", in the front's build) and the back half's at each bend
    #  ("bodyr", "bodyrs" the stump: in the back half's build))
    if "bodys" in parts:
        for src, dst in (("body", "bodyr"), ("bodys", "bodyrs")):
            os.makedirs(os.path.join(OUT, dst), exist_ok=True)
            parts[dst] = {}
            for k, v in list(parts[src].items()):
                if k.startswith("rear"):
                    shutil.move(os.path.join(OUT, src, k + ".png"), os.path.join(OUT, dst, k + ".png"))
                    parts[dst][k] = v
                    del parts[src][k]
        shutil.rmtree(os.path.join(OUT, "bodys"), ignore_errors=True)
        del parts["bodys"]
    old = json.load(open(os.path.join(OLD, "parts.json")))
    for s in FX:
        if s in old:
            shutil.copytree(os.path.join(OLD, s), os.path.join(OUT, s), dirs_exist_ok=True)
            parts[s] = old[s]
    parts["_joints"] = man["joints"]
    parts["_gills"] = man["gills"]
    parts["_tail"] = {"n": len(man["tails"]), "bend": man["tail_bend"]}
    parts["_jaw_open"] = 16
    parts["_bins"] = man["bins"]
    parts["_rear"] = {VIEW_NAME.get(v, v): {int(k): j for k, j in d.items()} for v, d in man["rear"].items()}
    views = {}
    for v, d in man["views"].items():
        vv = dict(J=d["J"], gill_rest=d["gill_rest"], eye_k=1.0, jaw_drop=2.0)
        if v == "down" and "fmouth" in parts:
            vv["mouth_h"] = parts["fmouth"]["0"][1]
        views[VIEW_NAME[v]] = vv
    parts["_views"] = views
    with open(os.path.join(OUT, "parts.json"), "w") as f:
        json.dump(parts, f, indent=1)
    n = sum(len(v) for k, v in parts.items() if not k.startswith("_"))
    px = sum(w * h for k, v in parts.items() if not k.startswith("_") for w, h, *_ in v.values())
    print(f"{n} frames, {px / 1e6:.1f} Mpx")


if __name__ == "__main__":
    main()
