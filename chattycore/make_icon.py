"""A chatty creature's mod icon (the game's mods list: 128 x 128, modicon.png/.tex/.xml - shown as a 70 x 70 square,
no mask): the creature's own in-game art (tools/workshop/hero.png, a frame of its animation), big, in a square with a
thin dark wooden frame - what DST mods' icons are (the user's installed Workshop mods, 2026-11-06: 11 of 12 square and
framed so, none round). The user, 2026-11-06: the slime's old icon - an early design drawing - "doesn't look like the
in-game creature"; Gilbert's - his whole body small in a medallion - "framing is just amateur"; "you don't have to do
medallion style".

    python chattycore/make_icon.py [chattyslime|chattysalamander]      (from dst-mods/; Pillow)
"""
import importlib.util
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 1024

# (the frame, drawn at 1024 and scaled to 128: an ink line, a wooden band lit from the top left, an inner ink line)
INK = (22, 15, 10)
WOOD_DARK, WOOD_LIGHT = (78, 52, 32), (138, 98, 60)
OUT, BAND, IN = 18, 42, 14
EDGE = OUT + BAND + IN              # (the art starts here)

SPEC = {
    # (Gummy: the whole slime, centred; the user, 2026-11-06: "gilbert and gummy are not centered")
    "chattyslime": dict(top=(30, 46, 40), bottom=(84, 104, 56), glow=(200, 240, 160, 110),
                        crop=(0.0, 0.0, 1.0, 1.0), width=720),
    # (Gilbert: his front - head, gills, front legs - centred top to bottom, the cut under the left of the frame, his
    # snout clear of the right)
    "chattysalamander": dict(top=(32, 40, 70), bottom=(84, 96, 64), glow=(255, 200, 180, 100),
                             crop=(0.40, 0.0, 1.0, 1.0), width=850, bleed_left=True,
                             fade_feet=70),
}
INNER = (EDGE, S - EDGE)            # (the art's square, its centre S / 2)


def vgrad(w, h, a, b):
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / (h - 1)
        d.line((0, y, w, y), fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,))
    return im


def draw(mod):
    sp = SPEC[mod]
    # (the inside: the sky's dusk at the top to the ground at the bottom, a soft light behind the creature, the
    # corners darker)
    inside = vgrad(S, S, sp["top"], sp["bottom"])
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((S / 2 - 330, 160, S / 2 + 330, 700), fill=sp["glow"])
    inside.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))
    vig = Image.new("L", (S, S), 0)
    ImageDraw.Draw(vig).ellipse((-160, -160, S + 160, S + 160), fill=255)
    dark = Image.new("RGBA", (S, S), (0, 0, 0, 150))
    dark.putalpha(Image.eval(vig.filter(ImageFilter.GaussianBlur(120)), lambda v: int((255 - v) * 0.6)))
    inside.alpha_composite(dark)
    # (the creature: its in-game art, big, on its shadow)
    hero = Image.open(os.path.join(ROOT, mod, "tools", "workshop", "hero.png")).convert("RGBA")
    hero = hero.crop(hero.getbbox())
    x0, y0, x1, y1 = sp["crop"]
    hero = hero.crop((round(hero.width * x0), round(hero.height * y0), round(hero.width * x1), round(hero.height * y1)))
    k = sp["width"] / hero.width
    hero = hero.resize((round(hero.width * k), round(hero.height * k)), Image.LANCZOS)
    hero = hero.crop(hero.getbbox())
    if sp.get("fade_feet"):             # (its art ends in a straight cut at the feet: faded into the shadow)
        h = sp["fade_feet"]
        alpha = hero.split()[3]
        ramp = Image.linear_gradient("L").resize((hero.width, h)).transpose(Image.FLIP_TOP_BOTTOM)
        fade = Image.new("L", hero.size, 255)
        fade.paste(ramp, (0, hero.height - h))
        hero.putalpha(Image.composite(alpha, Image.new("L", hero.size, 0), fade))
    # (centred in the art's square; a front cut off: its cut just under the left of the frame)
    x = INNER[0] - 12 if sp.get("bleed_left") else round(S / 2 - hero.width / 2)
    y = round(S / 2 - hero.height / 2)
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cx = x + hero.width / 2
    ImageDraw.Draw(shadow).ellipse((cx - hero.width * 0.42, y + hero.height - 45, cx + hero.width * 0.42,
                                    y + hero.height + 25), fill=(10, 8, 4, 120))
    inside.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(20)))
    inside.alpha_composite(hero, (x, y))
    # (the frame)
    im = Image.new("RGBA", (S, S), INK + (255,))
    band = vgrad(S - 2 * OUT, S - 2 * OUT, WOOD_LIGHT, WOOD_DARK)
    im.paste(band, (OUT, OUT))
    ImageDraw.Draw(im).rectangle((OUT + BAND, OUT + BAND, S - OUT - BAND - 1, S - OUT - BAND - 1), fill=INK + (255,))
    im.paste(inside.crop((EDGE, EDGE, S - EDGE, S - EDGE)), (EDGE, EDGE))
    return im


def write(mod):
    spec = importlib.util.spec_from_file_location("ktex", os.path.join(ROOT, mod, "tools", "ktex.py"))
    ktex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ktex)
    big = draw(mod)
    small = big.resize((128, 128), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1, percent=60, threshold=2))
    png = os.path.join(ROOT, mod, "modicon.png")
    small.save(png)
    big.resize((512, 512), Image.LANCZOS).save(os.path.join(ROOT, mod, "tools", "workshop", "icon_512.png"))
    ktex.write(png, os.path.join(ROOT, mod, "modicon.tex"))
    with open(os.path.join(ROOT, mod, "modicon.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write('<Atlas><Texture filename="modicon.tex" /><Elements><Element name="modicon.tex" u1="0" u2="1" v1="0" '
                'v2="1" /></Elements></Atlas>\n')
    print("wrote", png, "(.tex, .xml) and tools/workshop/icon_512.png")


if __name__ == "__main__":
    for m in sys.argv[1:] or list(SPEC):
        write(m)
