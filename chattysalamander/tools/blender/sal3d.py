"""The salamander (axolotl) as one 3D model, so every view comes from the same pose (the side, the front, the back, and
the back half turned off the front's line). Built from the approved side design (tools/gen/sal_vector.py: its canvas
pixels, y down) - 1 Blender unit = 100 canvas px, X forward (the head +X), Z up, the ground at canvas y = GROUND.

Run in Blender:  exec(open(r"<this file>").read()); build(bend=0)
or headless:     blender -b -P tools/blender/sal3d.py -- --bend 30

bend: the back half's yaw at the hips, degrees (+: the hips swing to the creature's left, +Y) - the whole body curves
over the waist like a snake's, the hind legs riding on it.
"""
import math

import os
import sys

import bpy
from mathutils import Vector

_HERE = os.path.dirname(os.path.abspath(globals().get("__file__") or SAL3D_FILE))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "..", "tools", "blender")))
import dst_style as D  # noqa: E402

GROUND = 690.0
WAIST_X = 6.9          # (the waist: where the back half's curve starts, units)
BEND_LEN = 1.6         # (over this much behind the waist the body turns to the hips' heading)
COLL = "Salamander"
TAIL_X = 4.3           # (the tail's root: the tail is its own part behind it, bent for its wave; the waist splits the
#                        body into the front half and the back half)
PART_FRONT, PART_REAR, PART_TAIL = 0, 1, 2
J3 = {}                # (the joints, 3D, as the last build() placed them)


def part_of(x):
    """which part a point of the body (rest x, units) is in"""
    return PART_FRONT if x >= WAIST_X else (PART_REAR if x >= TAIL_X else PART_TAIL)


def U(x, y):
    """canvas px (x, y down) -> (x, z) units"""
    return x / 100.0, (GROUND - y) / 100.0


