"""The creatures beside Wilson, for scale: the game's own Wilson (wilson.zip + player_idles.zip, read from the
installed game by tools/gen/dstref.py) and each mod's creature from its rig, all at the game's scale (one build pixel
a pixel), from the side and from the front. Run from this repo's root, after tools/anim/rig.py:

    python tools/scale_ref.py        -> build/preview/scale.png      (conda env teardown or pcvoice)

The Chatty Slime is drawn too when its repo is next to this one (../chattyslime).
"""
import importlib.util
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "gen"))
import dstref  # noqa: E402

BG = (214, 200, 160, 255)
SHADOW = (176, 160, 122, 255)
H, GROUND = 760, 690                   # (the picture's height, where the ground is)
# (what the game hides on a player with nothing worn or carried)
HIDE = {"ARM_carry", "HAT", "HAIR_HAT", "HEAD_HAT", "HEAD_HAT_NOHELM", "HEAD_HAT_HELM", "swap_object",
        "swap_hat", "hair_hat", "headbase_hat"}
HIDE |= {h.lower() for h in HIDE} | {h.upper() for h in HIDE}


def wilson(facing):
    zips = [dstref.zpath("wilson"), dstref.zpath("player_idles")]
    build = dstref.Build(zips[0])
    fps, frames, fc = dstref.find(zips[1:], "idle_loop", facing)
    w, h = 360, H
    im = dstref.render(build, frames[0][1], size=(w, h), origin=(w / 2, GROUND), scale=1.0, hide=HIDE)
    return im.crop((0, 0, w, h))


def rig(repo, name, view):
    path = os.path.join(repo, "tools", "anim", "rig.py")
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(f"rig_{os.path.basename(repo)}", path)
    r = importlib.util.module_from_spec(spec)
    cwd = os.getcwd()
    os.chdir(repo)
    try:
        spec.loader.exec_module(r)
        syms = {s: [(f"{s}/{k}.png", w, h, px, py) for k, (w, h, px, py, *_) in fr.items()] for s, fr in r.PARTS.items()}
        images = {n: Image.open(os.path.join(r.ART, n)).convert("RGBA") for fs in syms.values() for n, *_ in fs}
        length, looping, fn = r.ANIMS["idle"][:3]
        if isinstance(fn, dict):                     # (the slime's: {facing: (pose function, emits)})
            fn, emits = next(iter(fn.values()))
            frames = r.bake(fn, length, looping, emits)
        else:
            v = {"side": getattr(r, "SIDE", None), "down": getattr(r, "DOWN", None)}[view]
            frames = r.bake(fn, length, looping, view=v) if v is not None and getattr(r, "VIEWS", None) \
                else r.bake(fn, length, looping)
        w = 1150 if view == "side" else 560
        im = r.render(frames[0][2], syms, images, size=(w, H), ground=H - GROUND, scale=1.0, bg=(0, 0, 0, 0),
                      shadow=False, cx=w / 2)
    finally:
        os.chdir(cwd)
        sys.path.remove(os.path.dirname(path))
    bb = im.getbbox()
    return im.crop((bb[0], 0, bb[2], H)) if bb else im


def row(items, label):
    gap = 50
    W = sum(i.width for i, _ in items) + gap * (len(items) + 1)
    out = Image.new("RGBA", (W, H + 30), BG)
    d = ImageDraw.Draw(out)
    d.text((10, 6), label, fill=(0, 0, 0, 255))
    x = gap
    for im, name in items:
        cx = x + im.width / 2
        d.ellipse((cx - im.width * 0.42, 30 + GROUND - 16, cx + im.width * 0.42, 30 + GROUND + 16), fill=SHADOW)
        out.alpha_composite(im, (x, 30))
        d.text((cx - 3 * len(name), 30 + GROUND + 24), name, fill=(0, 0, 0, 255))
        x += im.width + gap
    return out


def main():
    slime = os.path.join(os.path.dirname(ROOT), "chattyslime")
    rows = []
    for view, facing, label in (("side", 5, "side"), ("down", 8, "front")):
        items = [(wilson(facing), "Wilson"), (rig(ROOT, "chattysalamander", view), "Chatty Salamander")]
        if os.path.isdir(slime):
            items.append((rig(slime, "chattyslime", view), "Chatty Slime"))
        rows.append(row(items, f"for scale ({label}): one build pixel a pixel, as in the game"))
    W = max(r.width for r in rows)
    sheet = Image.new("RGBA", (W, sum(r.height for r in rows)), BG)
    y = 0
    for r in rows:
        sheet.alpha_composite(r, (0, y))
        y += r.height
    out = os.path.join(ROOT, "build", "preview", "scale.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.convert("RGB").save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
