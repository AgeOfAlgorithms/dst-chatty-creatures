"""The game's own creatures, drawn: Don't Starve Together's anim zips (build.bin + atlas-N.tex + anim.bin) read and
rendered frame by frame, as references (for the image model: the real style; for the rig: real timing and motion).

    python tools/gen/dstref.py list <zip...>                         the animations in the zips (name, facing, frames)
    python tools/gen/dstref.py draw <out.png> <anim> <frame> <zip...> one frame (the build and bank from the zips)
    python tools/gen/dstref.py strip <out.png> <anim> <zip...>       every 2nd frame of an animation, side by side
    python tools/gen/dstref.py atlas <out_dir> <zip...>              the atlases as PNGs (straight alpha)

build.bin (read from the game's files, 2026-11-04; as ktools' krane reads it): "BILD", u32 version (6), symbols,
frames, the build's name (u32 length + bytes), materials (u32 count, each a name), then per symbol: hash, frames; per
frame: number, duration, f32 x y w h (the bounding box: middle and size), u32 first vertex, vertices; then u32 vertex
count and the vertices (f32 x y z u v w: position in the symbol's space, y down; texture u v, v up; w the atlas);
then the names (u32 count; hash, u32 length, bytes). anim.bin: tools/anim/animbin.py.
"""
import io
import os
import struct
import sys
import zipfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "anim"))
import animbin  # noqa: E402

DATA = r"C:/Program Files (x86)/Steam/steamapps/common/Don't Starve Together/data/anim"


# ---- textures (KTEX: DXT1, DXT5, RGB, RGBA) ----
def _565(c):
    r = ((c >> 11) & 31) * 255 // 31
    g = ((c >> 5) & 63) * 255 // 63
    b = (c & 31) * 255 // 31
    return np.stack([r, g, b], -1).astype(np.int32)