def interp(pts, x):
    """piecewise linear through [(x, v)] (sorted by x), clamped"""
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, v0), (x1, v1) in zip(pts, pts[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return v0 + (v1 - v0) * t
    return pts[-1][1]


def smooth(pts, x):
    """a smoother interpolation (Catmull-Rom on the values)"""
    xs = [p[0] for p in pts]
    if x <= xs[0]:
        return pts[0][1]
    if x >= xs[-1]:
        return pts[-1][1]
    i = max(k for k in range(len(xs) - 1) if xs[k] <= x)
    p0 = pts[max(i - 1, 0)][1]
    p1, p2 = pts[i][1], pts[i + 1][1]
    p3 = pts[min(i + 2, len(pts) - 1)][1]
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


# --- the shapes, from the side design (canvas px) -------------------------------------------------------------------

BODY_TOP = [(4, 476), (60, 469), (120, 458), (200, 438), (280, 404), (350, 368), (420, 330), (480, 301), (560, 251),
            (620, 231), (700, 213), (780, 198), (860, 186), (940, 181), (1000, 187), (1052, 210), (1082, 300)]
BODY_BOT = [(4, 480), (30, 492), (72, 518), (130, 549), (200, 565), (280, 574), (350, 576), (450, 581), (520, 593),
            (600, 610), (700, 616), (800, 606), (880, 586), (940, 567), (1000, 553), (1046, 538), (1082, 470)]
BODY_HW = [(4, 3), (60, 10), (150, 22), (300, 42), (430, 78), (520, 120), (600, 150), (700, 162), (850, 168),
           (950, 165), (1030, 150), (1082, 100)]

HEAD_TOP = [(928, 262), (945, 214), (970, 196), (1000, 189), (1060, 198), (1110, 214), (1152, 232), (1180, 246), (1206, 244),
            (1234, 254), (1250, 284), (1266, 326), (1280, 370), (1289, 410), (1292, 440)]
HEAD_BOT = [(928, 440), (975, 447), (1040, 466), (1120, 476), (1200, 471), (1240, 463), (1273, 452), (1292, 444)]
HEAD_HW = [(928, 150), (960, 188), (1030, 206), (1100, 200), (1170, 186), (1220, 168), (1260, 140), (1280, 105),
           (1292, 55)]

JAW_TOP = [(962, 452), (1000, 458), (1040, 468), (1120, 478), (1200, 473), (1240, 465), (1267, 470)]
JAW_BOT = [(962, 470), (984, 527), (1010, 541), (1050, 547), (1100, 545), (1150, 539), (1200, 528), (1240, 514),
           (1259, 500), (1267, 484)]
JAW_HW = [(962, 165), (1000, 182), (1100, 188), (1200, 168), (1245, 140), (1267, 90)]

EYE = (1150, 0.62)           # (canvas x along the head, and how far round its top toward the side (0 the top, 1 the
#                               side's middle): up on the head's front corners, frog-like, looking out ahead - seen
#                               from the front as well as the side)
EYE_R = 0.5
# (the lids: each state's upper lid edge top(u) and lower lid edge bot(u), in the eye's own frame - u across it
#  (+: toward the snout), v up it, both in eye radii; None: no lid)
LIDS = {
    "open": (lambda u: 0.55 - 0.08 * u, None),
    "wide": (lambda u: 0.95, None),
    "half": (lambda u: 0.05 - 0.05 * u, None),
    "stern": (lambda u: 0.32 - 0.22 * u, None),
    "angry": (lambda u: 0.22 - 0.5 * u, lambda u: -0.7),
    "sad": (lambda u: 0.28 + 0.45 * u, None),
    "closed": (lambda u: -0.12 - 0.22 * (1 - u * u), lambda u: -0.12 - 0.22 * (1 - u * u)),
    "happy": (lambda u: -0.35 + 0.55 * (1 - u * u), lambda u: -0.35 + 0.55 * (1 - u * u)),
    "squeeze": (lambda u: 0.05 - 0.35 * abs(u), lambda u: 0.05 - 0.35 * abs(u)),
    "dead": (lambda u: 0.15, None),
}
GILLS = [((1004, 300), 28), ((996, 346), 68), ((990, 392), 106)]
GILL_LEN = 1.85


def fin_h(x):
    return interp([(0, 8), (30, 32), (130, 46), (300, 44), (470, 28), (570, 10), (640, 0)], x)


def fin_bot_h(x):
    return interp([(0, 7), (30, 24), (120, 34), (220, 20), (300, 0)], x)


# --- the bend --------------------------------------------------------------------------------------------------------

def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


class Spine:
    """the body's midline bent at the waist: maps a rest point (x along the body, y across, z up) onto it. bend: the
    back half's yaw (degrees); tail: the tail's curl, its tip up (+) or down, degrees, growing toward the tip"""

    def __init__(self, bend, tail=0.0):
        self.bend = math.radians(bend)
        self.tail = math.radians(tail)
        self.zr = (GROUND - smooth(BODY_TOP, TAIL_X * 100) + GROUND - smooth(BODY_BOT, TAIL_X * 100)) / 200
        self.tpts = [(TAIL_X, self.zr, 0.0)]       # (the tail's curl: x, z, angle, back from its root)
        x, z, s = TAIL_X, self.zr, 0.0
        while s < TAIL_X + 0.5:
            th = self.theta(s + 0.01)
            s += 0.02
            x -= math.cos(th) * 0.02
            z += math.sin(th) * 0.02
            self.tpts.append((x, z, self.theta(s)))
        # (sample the curve behind the waist)
        self.ds = 0.02
        self.pts = [(WAIST_X, 0.0, 0.0)]           # (x, y, heading)
        s, x, y = 0.0, WAIST_X, 0.0
        while s < 14.0:
            phi = self.phi(s + self.ds / 2)
            x -= math.cos(phi) * self.ds
            y -= math.sin(phi) * self.ds
            s += self.ds
            self.pts.append((x, y, self.phi(s)))

    def theta(self, s):
        return self.tail * min(max(s / TAIL_X, 0.0), 1.2) ** 1.4

    def pitch(self, x, z):
        """the tail's curl: a rest (x, z) behind its root onto it"""
        if x >= TAIL_X or not self.tail:
            return x, z
        s = TAIL_X - x
        i = min(int(s / 0.02), len(self.tpts) - 2)
        t = s / 0.02 - i
        a, b = self.tpts[i], self.tpts[i + 1]
        cx, cz, th = (a[k] + (b[k] - a[k]) * t for k in range(3))
        dz = z - self.zr
        return cx + math.sin(th) * dz, cz + math.cos(th) * dz

    def phi(self, s):
        return self.bend * (smoothstep(0.0, BEND_LEN, s) + 0.3 * smoothstep(3.0, 6.5, s))

    def frame(self, x):
        """the spine's point and heading at rest x"""
        if x >= WAIST_X:
            return x, 0.0, 0.0
        s = WAIST_X - x
        i = min(int(s / self.ds), len(self.pts) - 2)
        t = s / self.ds - i
        a, b = self.pts[i], self.pts[i + 1]
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t

    def map(self, p, at_x=None):
        """a rest point onto the bent body; at_x: ride rigidly on the frame there (the hind legs)"""
        x, y, z = p
        fx = x if at_x is None else at_x
        cx, cy, h = self.frame(fx)
        xp, z = self.pitch(x, z) if at_x is None else (x, z)
        dx = xp - fx
        c, s = math.cos(h), math.sin(h)
        return Vector((cx + dx * c - y * s, cy + dx * s + y * c, z))


# --- mesh helpers ----------------------------------------------------------------------------------------------------

def coll():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(c)
    return c


def clear():
    c = bpy.data.collections.get(COLL)
    if c:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)


def make(name, verts, faces, mat=None, subsurf=1, smooth_shade=True, parts=None, xpos=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    if parts is not None:
        at = me.attributes.new("sal_part", "INT", "FACE")
        at.data.foreach_set("value", parts)
    if xpos is not None:
        at = me.attributes.new("sal_x", "FLOAT", "FACE")
        at.data.foreach_set("value", xpos)
    if smooth_shade:
        for poly in me.polygons:
            poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll().objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    if subsurf:
        m = ob.modifiers.new("subsurf", "SUBSURF")
        m.levels = subsurf
        m.render_levels = subsurf
    return ob


def superellipse(t, a, b, n_up, n_down):
    c, s = math.cos(t), math.sin(t)
    n = n_up if s >= 0 else n_down
    y = a * math.copysign(abs(c) ** (2.0 / n), c)
    z = b * math.copysign(abs(s) ** (2.0 / n), s)
    return y, z


def loft(name, top, bot, hw, x0, x1, n_st=60, n_ring=40, n_up=2.3, n_down=3.0, round_front=0.0, round_back=0.0,
         spine=None, mat=None, subsurf=1, tag=None):
    """a body of rings across x: each a superellipse between top(x) and bot(x) (canvas y), half wide hw(x) (canvas
    px); the ends rounded over round_* canvas px; the rings mapped onto the spine"""
    verts, faces = [], []
    xs = [x0 + (x1 - x0) * i / (n_st - 1) for i in range(n_st)]
    for x in xs:
        zt, zb = (GROUND - smooth(top, x)) / 100, (GROUND - smooth(bot, x)) / 100
        zc, b = (zt + zb) / 2, max((zt - zb) / 2, 0.005)
        a = max(smooth(hw, x) / 100, 0.005)
        f = 1.0
        if round_front and x > x1 - round_front:
            f = math.sqrt(max(1 - ((x - (x1 - round_front)) / round_front) ** 2, 0.0))
        if round_back and x < x0 + round_back:
            f = math.sqrt(max(1 - (((x0 + round_back) - x) / round_back) ** 2, 0.0))
        f = max(f, 0.03)
        for k in range(n_ring):
            t = 2 * math.pi * k / n_ring
            y, z = superellipse(t, a * f, b * f, n_up, n_down)
            p = (x / 100, y, zc + z)
            verts.append(spine.map(p) if spine else Vector(p))
    parts, xpos = [], []
    for i in range(n_st - 1):
        for k in range(n_ring):
            a0, a1 = i * n_ring + k, i * n_ring + (k + 1) % n_ring
            faces.append((a0, a1, a1 + n_ring, a0 + n_ring))
            parts.append(tag((xs[i] + xs[i + 1]) / 200) if tag else 0)
            xpos.append((xs[i] + xs[i + 1]) / 200)
    # (close both ends with a fan)
    for i, rev in ((0, True), (n_st - 1, False)):
        ring = [i * n_ring + k for k in range(n_ring)]
        c = sum((verts[j] for j in ring), Vector()) / n_ring
        verts.append(c)
        ci = len(verts) - 1
        for k in range(n_ring):
            f = (ring[k], ring[(k + 1) % n_ring], ci)
            faces.append(f[::-1] if rev else f)
            parts.append(tag(xs[i] / 100) if tag else 0)
            xpos.append(xs[i] / 100)
    return make(name, verts, faces, mat, subsurf, parts=parts if tag else None, xpos=xpos if tag else None)


def tube(name, path, radii, n_ring=20, mat=None, subsurf=1, cap=True, map_fn=None):
    """a tube along points (Vectors) with radii, its ends capped round"""
    verts, faces = [], []
    n = len(path)
    for i in range(n):
        d = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        u = d.cross(up).normalized()
        v = d.cross(u).normalized()
        for k in range(n_ring):
            t = 2 * math.pi * k / n_ring
            verts.append(path[i] + (u * math.cos(t) + v * math.sin(t)) * radii[i])
    for i in range(n - 1):
        for k in range(n_ring):
            a0, a1 = i * n_ring + k, i * n_ring + (k + 1) % n_ring
            faces.append((a0, a1, a1 + n_ring, a0 + n_ring))
    if cap:
        for i, rev, out in ((0, True, -1), (n - 1, False, 1)):
            d = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
            c = path[i] + d * out * radii[i] * 0.7
            verts.append(c)
            ci = len(verts) - 1
            for k in range(n_ring):
                f = (i * n_ring + k, i * n_ring + (k + 1) % n_ring, ci)
                faces.append(f[::-1] if rev else f)
    if map_fn:
        verts = [map_fn(v) for v in verts]
    return make(name, verts, faces, mat, subsurf)


def ellipsoid(name, center, size, mat=None, rot=None, map_fn=None, n=24, subsurf=1):
    verts, faces = [], []
    rows = n // 2
    for i in range(rows + 1):
        th = math.pi * i / rows
        for k in range(n):
            ph = 2 * math.pi * k / n
            v = Vector((math.sin(th) * math.cos(ph) * size[0], math.sin(th) * math.sin(ph) * size[1],
                        math.cos(th) * size[2]))
            if rot:
                v = rot @ v
            verts.append(Vector(center) + v)
    for i in range(rows):
        for k in range(n):
            a0, a1 = i * n + k, i * n + (k + 1) % n
            faces.append((a0, a0 + n, a1 + n, a1))
    if map_fn:
        verts = [map_fn(v) for v in verts]
    return make(name, verts, faces, mat, subsurf)


def strip(name, base, tips, thick, mat=None, map_fn=None, tag=None):
    """a thin membrane (a fin) between two polylines, thick across y"""
    verts, faces = [], []
    n = len(base)
    for side in (-1, 1):
        for p in base + tips:
            verts.append(Vector((p[0], p[1] + side * thick / 2, p[2])))
    m = 2 * n
    parts, xpos = [], []
    for i in range(n - 1):
        b0, b1, t0, t1 = i, i + 1, n + i, n + i + 1
        faces.append((b0, b1, t1, t0))                       # (one side)
        faces.append((m + b0, m + t0, m + t1, m + b1))       # (the other)
        faces.append((t0, t1, m + t1, m + t0))               # (the edge)
        faces.append((b0, m + b0, m + b1, b1))
        parts += [tag((base[i][0] + base[i + 1][0]) / 2) if tag else 0] * 4
        xpos += [(base[i][0] + base[i + 1][0]) / 2] * 4
    if map_fn:
        verts = [map_fn(v) for v in verts]
    return make(name, verts, faces, mat, subsurf=0, parts=parts if tag else None, xpos=xpos if tag else None)


# --- materials (plain for now: the look comes later) -----------------------------------------------------------------

def mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*[c / 255 for c in rgb], 1)
    bsdf.inputs["Roughness"].default_value = 0.8
    m.diffuse_color = (*[c / 255 for c in rgb], 1)
    return m


def materials():
    """the design's palette (sal_vector.py), painted DST-style (tools/blender/dst_style.py)"""
    P = D.paint
    return dict(
        skin=P("sal_skin", base=(212, 148, 148), light=(228, 176, 168), shade=(118, 66, 84), top=(176, 110, 120),
               belly=(222, 178, 164), spots=(138, 76, 92), spot_scale=1.3, spot_size=0.3),
        jaw=P("sal_jaw", base=(184, 112, 126), light=(206, 140, 148), shade=(104, 56, 74), belly=(214, 166, 156),
              spots=None),
        fin=P("sal_fin", base=(180, 110, 124), light=(204, 138, 146), shade=(148, 82, 100), mottle=0.0, alpha=0.95),
        gill=P("sal_gill", base=(168, 72, 104), light=(204, 112, 140), shade=(104, 40, 66), mottle=0.0),
        stalk=P("sal_stalk", base=(214, 138, 156), light=(236, 176, 186), shade=(150, 80, 104), mottle=0.0),
        eye=P("sal_eye", base=(34, 18, 26), glow=True),
        mouth=P("sal_mouth", base=(150, 46, 62), light=(186, 76, 88), shade=(96, 26, 42), mottle=0.0, hatch=0.0,
                under=0.0),
        glint=P("sal_glint", base=(255, 250, 236), glow=True),
        claw=P("sal_claw", base=(238, 230, 214), light=(250, 246, 236), shade=(176, 160, 150), mottle=0.0))


def views(out_dir, bend=0.0, elevation=35.0, which=(("side", -90), ("front", 0), ("back", 180)), size=15.0,
          prefix=""):
    """render the views (DST-style) to out_dir/<prefix><name>.png"""
    build(bend=bend)
    D.setup_scene(resolution=(1600, 1100))
    for o in coll().objects:
        if o.name.startswith("nostril") or o.name.endswith("_glint"):
            D.no_ink(o)
        elif o.name.startswith("gill") and o.name.endswith("_vane"):
            D.no_ink(o)                       # (the fringe: its own darker paint, no line - a line goes solid black)
        elif o.name.startswith("gill"):
            D.fine_ink(o, 3.5)
    out = []
    for name, az in which:
        D.camera(target=(6.4, 0, 2.9), azimuth=az, elevation=elevation, size=size)
        out.append(D.render(os.path.join(out_dir, f"{prefix}{name}.png")))
    return out


# --- the parts -------------------------------------------------------------------------------------------------------

def head_surface_y(x, z, frac=1.0):
    """the head's half width at (x, z) units (its superellipse), for placing things on it"""
    xc = x * 100
    zt, zb = (GROUND - smooth(HEAD_TOP, xc)) / 100, (GROUND - smooth(HEAD_BOT, xc)) / 100
    zc, b = (zt + zb) / 2, (zt - zb) / 2
    a = smooth(HEAD_HW, xc) / 100
    u = min(abs((z - zc) / b), 0.999)
    n = 2.2 if z >= zc else 4.0
    return a * (1 - u ** n) ** (1 / n) * frac


def head_frame(x, z, side):
    """the head's surface at (x, z) on a side: the point and its outward normal"""
    e = 0.02
    y = head_surface_y(x, z) * side
    dydx = (head_surface_y(x + e, z) - head_surface_y(x - e, z)) / (2 * e) * side
    dydz = (head_surface_y(x, z + e) - head_surface_y(x, z - e)) / (2 * e) * side
    n = Vector((-dydx, 1.0, -dydz)) * side if side > 0 else Vector((dydx, -1.0, dydz))
    return Vector((x, y, z)), n.normalized()


def head_top_frame(xc, along, side):
    """a point on the head's cross-section at canvas x, `along` of the way round from its top (0) to its side's middle
    (1), and the outward normal there"""
    zt, zb = (GROUND - smooth(HEAD_TOP, xc)) / 100, (GROUND - smooth(HEAD_BOT, xc)) / 100
    zc, b = (zt + zb) / 2, (zt - zb) / 2
    a = smooth(HEAD_HW, xc) / 100
    n_ = 2.1
    t = math.pi / 2 * (1 - along)
    y, z = superellipse(t, a, b, n_, n_)
    gy = n_ * abs(y) ** (n_ - 1) / a ** n_
    gz = n_ * abs(z) ** (n_ - 1) / b ** n_
    # (and the head's slope along x there, its top falling toward the snout)
    e = 2.0
    dz = ((GROUND - smooth(HEAD_TOP, xc + e)) - (GROUND - smooth(HEAD_TOP, xc - e))) / (2 * e)
    n = Vector((-dz * gz * 0.5, gy * side, gz)).normalized()
    return Vector((xc / 100, y * side, zc + z)), n


def sphere_pts(c, r, frame, n_lat=20, n_lon=28):
    """a sphere about c in frame (u, v, w): (verts, faces, local (u, v, w) per vert)"""
    u, v, w = frame
    verts, loc, faces = [], [], []
    for i in range(n_lat + 1):
        th = math.pi * i / n_lat                    # (from the front of the eye (w) round to its back)
        for k in range(n_lon):
            ph = 2 * math.pi * k / n_lon
            lu, lv, lw = math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)
            loc.append((lu, lv, lw))
            verts.append(c + (u * lu + v * lv + w * lw) * r)
    for i in range(n_lat):
        for k in range(n_lon):
            a0, a1 = i * n_lon + k, i * n_lon + (k + 1) % n_lon
            faces.append((a0, a1, a1 + n_lon, a0 + n_lon))
    return verts, faces, loc


