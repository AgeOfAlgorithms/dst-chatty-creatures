"""Don't Starve Together's anim.bin, read and written: the animations of a bank, frame by frame, each element a
symbol's frame with a full 2 x 2 matrix (so shear too, which a Spriter file cannot give) and a translation.

The format (read from the game's files and from what the Mod Tools' scml.exe writes, 2026-11-04): "ANIM", then u32s
version (4), elements in all, frames in all, events (0), animations. Each animation: its name (u32 length + bytes),
facings (u8: 1 right, 2 up, 4 left, 8 down, ...; 255 all, 5 the side, 2 up, 8 down), the bank's hash (u32), frame
rate (f32), frames (u32). Each frame: its bounding box (f32 x, y, w, h: the middle and size), events (u32, 0), elements
(u32), each: symbol hash, build frame, layer hash (u32s), then f32 a, b, c, d, tx, ty, z. Elements come front first;
y is down; a point (x, y) of the symbol's frame goes to (a x + c y + tx, b x + d y + ty). Last, the names: a u32
count, each a u32 hash, a u32 length and the bytes. The hash is the game's (sdbm, of the lower-cased name)."""
import struct


def khash(s):
    h = 0
    for ch in s.lower():
        h = (ord(ch) + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
    return h


def write(path, bank, anims):
    """anims: [(name, facing, fps, frames)] or [(name, facing, fps, frames, bank)] (several banks in one file); a frame
    is (bbox, elements), an element (symbol, build_frame, layer, a, b, c, d, tx, ty), front first"""
    names = {bank}
    n_el = n_fr = 0
    body = bytearray()
    for name, facing, fps, frames, *own in anims:
        bk = own[0] if own else bank
        names.add(bk)
        nb = name.encode()
        body += struct.pack("<I", len(nb)) + nb
        body += struct.pack("<BIfI", facing, khash(bk), fps, len(frames))
        for bbox, els in frames:
            body += struct.pack("<4f", *bbox)
            body += struct.pack("<I", 0)
            body += struct.pack("<I", len(els))
            n = len(els)
            for i, (sym, bf, layer, a, b, c, d, tx, ty) in enumerate(els):
                names.add(sym)
                names.add(layer)
                z = -5 + 10 * i / max(n, 1)
                body += struct.pack("<3I7f", khash(sym), bf, khash(layer), a, b, c, d, tx, ty, z)
            n_el += n
            n_fr += 1
    out = bytearray(b"ANIM") + struct.pack("<5I", 4, n_el, n_fr, 0, len(anims)) + body
    out += struct.pack("<I", len(names))
    for s in sorted(names):
        sb = s.encode()
        out += struct.pack("<2I", khash(s), len(sb)) + sb
    with open(path, "wb") as f:
        f.write(out)


def read(path):
    """[(name, facing, fps, [(bbox, [(symbol, build_frame, layer, a, b, c, d, tx, ty, z)])])]"""
    b = open(path, "rb").read()
    assert b[:4] == b"ANIM"
    o = 4

    def rd(fmt):
        nonlocal o
        v = struct.unpack_from(fmt, b, o)
        o += struct.calcsize(fmt)
        return v

    ver, ne, nf, nev, na = rd("<5I")
    raw = []
    for _ in range(na):
        (n,) = rd("<I")
        name = b[o:o + n].decode()
        o += n
        facing, root, fps, frames = rd("<BIfI")
        fr = []
        for _ in range(frames):
            bbox = rd("<4f")
            (ev,) = rd("<I")
            o += 4 * ev
            (nel,) = rd("<I")
            fr.append((bbox, [rd("<3I7f") for _ in range(nel)]))
        raw.append((name, facing, fps, fr))
    (nh,) = rd("<I")
    H = {}
    for _ in range(nh):
        h, n = rd("<2I")
        H[h] = b[o:o + n].decode()
        o += n
    return [(name, facing, fps, [(bbox, [(H.get(e[0], e[0]), e[1], H.get(e[2], e[2])) + tuple(e[3:]) for e in els])
                                 for bbox, els in fr]) for name, facing, fps, fr in raw]