def tex_to_image(b):
    assert b[:4] == b"KTEX"
    h = struct.unpack("<I", b[4:8])[0]
    fmt, mips = (h >> 4) & 0x1F, (h >> 13) & 0x1F
    w, hh, pitch, size = struct.unpack("<HHHI", b[8:18])
    off = 8 + 10 * mips
    data = np.frombuffer(b, np.uint8, size, off)
    if fmt in (0, 1, 2):
        bw, bh = (w + 3) // 4, (hh + 3) // 4
        bs = 8 if fmt == 0 else 16
        blk = data.reshape(bh, bw, bs)
        cb = blk[..., -8:]
        c0 = cb[..., 0].astype(np.int32) | (cb[..., 1].astype(np.int32) << 8)
        c1 = cb[..., 2].astype(np.int32) | (cb[..., 3].astype(np.int32) << 8)
        bits = cb[..., 4].astype(np.uint32) | (cb[..., 5].astype(np.uint32) << 8) | \
            (cb[..., 6].astype(np.uint32) << 16) | (cb[..., 7].astype(np.uint32) << 24)
        p0, p1 = _565(c0), _565(c1)
        four = (c0 > c1)[..., None] | (fmt != 0)
        p2 = np.where(four, (2 * p0 + p1) // 3, (p0 + p1) // 2)
        p3 = np.where(four, (p0 + 2 * p1) // 3, 0)
        pal = np.stack([p0, p1, p2, p3], 2)  # bh bw 4 3
        idx = np.stack([(bits >> (2 * i)) & 3 for i in range(16)], -1).astype(np.int64)  # bh bw 16
        rgb = np.take_along_axis(pal, idx[..., None].repeat(3, -1), 2)  # bh bw 16 3
        if fmt == 2:
            ab = blk[..., :8]
            a0 = ab[..., 0].astype(np.int32)
            a1 = ab[..., 1].astype(np.int32)
            abits = np.zeros(ab.shape[:2], np.uint64)
            for i in range(6):
                abits |= ab[..., 2 + i].astype(np.uint64) << np.uint64(8 * i)
            big = a0 > a1
            apal = [a0, a1]
            for i in range(1, 7):
                eight = ((7 - i) * a0 + i * a1) // 7
                six = ((5 - i) * a0 + i * a1) // 5 if i <= 4 else (0 if i == 5 else 255)
                apal.append(np.where(big, eight, six))
            apal = np.stack(apal, -1)
            aidx = np.stack([(abits >> np.uint64(3 * i)) & np.uint64(7) for i in range(16)], -1).astype(np.int64)
            alpha = np.take_along_axis(apal, aidx, 2)
        elif fmt == 0:
            alpha = np.where((~four[..., 0])[..., None] & (idx == 3), 0, 255)
        else:
            alpha = np.full(idx.shape, 255)
        px = np.concatenate([rgb, alpha[..., None]], -1).reshape(bh, bw, 4, 4, 4)
        px = px.transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)[:hh, :w]
    elif fmt == 4:
        px = data.reshape(hh, w, 4)
    elif fmt == 5:
        px = np.concatenate([data.reshape(hh, w, 3), np.full((hh, w, 1), 255, np.uint8)], -1)
    else:
        raise ValueError(f"tex format {fmt}")
    px = np.ascontiguousarray(px[::-1]).astype(np.float32)  # (stored bottom row first)
    a = px[..., 3:4] / 255.0
    px[..., :3] = np.where(a > 0, np.clip(px[..., :3] / np.maximum(a, 1e-3), 0, 255), 0)  # (premultiplied -> straight)
    return Image.fromarray(px.astype(np.uint8), "RGBA")


# ---- builds ----
def read_build(b):
    assert b[:4] == b"BILD"
    o = 4

    def rd(fmt):
        nonlocal o
        v = struct.unpack_from(fmt, b, o)
        o += struct.calcsize(fmt)
        return v

    ver, nsym, nfr = rd("<3I")
    (n,) = rd("<I")
    name = b[o:o + n].decode()
    o += n
    (nmat,) = rd("<I")
    mats = []
    for _ in range(nmat):
        (n,) = rd("<I")
        mats.append(b[o:o + n].decode())
        o += n
    syms = []
    for _ in range(nsym):
        hsh, nf = rd("<2I")
        frames = [rd("<2I4f2I") for _ in range(nf)]
        syms.append((hsh, frames))
    (nv,) = rd("<I")
    verts = np.frombuffer(b, np.float32, nv * 6, o).reshape(nv, 6)
    o += nv * 24
    (nh,) = rd("<I")
    H = {}
    for _ in range(nh):
        hsh, n = rd("<2I")
        H[hsh] = b[o:o + n].decode()
        o += n
    return name, mats, syms, verts, H


class Build:
    """symbol -> [(frame number, duration, image (RGBA), (x0, y0) its top left in the symbol's space)]"""

    def __init__(self, zpath):
        z = zipfile.ZipFile(zpath)
        self.name, mats, syms, verts, H = read_build(z.read("build.bin"))
        atl = {}
        for i, m in enumerate(mats):
            if m in z.namelist():
                atl[i] = tex_to_image(z.read(m))
        self.atlases = atl
        self.symbols = {}
        for hsh, frames in syms:
            out = []
            for num, dur, x, y, w, h, vs, nv in frames:
                if nv == 0:
                    continue
                v = verts[vs:vs + nv]
                ai = int(round(v[0, 5]))
                if ai not in atl:
                    continue
                A = atl[ai]
                x0, x1, y0, y1 = v[:, 0].min(), v[:, 0].max(), v[:, 1].min(), v[:, 1].max()
                u0, u1, v0, v1 = v[:, 3].min(), v[:, 3].max(), v[:, 4].min(), v[:, 4].max()
                box = (u0 * A.width, (1 - v1) * A.height, u1 * A.width, (1 - v0) * A.height)
                ww, hh = max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0)))
                im = A.resize((ww, hh), Image.BICUBIC, box=box)
                out.append((num, dur, im, (float(x0), float(y0))))
            self.symbols[H.get(hsh, hsh)] = out
            self.symbols[hsh] = out

    def frame(self, sym, f):
        fr = self.symbols.get(sym)
        if not fr:
            return None
        best = fr[0]
        for e in fr:
            if e[0] <= f:
                best = e
        return best