def eye(name, side, state, M):
    """an eye: a dark ball sunk in the head's front corner, its lids skin shells over it cut to the state's shape (their
    edges inked), a glint"""
    p, n = head_top_frame(EYE[0], EYE[1], side)
    fwd = Vector((1, 0, 0))
    w = (n + fwd * 0.9).normalized()           # (looking ahead more than up)
    u = (fwd - w * fwd.dot(w)).normalized()
    v = w.cross(u).normalized() * side
    if v.z < 0:
        v = -v
    c = p - w * EYE_R * 0.35
    J3[f"eye_{'LR'[side > 0]}"] = c
    r = EYE_R * (1.08 if state == "wide" else 1.0)
    vs, fs, _ = sphere_pts(c, r, (u, v, w))
    obs = [make(name, vs, fs, M["eye"], subsurf=1)]
    top, bot = LIDS[state]
    for lid, edge, keep in (("lid_t", top, lambda lu, lv, e: lv > e), ("lid_b", bot, lambda lu, lv, e: lv < e)):
        if edge is None:
            continue
        vs, fs, loc = sphere_pts(c, r * 1.07, (u, v, w), 32, 40)
        kept = []
        for f in fs:
            lu = sum(loc[i][0] for i in f) / 4
            lv = sum(loc[i][1] for i in f) / 4
            lw = sum(loc[i][2] for i in f) / 4
            if lw < -0.3 or keep(lu, lv, edge(max(-1.0, min(1.0, lu)))):
                kept.append(f)
        obs.append(make(f"{name}_{lid}", vs, kept, M["skin"], subsurf=1))
    if state == "dead":
        for a in (1, -1):
            d = (u + v * a).normalized()
            q = c + w * r * 1.02
            obs.append(tube(f"{name}_x{a}", [q - d * r * 0.7, q, q + d * r * 0.7], [0.05, 0.06, 0.05], n_ring=8,
                            mat=M["eye"], subsurf=0))
    if state in ("open", "wide", "half", "stern", "angry", "sad", "dead") and state != "dead":
        g = c + (w * 0.9 + v * 0.35 + u * 0.15).normalized() * r
        obs.append(ellipsoid(f"{name}_glint", g, (0.09, 0.09, 0.09), M["glint"], subsurf=0))
    return obs


