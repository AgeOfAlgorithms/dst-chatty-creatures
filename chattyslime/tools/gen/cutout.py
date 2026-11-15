"""A generated drawing (ink on plain white) to a transparent PNG, cropped; and smooth warps of one (the body's shapes).

    python tools/gen/cutout.py in.png out.png [--width 250]

The background: the near-white pixels joined to the picture's edge (white inside the outline - an eyeball, a
highlight - stays). Its edge is unblended: a pixel there is ink over white, its alpha 1 - its brightness, its colour
what the ink was. width: scaled to that many pixels across (LANCZOS, after cutting: a clean edge).
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage


def cutout(im, white=0.84, grey=0.12, with_offset=False):
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255
    mn, mx = a.min(-1), a.max(-1)
    cand = (mn > white) & (mx - mn < grey)
    lab, n = ndimage.label(cand)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(edge))
    # (a band either side of the background's edge: blended)
    near = ndimage.binary_dilation(bg, iterations=2) & ~ndimage.binary_erosion(bg, iterations=2)
    alpha = np.where(bg, 0.0, 1.0)
    blend = np.clip((1 - mn) / (1 - 0.35), 0, 1)                   # (white -> 0 ... ink and colour -> 1)
    alpha = np.where(near, np.where(bg, blend * (mn < white + 0.08), np.maximum(blend, 0.0)), alpha)
    alpha = np.where(near & ~bg, np.maximum(alpha, ndimage.binary_erosion(~bg, iterations=1) * 1.0), alpha)
    al = alpha[..., None]
    rgb = np.where(al > 0.02, (a - (1 - al)) / np.maximum(al, 0.02), 0)
    out = np.concatenate([np.clip(rgb, 0, 1), alpha[..., None]], -1)
    img = Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")
    bb = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox() or (0, 0, img.width, img.height)
    return (img.crop(bb), bb[:2]) if with_offset else img.crop(bb)


def largest(img, with_offset=False):
    """only the biggest connected piece (strays dropped), cropped (with_offset: and where the crop's top left was)"""
    a = np.asarray(img).copy()
    lab, n = ndimage.label(a[..., 3] > 24)
    if n > 1:
        sizes = ndimage.sum(np.ones(lab.shape), lab, range(1, n + 1))
        keep = ndimage.binary_dilation(lab == (int(np.argmax(sizes)) + 1), iterations=2)
        a[..., 3] = (a[..., 3] * keep).astype(np.uint8)
    im = Image.fromarray(a, "RGBA")
    bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox() or (0, 0, im.width, im.height)
    return (im.crop(bb), bb[:2]) if with_offset else im.crop(bb)


def scaled(img, width):
    k = width / img.width
    size = (max(1, round(img.width * k)), max(1, round(img.height * k)))
    a = premul(img)
    ch = [np.asarray(Image.fromarray(a[..., c], "F").resize(size, Image.LANCZOS)) for c in range(4)]
    return unpremul(np.stack(ch, -1))


def premul(img):
    a = np.asarray(img).astype(np.float32) / 255
    a[..., :3] *= a[..., 3:4]
    return a


def unpremul(a):
    if isinstance(a, Image.Image):
        a = np.asarray(a).astype(np.float32) / 255
    a = np.clip(a, 0, 1)
    al = a[..., 3:4]
    rgb = np.where(al > 1e-3, a[..., :3] / np.maximum(al, 1e-3), 0)
    return Image.fromarray((np.concatenate([np.clip(rgb, 0, 1), al], -1) * 255 + 0.5).astype(np.uint8), "RGBA")


def warp(img, inv, size, origin):
    """img's pixels moved: inv(X, Y) -> (x, y), arrays of output points (y up from the origin, in pixels) to where
    they come from in img (the same: y up from img's bottom middle). size: the output (w, h); origin: where its
    (0, 0) is, from its bottom left"""
    a = premul(img)
    W, H = size
    X, Y = np.meshgrid(np.arange(W) + 0.5 - origin[0], (H - np.arange(H) - 0.5) - origin[1])
    sx, sy = inv(X, Y)
    col = sx + img.width / 2 - 0.5
    row = img.height - sy - 0.5
    pm = np.stack([ndimage.map_coordinates(a[..., c], [row, col], order=3, mode="constant", cval=0.0)
                   for c in range(4)], -1)
    return unpremul(np.clip(pm, 0, 1))


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    im = cutout(Image.open(src))
    if "--width" in sys.argv:
        im = scaled(im, int(sys.argv[sys.argv.index("--width") + 1]))
    im.save(dst)
    print(dst, im.size)