def banks(zips):
    out = []
    for p in zips:
        z = zipfile.ZipFile(p)
        if "anim.bin" in z.namelist():
            tmp = io.BytesIO(z.read("anim.bin"))
            path = os.path.join(os.environ.get("TEMP", "."), "_dstref_anim.bin")
            open(path, "wb").write(tmp.getvalue())
            out += animbin.read(path)
    return out


def render(build, els, size=(600, 500), origin=(300, 420), scale=1.0, bg=(0, 0, 0, 0), hide=()):
    """one frame's elements (front first) onto a canvas; origin: where the creature's (0, 0) goes"""
    canvas = Image.new("RGBA", size, bg)
    for e in reversed(els):
        sym, bf, layer, a, b, c, d, tx, ty = e[:9]
        if sym in hide or layer in hide:
            continue
        fr = build.frame(sym, bf)
        if fr is None:
            continue
        _, _, im, (x0, y0) = fr
        # symbol pixel (u, v) -> symbol space (x0 + u, y0 + v) -> screen (a x + c y + tx, b x + d y + ty) * scale + origin
        M = np.array([[a, c, tx], [b, d, ty], [0, 0, 1]], float)
        T = np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], float)
        S = np.array([[scale, 0, origin[0]], [0, scale, origin[1]], [0, 0, 1]], float)
        F = S @ M @ T
        try:
            inv = np.linalg.inv(F)
        except np.linalg.LinAlgError:
            continue
        layer_im = im.transform(size, Image.AFFINE, tuple(inv[:2].reshape(-1)), Image.BICUBIC)
        canvas.alpha_composite(layer_im)
    return canvas


def find(zips, anim, facing=None):
    for name, fc, fps, frames in banks(zips):
        if name == anim and (facing is None or fc == facing):
            return fps, frames, fc
    raise SystemExit(f"no animation {anim}")


def strip(zips, anim, out, step=2, facing=None, size=(420, 420), origin=(210, 360), scale=0.8, bg=(214, 200, 160, 255)):
    build = Build([p for p in zips if "build.bin" in zipfile.ZipFile(p).namelist()][0])
    fps, frames, fc = find(zips, anim, facing)
    ims = [render(build, els, size, origin, scale, bg) for _, els in frames[::step]]
    W = size[0] * min(len(ims), 8)
    rows = (len(ims) + 7) // 8
    sheet = Image.new("RGBA", (W, size[1] * rows), bg)
    for i, im in enumerate(ims):
        sheet.alpha_composite(im, ((i % 8) * size[0], (i // 8) * size[1]))
    sheet.save(out)
    return fps, len(frames)


def zpath(n):
    return n if os.path.exists(n) else os.path.join(DATA, n if n.endswith(".zip") else n + ".zip")


if __name__ == "__main__":
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "list":
        for name, fc, fps, frames in banks([zpath(z) for z in rest]):
            print(f"{name:40s} facing {fc:3d} fps {fps:4.0f} frames {len(frames)}")
    elif cmd == "draw":
        out, anim, f, zips = rest[0], rest[1], int(rest[2]), [zpath(z) for z in rest[3:]]
        build = Build([p for p in zips if "build.bin" in zipfile.ZipFile(p).namelist()][0])
        fps, frames, fc = find(zips, anim)
        render(build, frames[f][1], bg=(214, 200, 160, 255)).save(out)
    elif cmd == "strip":
        out, anim, zips = rest[0], rest[1], [zpath(z) for z in rest[2:]]
        print(strip(zips, anim, out))
    elif cmd == "atlas":
        od, zips = rest[0], [zpath(z) for z in rest[1:]]
        os.makedirs(od, exist_ok=True)
        for p in zips:
            z = zipfile.ZipFile(p)
            for n in z.namelist():
                if n.endswith(".tex"):
                    tex_to_image(z.read(n)).save(os.path.join(od, os.path.basename(p)[:-4] + "_" + n[:-4] + ".png"))