def gill(name, root, angle, side, m_stalk, m_vane, d=None, nrm=None, droop=True):
    """a gill: a stalk from the head's side fanned up and back (angle from straight up, toward the tail), splayed out
    sideways; a feathered vane about it, facing half out and half forward (seen from the side and the front).
    d, nrm: the stalk's direction and the vane's facing given instead (the rig's one gill, drawn straight up the
    screen and facing it); droop: the tips' droop back"""
    a = math.radians(angle)
    d = d.normalized() if d is not None else Vector((-math.sin(a), side * 0.85, math.cos(a))).normalized()
    nrm = nrm if nrm is not None else Vector((0.8, side * 0.55, 0.25))
    nrm = (nrm - d * nrm.dot(d)).normalized()
    dr = Vector((-0.25, 0, -0.12)) if droop else Vector((0, 0, 0))
    s = d.cross(nrm).normalized()
    path, radii = [], []
    N = 14
    for i in range(N):
        t = i / (N - 1)
        # (a little curve: the tips droop back)
        p = root + d * GILL_LEN * t + dr * t * t
        path.append(p)
        radii.append(0.075 * (1 - 0.55 * t))
    tube(name + "_stalk", path, radii, n_ring=8, mat=m_stalk, subsurf=1)
    # (the vane: a serrated leaf about the stalk - fringe filaments, as zigzags of its edge)
    verts, faces = [], []
    M = 40
    for i in range(M):
        t = 0.1 + 0.9 * i / (M - 1)
        p = root + d * GILL_LEN * t + dr * t * t
        w = 0.46 * math.sin(math.pi * min(t * 1.05, 1.0)) ** 0.7 + 0.05
        w *= 1.0 if i % 2 == 0 else 0.62                           # (the fringe: every other point in)
        back = -d * (0.12 if i % 2 == 0 else 0.0)                   # (the filaments raked toward the tip... back)
        for sd in (-1, 1):
            verts.append(p + s * sd * w + back)
        verts.append(p)
    for i in range(M - 1):
        L0, C0, R0 = 3 * i, 3 * i + 2, 3 * i + 1
        L1, C1, R1 = 3 * i + 3, 3 * i + 5, 3 * i + 4
        faces.append((L0, L1, C1, C0))
        faces.append((C0, C1, R1, R0))
    ob = make(name + "_vane", verts, faces, m_vane, subsurf=0)
    sol = ob.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.03
    return ob


