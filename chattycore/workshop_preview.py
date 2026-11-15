"""A chatty creature's Steam Workshop preview (1024 x 1024): its name big at the top, a tagline, a player's line in a
dark chip (a speech icon) and the creature's answer in a white speech bubble over it, the creature on a DST-ish
evening backdrop (a dusky sky, rolling hills, a ground with grass tufts), feature chips at the bottom. The layout of
the user's Mochi the Corgi page (the user, 2026-11-05: "a good example is ...?id=3826771785").

    python chattycore/workshop_preview.py <mod>         (conda env pcvoice: Pillow; the mod's SPEC below)
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = H = 1024
TITLE = r"C:\Windows\Fonts\impact.ttf"
BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
TAG = r"C:\Windows\Fonts\bahnschrift.ttf"

SPEC = {
    "chattysalamander": dict(
        name=("GILBERT", " THE SALAMANDER"), accent=(255, 128, 150), tagline="THE AI AXOLOTL YOU CAN TALK TO",
        hero="chattysalamander/tools/workshop/hero.png", hero_w=820, hero_at=(500, 885),
        you='"Gilbert, seen any frogs?"', reply="Hrrm... by the old pond. Come, I'll show you.",
        chips=("VOICE & CHAT", "AI CONVERSATIONS"), sky=((28, 30, 52), (92, 64, 78)), seed=3),
    "chattyslime": dict(
        name=("GUMMY", " THE SLIME"), accent=(150, 222, 96), tagline="THE AI SLIME YOU CAN TALK TO",
        hero="chattyslime/tools/workshop/hero.png", hero_w=440, hero_at=(512, 860),
        you='"Gummy, what\'s your favourite food?"', reply="Berries! Gloop, ALL the berries!",
        chips=("VOICE & CHAT", "AI CONVERSATIONS"), sky=((26, 34, 46), (70, 80, 66)), seed=5),
}


def font(path, size):
    return ImageFont.truetype(path, size)


def lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def backdrop(sky, seed):
    rnd = random.Random(seed)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=lerp(sky[0], sky[1], min(1, y / 640) ** 1.3))
    # (a low sun's glow behind the hills)
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W / 2 - 360, 420, W / 2 + 360, 860), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    im = Image.composite(Image.new("RGB", (W, H), (236, 170, 120)), im, glow)
    d = ImageDraw.Draw(im)
    # (hills, far to near, darker each)
    for k, (base, amp, col) in enumerate(((640, 40, (58, 52, 62)), (680, 34, (44, 44, 46)), (716, 26, (36, 38, 34)))):
        ph = rnd.random() * 6
        pts = [(x, base - amp * math.sin(x / 150 + ph) - amp * 0.4 * math.sin(x / 61 + ph * 2)) for x in range(0, W + 9, 8)]
        d.polygon(pts + [(W, H), (0, H)], fill=col)
        # (a few spiky DST trees on the far hills)
        if k < 2:
            for _ in range(5):
                x = rnd.randint(20, W - 20)
                y = base - amp * math.sin(x / 150 + ph) - 4
                h = rnd.randint(46, 90)
                d.polygon([(x, y - h), (x - h * 0.22, y), (x + h * 0.22, y)], fill=lerp(col, (20, 18, 22), 0.4))
    # (the ground: a DST dirt-and-grass field, its top edge rough)
    gy = 740
    ground = [(x, gy + 6 * math.sin(x / 37) + 4 * math.sin(x / 13)) for x in range(0, W + 9, 8)]
    d.polygon(ground + [(W, H), (0, H)], fill=(86, 74, 48))
    for _ in range(260):                                  # (scratchy strokes, as the game's turf)
        x, y = rnd.randint(0, W), rnd.randint(gy + 10, H)
        l = rnd.randint(6, 18)
        d.line([(x, y), (x + l, y - l * 0.35)], fill=(70, 60, 38), width=2)
    for _ in range(26):                                   # (grass tufts)
        x, y = rnd.randint(0, W), rnd.randint(gy + 20, H - 40)
        for j in range(5):
            a = math.radians(-60 + j * 30)
            d.line([(x, y), (x + 18 * math.sin(a), y - 26 * math.cos(a))], fill=(120, 116, 58), width=3)
    # (a vignette)
    v = Image.new("L", (W, H), 0)
    ImageDraw.Draw(v).ellipse((-220, -160, W + 220, H + 260), fill=255)
    v = v.filter(ImageFilter.GaussianBlur(120))
    im = Image.composite(im, Image.new("RGB", (W, H), (10, 10, 14)), v)
    return im.convert("RGBA")


def shadowed(im, draw_fn, blur=10, offset=(0, 6), alpha=150):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(sh), (0, 0, 0, alpha), offset)
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    draw_fn(ImageDraw.Draw(im), None, (0, 0))


def text_w(f, s):
    return f.getbbox(s)[2] - f.getbbox(s)[0]


def mic_icon(d, cx, cy, r, col, bg):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    d.rounded_rectangle((cx - r * 0.22, cy - r * 0.55, cx + r * 0.22, cy + r * 0.12), r * 0.22, fill=bg)
    d.arc((cx - r * 0.42, cy - r * 0.3, cx + r * 0.42, cy + r * 0.32), 0, 180, fill=bg, width=max(2, int(r * 0.1)))
    d.line([(cx, cy + r * 0.32), (cx, cy + r * 0.52)], fill=bg, width=max(2, int(r * 0.1)))
    d.line([(cx - r * 0.22, cy + r * 0.52), (cx + r * 0.22, cy + r * 0.52)], fill=bg, width=max(2, int(r * 0.1)))


def chat_icon(d, cx, cy, r, col):
    d.rounded_rectangle((cx - r, cy - r * 0.75, cx + r, cy + r * 0.5), r * 0.3, fill=col)
    d.polygon([(cx - r * 0.5, cy + r * 0.45), (cx - r * 0.65, cy + r * 0.95), (cx - r * 0.05, cy + r * 0.45)], fill=col)
    for k in (-1, 0, 1):
        d.ellipse((cx + k * r * 0.45 - r * 0.12, cy - r * 0.25, cx + k * r * 0.45 + r * 0.12, cy - r * 0.01),
                  fill=(26, 30, 40))


def make(mod):
    S = SPEC[mod]
    im = backdrop(S["sky"], S["seed"])
    acc = S["accent"]
    # (the title: the name in the accent colour, the rest white, Impact, shadowed)
    a, b = S["name"]
    size = 120
    while True:                                  # (as big as fits, a margin each side)
        ft = font(TITLE, size)
        wa, wb = text_w(ft, a), text_w(ft, b)
        if wa + wb <= W - 90 or size < 60:
            break
        size -= 4
    x0 = (W - wa - wb) / 2

    def title(d, sh, off):
        d.text((x0 + off[0], 36 + off[1]), a, font=ft, fill=sh or acc)
        d.text((x0 + wa + off[0], 36 + off[1]), b, font=ft, fill=sh or (255, 255, 255))
    shadowed(im, title, blur=8)
    fs = font(TAG, 34)
    tl = S["tagline"]
    spaced = " ".join(tl)
    d = ImageDraw.Draw(im)
    d.text(((W - text_w(fs, spaced)) / 2, 172), spaced, font=fs, fill=(214, 220, 232))
    # (the creature, with a soft shadow on the ground)
    hero = Image.open(os.path.join(ROOT, S["hero"])).convert("RGBA")
    hero = hero.crop(hero.getbbox())
    k = S["hero_w"] / hero.width
    hero = hero.resize((int(hero.width * k), int(hero.height * k)), Image.LANCZOS)
    cx, by = S["hero_at"]
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((cx - hero.width * 0.42, by - 30, cx + hero.width * 0.42, by + 26), fill=(0, 0, 0, 120))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    im.alpha_composite(hero, (int(cx - hero.width / 2), int(by - hero.height)))
    top = by - hero.height
    # (the player's line: a dark chip with a mic icon, top left)
    fb = font(BOLD, 38)
    you = S["you"]
    yw = text_w(fb, you)
    yx, yy = 92, 250

    def chip(d, sh, off):
        d.rounded_rectangle((yx - 40 + off[0], yy + off[1], yx + yw + 44 + off[0], yy + 84 + off[1]), 16,
                            fill=sh or (22, 24, 34, 235))
    shadowed(im, chip)
    d = ImageDraw.Draw(im)
    d.text((yx + 2, yy + 18), you, font=fb, fill=(255, 255, 255))
    mic_icon(d, yx - 40, yy, 34, acc, (22, 24, 34))
    # (its answer: a white bubble over it, its tail pointing down at its head)
    rep = S["reply"]
    fr = font(BOLD, 38)
    lines, cur = [], ""
    for word in rep.split():
        if text_w(fr, (cur + " " + word).strip()) > 600:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    lines.append(cur)
    bw = max(text_w(fr, l) for l in lines) + 64
    bh = 50 * len(lines) + 34
    bx = min(W - 40 - bw, max(300, cx + hero.width * 0.12 - bw / 2))
    byy = max(340, top - bh - 50)
    tipx = min(bx + bw - 60, max(bx + 60, cx + hero.width * 0.28))

    def bubble(d, sh, off):
        f = sh or (255, 255, 255)
        d.rounded_rectangle((bx + off[0], byy + off[1], bx + bw + off[0], byy + bh + off[1]), 18, fill=f)
        d.polygon([(tipx - 26 + off[0], byy + bh - 2 + off[1]), (tipx + 18 + off[0], byy + bh - 2 + off[1]),
                   (tipx - 8 + off[0], byy + bh + 40 + off[1])], fill=f)
    shadowed(im, bubble)
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        d.text((bx + (bw - text_w(fr, l)) / 2, byy + 16 + 50 * i), l, font=fr, fill=(28, 26, 30))
    # (the feature chips)
    fc = font(TAG, 36)
    ws = [text_w(fc, c) for c in S["chips"]]
    gap = 30
    total = sum(w + 110 for w in ws) + gap * (len(ws) - 1)
    x = (W - total) / 2
    for i, (c, w) in enumerate(zip(S["chips"], ws)):
        x1 = x + w + 110

        def ch(d, sh, off, x=x, x1=x1):
            d.rounded_rectangle((x + off[0], 900 + off[1], x1 + off[0], 984 + off[1]), 14, fill=sh or (18, 20, 28, 240))
        shadowed(im, ch)
        d = ImageDraw.Draw(im)
        d.rectangle((x + 14, 976, x1 - 14, 982), fill=acc)
        if i == 0:
            mic_icon(d, x + 48, 942, 22, acc, (18, 20, 28))
        else:
            chat_icon(d, x + 48, 940, 22, acc)
        d.text((x + 84, 920), c, font=fc, fill=(255, 255, 255))
        x = x1 + gap
    out = os.path.join(ROOT, mod, "tools", "workshop", "preview.png")
    im.convert("RGB").save(out)
    print("wrote", out)


if __name__ == "__main__":
    for m in (sys.argv[1:] or list(SPEC)):
        make(m)