def leg(name, hip, knee, ankle, foot, r, side, m_skin, m_claw, spine, at_x, toe_dir=0.0):
    """a stout leg: hip -> knee -> ankle (units, rest), a flat foot, four toes with claws; riding on the spine at at_x"""
    mp = (lambda v: spine.map(v, at_x)) if spine else None
    pts = []
    for a, b, n in ((hip, knee, 6), (knee, ankle, 6)):
        for i in range(n):
            t = i / n
            pts.append(Vector(a).lerp(Vector(b), t))
    pts.append(Vector(ankle))
    rr = []
    for i in range(len(pts)):
        t = i / (len(pts) - 1)
        rr.append(r[0] + (r[1] - r[0]) * min(t * 2, 1) + (r[2] - r[1]) * max(t * 2 - 1, 0))
    tube(name, pts, rr, n_ring=20, mat=m_skin, map_fn=mp)
    fx, fy, fz = foot
    ellipsoid(name + "_foot", (fx, fy, fz), (0.62, 0.5, 0.22), m_skin, map_fn=mp)
    for i in range(4):
        a = math.radians(-42 + i * 28 + toe_dir) * side
        dirv = Vector((math.cos(a), math.sin(a), 0))
        base = Vector((fx, fy, 0.16)) + dirv * 0.35
        tip = base + dirv * 0.42 + Vector((0, 0, -0.08))
        tube(name + f"_toe{i}", [base, base.lerp(tip, 0.5), tip], [0.13, 0.11, 0.08], n_ring=10, mat=m_skin,
             map_fn=mp)
        cbase = tip
        ctip = tip + dirv * 0.2 + Vector((0, 0, -0.07))
        tube(name + f"_claw{i}", [cbase, cbase.lerp(ctip, 0.5), ctip], [0.07, 0.045, 0.01], n_ring=8, mat=m_claw,
             subsurf=0, map_fn=mp)


def zmid(xc):
    return (GROUND - smooth(BODY_TOP, xc) + GROUND - smooth(BODY_BOT, xc)) / 200


def build(bend=0.0, eyes="open", tail=0.0, stump=False):
    """the whole creature, its back half bent `bend` degrees, its eyes `eyes` (LIDS), its tail curled `tail` degrees;
    stump: the tail dropped (a stump healed over where it was). Sets J3, the joints."""
    clear()
    sp = Spine(bend, tail)
    M = materials()
    J3.clear()
    J3.update(body=Vector((WAIST_X, 0, zmid(WAIST_X * 100))), head=Vector((10.1, 0, 2.75)),
              jaw=Vector((9.75, 0, 2.4)), lip=Vector((12.4, 0, 2.2)), spine=sp)
    J3["tail"] = sp.map((TAIL_X, 0, zmid(TAIL_X * 100)))
    for i, x in enumerate((4.25, 2.75, 1.6)):
        J3[f"tail{i + 1}"] = sp.map((x, 0, zmid(x * 100)))
    # (the body and the tail: one surface, its faces tagged front half, back half, tail; or, the tail dropped, the
    #  back half ends in a stump)
    if stump:
        loft("body", BODY_TOP, BODY_BOT, BODY_HW, TAIL_X * 100 - 40, 1082, n_st=80, round_front=60, round_back=55,
             spine=sp, mat=M["skin"], tag=part_of)
    else:
        loft("body", BODY_TOP, BODY_BOT, BODY_HW, 4, 1082, n_st=90, round_front=60, spine=sp, mat=M["skin"],
             tag=part_of)
    # (the fins: along the back, under the tail)
    base, tips = [], []
    x0f = TAIL_X * 100 - 10 if stump else 4
    for i in range(60):
        x = x0f + (640 - x0f) * i / 59
        zt = (GROUND - smooth(BODY_TOP, x)) / 100
        h = fin_h(x) * (1 + 0.1 * math.sin(x * 0.045)) / 100
        base.append((x / 100, 0, zt - 0.1))
        tips.append((x / 100, 0, zt + h))
    strip("fin_top", base, tips, 0.05, M["fin"], map_fn=sp.map, tag=part_of)
    if not stump:
        base, tips = [], []
        for i in range(30):
            x = 4 + (300 - 4) * i / 29
            zb = (GROUND - smooth(BODY_BOT, x)) / 100
            base.append((x / 100, 0, zb + 0.1))
            tips.append((x / 100, 0, zb - fin_bot_h(x) / 100))
        strip("fin_bot", base, tips, 0.05, M["fin"], map_fn=sp.map, tag=part_of)
    # (the mouth's inside: under the lip, behind the jaw - it shows as the jaw drops)
    loft("mouth", [(x, y - 4) for x, y in HEAD_BOT], [(x, y + 62) for x, y in HEAD_BOT],
         [(x, w * 0.82) for x, w in JAW_HW], 975, 1262, n_st=30, n_up=3.0, n_down=2.2, round_front=30,
         round_back=20, mat=M["mouth"])
    # (the head, the jaw: on the front half - unbent)
    loft("head", HEAD_TOP, HEAD_BOT, HEAD_HW, 928, 1292, n_st=50, n_up=2.1, n_down=4.0, round_front=85,
         round_back=30, mat=M["skin"])
    loft("jaw", JAW_TOP, JAW_BOT, JAW_HW, 962, 1267, n_st=40, n_up=4.0, n_down=2.4, round_front=40, round_back=20,
         mat=M["jaw"])
    # (the eyes)
    for side in (-1, 1):
        eye(f"eye{'LR'[side > 0]}", side, eyes, M)
    # (the fangs: on the upper lip, pointing down)
    for fxc, half, length in ((1146, 13, 30), (1206, 11, 24)):
        fx, fz = U(fxc, 466)
        for side in (-1, 1):
            y = head_surface_y(fx, fz + 0.05) * 0.93 * side
            tube(f"fang{fxc}{side}", [Vector((fx, y, fz + 0.04)), Vector((fx, y, fz - length / 200)),
                                      Vector((fx, y, fz - length / 100))], [half / 100, half / 170, 0.01],
                 n_ring=8, mat=M["claw"], subsurf=0)
    # (the nostrils)
    for side in (-1, 1):
        ellipsoid(f"nostril{side}", (12.78, side * 0.42, 3.0), (0.05, 0.05, 0.04), M["eye"], subsurf=0)
    # (the gills: three a side)
    for i, ((gx, gy), ang) in enumerate(GILLS):
        x, z = U(gx, gy)
        for side in (-1, 1):
            y = head_surface_y(x + 0.1, z) * 0.85 * side
            root = Vector((x, y, z))
            gill(f"gill{i}{'LR'[side > 0]}", root, ang, side, M["stalk"], M["gill"])
            a = math.radians(ang)
            J3[f"gill_{'LR'[side > 0]}{i}"] = root
            J3[f"gilldir_{'LR'[side > 0]}{i}"] = Vector((-math.sin(a), side * 0.85, math.cos(a))).normalized()
    # (the legs: the front pair on the front half, the hind pair riding on the bent body at the hips)
    for side in (-1, 1):
        leg(f"leg_f{'LR'[side > 0]}", (7.7, side * 1.4, 2.1), (7.85, side * 2.0, 1.2), (8.15, side * 2.3, 0.42),
            (8.5, side * 2.5, 0.2), (0.6, 0.5, 0.42), side, M["skin"], M["claw"], None, None)
        ellipsoid(f"shoulder{'LR'[side > 0]}", (7.75, side * 1.4, 2.05), (0.72, 0.6, 0.8), M["skin"])
        leg(f"leg_b{'LR'[side > 0]}", (4.85, side * 1.1, 2.0), (4.9, side * 1.5, 1.1), (5.05, side * 1.7, 0.42),
            (5.4, side * 1.85, 0.2), (0.9, 0.7, 0.48), side, M["skin"], M["claw"], sp, 4.87)
        ellipsoid(f"thigh{'LR'[side > 0]}", (4.87, side * 1.1, 2.2), (1.08, 0.78, 1.05), M["skin"],
                  map_fn=lambda v: sp.map(v, 4.87))
        J3[f"leg_f{'LR'[side > 0]}"] = Vector((7.75, side * 1.4, 2.05))
        J3[f"leg_b{'LR'[side > 0]}"] = sp.map((4.87, side * 1.1, 2.2), 4.87)
    return sp


if __name__ == "__main__":
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    b = float(argv[argv.index("--bend") + 1]) if "--bend" in argv else 0.0
    build(bend=b)


# --- the dropped tail (the decoy: scripts/chattysalamander/tail.lua) ---------------------------------------------

DECOY_PHASES = 8
DECOY_YAW = -28.0          # (degrees: its root end turned toward us)


def build_decoy(phase=0.0, amp=0.45, hop=0.0):
    """the tail on its own, dropped: fallen on its side, its flat paddle on the ground (a salamander's tail is tall and
    thin), thrashing - an S along it across the ground (`amp` units at most, at `phase` of its cycle), its tip
    slapping up `hop` units; its root end raw (a dark red cut). Its middle at x = 0, the ground at z = 0."""
    clear()
    M = materials()
    xr = TAIL_X * 100 + 10
    L = TAIL_X

    def mp(v):
        x, y, z = v
        u = min(max((TAIL_X - x) / L, 0.0), 1.0)          # (0 at the root, 1 at the tip)
        w = amp * math.sin(2 * math.pi * (0.85 * u - phase)) * (0.35 + 0.65 * u)
        half = max(smooth(BODY_HW, x * 100) / 100, 0.02)  # (its thickness, now upward)
        up = hop * u * u * max(0.0, math.sin(2 * math.pi * phase))
        # (on its side: its height lies across the ground, its thickness stands up from it)
        q = Vector((x - TAIL_X / 2, (z - zmid(x * 100)) + w, y + half + up))
        # (turned a little, so its cut end shows)
        c_, s_ = math.cos(math.radians(DECOY_YAW)), math.sin(math.radians(DECOY_YAW))
        return Vector((q.x * c_ - q.y * s_, q.x * s_ + q.y * c_, q.z))
    loft("decoy", BODY_TOP, BODY_BOT, BODY_HW, 4, xr, n_st=50, round_back=0, mat=M["skin"])
    ob = bpy.data.objects["decoy"]
    for v in ob.data.vertices:
        v.co = mp(v.co)
    base, tips = [], []
    for i in range(40):
        x = 4 + (xr - 14) * i / 39
        zt = (GROUND - smooth(BODY_TOP, x)) / 100
        h = fin_h(x) * (1 + 0.1 * math.sin(x * 0.045)) / 100
        base.append((x / 100, 0, zt - 0.1))
        tips.append((x / 100, 0, zt + h))
    strip("decoy_fin", base, tips, 0.05, M["fin"], map_fn=mp)
    base, tips = [], []
    for i in range(30):
        x = 4 + (300 - 4) * i / 29
        zb = (GROUND - smooth(BODY_BOT, x)) / 100
        base.append((x / 100, 0, zb + 0.1))
        tips.append((x / 100, 0, zb - fin_bot_h(x) / 100))
    strip("decoy_finb", base, tips, 0.05, M["fin"], map_fn=mp)
    # (the cut: a raw end)
    zc = zmid(xr)
    a = smooth(BODY_HW, xr) / 100
    b = ((GROUND - smooth(BODY_BOT, xr)) - (GROUND - smooth(BODY_TOP, xr))) / 200
    c = mp((xr / 100 + 0.01, 0, zc))
    ellipsoid("decoy_cut", c, (0.05, b * 0.92, a * 0.92), M["mouth"])
    return [o for o in coll().objects]
