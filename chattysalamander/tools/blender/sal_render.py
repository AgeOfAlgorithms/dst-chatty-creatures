"""Render the salamander's parts for the rig (tools/anim/rig.py) from its 3D model (sal3d.py): each part on its own, as
Klei's puppets are cut out, from each of the game's three views (side, down: toward us, up: away), DST-style
(tools/blender/dst_style.py), at the build's size x SS -> art/parts3d/raw/*.png and manifest.json; then
tools/blender/sal_post.py shrinks them and writes art/parts3d/<symbol>/<frame>.png and parts.json.

    blender -b -P tools/blender/sal_render.py -- [--views side,down,up] [--quick]

How the parts are cut:
- parts that move against each other (the head, the jaw, the legs, the gills, the eyes) are whole, so nothing is missing
  when they turn; what of them is inside what they're attached to is hidden (that is held out), so they meet it with no
  line, as in the whole model.
- the body is one mesh, cut by its faces into the front half, the back half and the tail: each drawn with the others
  held out, so the three fit exactly, with no line between them (they don't move against each other: the tail changes
  frames, its curl, and its root doesn't move).
- the back half's parts (its body, the hind legs, the tail) are rendered at each bend (BINS: how far the hips have
  swung off the front's line), the tail at each curl (TAILS): the game picks the bend, the rig the curl.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sal3d as M3  # noqa: E402

D = M3.D
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "art", "parts3d", "raw")

B = 68.75             # (build px a Blender unit: the design's canvas px x 0.6875, 100 canvas px a unit)
SS = 2                # (rendered at SS x, shrunk after: smooth lines)
ELEV = 35.0           # (the camera's pitch)
VIEWS = {"side": -90.0, "down": 0.0, "up": 180.0}
LEFT = {"down": -1, "up": 1}      # (which side of the creature (-1: its right, the model's -Y) is on the screen's left)
BINS = [-50.0, -37.5, -25.0, -12.5, 0.0, 12.5, 25.0, 37.5, 50.0]
TAILS = [-1.0, -0.67, -0.33, 0.0, 0.33, 0.67, 1.0]
TAIL_BEND = 40.0      # (degrees the tip curls at TAILS +-1)
LINE = 0.1            # (the ink's width, units)
PAD = 0.22            # (units around a part: its line, the line's wobble)

manifest = {"B": B, "SS": SS, "elev": ELEV, "bins": BINS, "tails": TAILS, "tail_bend": TAIL_BEND, "parts": [],
            "joints": {}, "views": {}, "rear": {}}


# --- the camera ------------------------------------------------------------------------------------------------------

def basis(view):
    a, e = math.radians(VIEWS[view]), math.radians(ELEV)
    toward = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))     # (to the camera)
    f = -toward
    r = f.cross(Vector((0, 0, 1))).normalized()
    u = r.cross(f).normalized()
    return r, u, f


ORIGIN = Vector((M3.WAIST_X, 0.0, 0.0))     # (the rig's origin: the ground under the waist)


def proj(view, p):
    """a 3D point -> the rig's build px (y up), from the ground under the waist"""
    r, u, _ = basis(view)
    d = Vector(p) - ORIGIN
    return [d.dot(r) * B, d.dot(u) * B]


# --- holdout, face marks ---------------------------------------------------------------------------------------------

def holdout_mat():
    m = bpy.data.materials.get("DST_holdout")
    if m is None:
        m = bpy.data.materials.new("DST_holdout")
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        h = nt.nodes.new("ShaderNodeHoldout")
        nt.links.new(h.outputs[0], o.inputs["Surface"])
    return m


def objs():
    return list(M3.coll().objects)


def setup_lines():
    D.setup_scene(resolution=(64, 64))
    fs = bpy.context.scene.view_layers[0].freestyle_settings
    for o in objs():
        if o.name.startswith("nostril") or o.name.endswith("_glint"):
            D.no_ink(o)
        elif o.name.startswith("gill") and o.name.endswith("_vane"):
            D.no_ink(o)
        elif o.name.startswith("gill"):
            D.fine_ink(o, 3.5)
    for l in fs.linesets:
        l.select_by_face_marks = True
        l.face_mark_negation = "INCLUSIVE"
        l.face_mark_condition = "ONE"
        l.select_border = False
        l.select_external_contour = False
    px = LINE * B * SS
    for name, k in (("DST_ink", 1.0), ("DST_sketch", 0.4), ("DST_fine", 0.27)):
        ls = bpy.data.linestyles.get(name)
        if ls:
            ls.thickness = px * k


def marks(ob, vals):
    me = ob.data
    at = me.attributes.get("freestyle_face") or me.attributes.new("freestyle_face", "BOOLEAN", "FACE")
    at.data.foreach_set("value", vals)


def stage(draw, hold=(), faces=None):
    """draw: the objects drawn; hold: objects that hide what's behind them, not drawn; faces: {object: part ids} -
    of a split mesh only those faces drawn, its others held out"""
    faces = faces or {}
    hm = holdout_mat()
    draw, hold = set(draw), set(hold)
    for o in objs():
        o.hide_render = o not in draw and o not in hold
        o.is_holdout = False
        n = len(o.data.polygons)
        me = o.data
        # (a holdout's faces: the holdout material - an object held out as a whole Freestyle doesn't see, and the
        #  lines behind it would show)
        hslot = None
        if o in hold and o not in draw or (o in draw and o in faces):
            if hm.name not in [m.name for m in me.materials if m]:
                me.materials.append(hm)
            hslot = [m.name if m else "" for m in me.materials].index(hm.name)
        if o in hold and o not in draw:
            me.polygons.foreach_set("material_index", [hslot] * n)
            marks(o, [False] * n)
        elif o in draw and o in faces:
            me = o.data
            if len(me.materials) < 2:
                me.materials.append(hm)
            parts = [0] * n
            me.attributes["sal_part"].data.foreach_get("value", parts)
            xs = [0.0] * n
            me.attributes["sal_x"].data.foreach_get("value", xs)
            on = [drawn(p, x, faces[o]) for p, x in zip(parts, xs)]
            me.polygons.foreach_set("material_index", [0 if v else hslot for v in on])
            marks(o, on)
        else:
            if len(me.materials) > 1:
                me.polygons.foreach_set("material_index", [0] * n)
            marks(o, [o in draw] * n)
        o.data.update()


SEAMS = ((M3.PART_FRONT, M3.PART_REAR, M3.WAIST_X), (M3.PART_REAR, M3.PART_TAIL, M3.TAIL_X))
OVERLAP = 0.14        # (units a split part goes on past its seam, under its neighbour: no hairline gap between them)


def drawn(p, x, parts):
    if p in parts:
        return True
    for a, b, at in SEAMS:
        if abs(x - at) < OVERLAP and ((p == a and b in parts) or (p == b and a in parts)):
            return True
    return False


def bounds(view, draw, faces=None):
    """the drawn geometry's extent on the screen (units: right, up from the origin)"""
    r, u, _ = basis(view)
    dg = bpy.context.evaluated_depsgraph_get()
    xs, ys = [], []
    for o in draw:
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        mw = eo.matrix_world
        if faces and o in faces:
            at = me.attributes.get("sal_part")
            keep = set()
            if at is not None:
                for poly in me.polygons:
                    if at.data[poly.index].value in faces[o]:
                        keep.update(poly.vertices)
            vs = [me.vertices[i].co for i in keep] if keep else [v.co for v in me.vertices]
        else:
            vs = [v.co for v in me.vertices]
        for c in vs:
            d = mw @ c - ORIGIN
            xs.append(d.dot(r))
            ys.append(d.dot(u))
        eo.to_mesh_clear()
    return min(xs) - PAD, max(xs) + PAD, min(ys) - PAD, max(ys) + PAD


def shoot(symbol, frame, view, draw, hold=(), faces=None, pivot=None):
    """render one part; its pivot a 3D point (the joint it turns about) -> the manifest"""
    draw = [o for o in draw if o is not None]
    stage(draw, hold, faces)
    # (a split part's lines run on into its neighbour's: no taper at their ends, or they thin where the parts meet)
    for name in ("DST_ink", "DST_sketch"):
        ls = bpy.data.linestyles.get(name)
        if ls and "taper" in ls.thickness_modifiers:
            ls.thickness_modifiers["taper"].use = not faces
    x0, x1, y0, y1 = bounds(view, draw, faces)
    sc = bpy.context.scene
    rx, ry = max(2, math.ceil((x1 - x0) * B * SS)), max(2, math.ceil((y1 - y0) * B * SS))
    w, h = rx / (B * SS), ry / (B * SS)
    r, u, _ = basis(view)
    c = ORIGIN + r * (x0 + w / 2) + u * (y0 + h / 2)
    D.camera(target=tuple(c), azimuth=VIEWS[view], elevation=ELEV, size=max(w, h))
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    path = os.path.join(OUT, f"{symbol}__{frame}.png")
    D.render(path)
    pv = proj(view, pivot) if pivot is not None else [(x0 + w / 2) * B, (y0 + h / 2) * B]
    # (the pivot in the picture's px from its top left, at SS)
    ix = (pv[0] / B - x0) * B * SS
    iy = ((y0 + h) - pv[1] / B) * B * SS
    manifest["parts"].append(dict(symbol=symbol, frame=frame, file=os.path.basename(path), size=[rx, ry],
                                  pivot=[ix, iy], view=view))
    print("part", symbol, frame, rx, ry, flush=True)


def ob(name):
    return bpy.data.objects.get(name)


def group(prefix):
    return [o for o in objs() if o.name.startswith(prefix)]


def leg_objs(kind, side):
    s = "LR"[side > 0]
    extra = ("shoulder" if kind == "f" else "thigh") + s
    return group(f"leg_{kind}{s}") + [ob(extra)]


def side_of(view, screen):
    """the creature's side (-1, 1) on the screen's left (screen 'l') or right ('r') in a front or back view"""
    return LEFT[view] if screen == "l" else -LEFT[view]


# --- the parts -------------------------------------------------------------------------------------------------------

def rest_parts(views):
    """the front half's parts (not bent): the body's front, the head, the jaw, the mouth, the front legs"""
    M3.build(bend=0.0)
    setup_lines()
    body, fins = ob("body"), [ob("fin_top")]
    J = M3.J3
    head = [ob("head")] + group("nostril") + group("fang")
    for view in views:
        tag = {"side": "", "down": "f", "up": "b"}[view]
        bsym = {"side": "body", "down": "fbody", "up": "bshoulder"}[view]
        shoot(bsym, "front" if view == "side" else "0", view, [body] + fins, faces={body: {0}, fins[0]: {0}},
              pivot=J["body"])
        if view != "up":
            shoot(tag + "head" if tag else "head", "shut" if view == "side" else "0", view, head, hold=[body],
                  pivot=J["head"] if view == "side" else J["head"])
            shoot(tag + "jaw" if tag else "jaw", "0", view, [ob("jaw")], hold=[body],
                  pivot=J["jaw"] if view == "side" else J["lip"])
            shoot(tag + "mouth" if tag else "mouth", "0", view, [ob("mouth")], hold=[body],
                  pivot=J["jaw"] if view == "side" else J["lip"])
        else:
            shoot("bhead", "0", view, head + [ob("jaw")], hold=[body], pivot=J["head"])
        if view == "side":
            shoot("leg_front", "near", view, leg_objs("f", -1), hold=[body], pivot=J["leg_fL"])
            shoot("leg_front", "far", view, leg_objs("f", 1), pivot=J["leg_fR"])
        else:
            for scr in ("l", "r"):
                sd = side_of(view, scr)
                shoot("fleg" if view == "down" else "bfore", scr, view, leg_objs("f", sd), hold=[body],
                      pivot=J[f"leg_f{'LR'[sd > 0]}"])


def eye_parts(views, quick=False):
    for state in (["open", "closed", "happy"] if quick else list(M3.LIDS)):
        M3.build(bend=0.0, eyes=state)
        setup_lines()
        J = M3.J3
        for view in views:
            if view == "up":
                continue
            if view == "side":
                shoot("eye", state, view, group("eyeL"), hold=[ob("head")], pivot=J["eye_L"])
            else:
                for scr in ("l", "r"):
                    sd = side_of(view, scr)
                    s = "LR"[sd > 0]
                    shoot("feye", f"{state}_{scr}", view, group("eye" + s), hold=[ob("head")], pivot=J["eye_" + s])


def gill_parts(views):
    """one gill drawn straight up the screen, its feathered vane facing us - the rig turns it to each stalk's angle"""
    M3.build(bend=0.0)
    for view in views:
        r, u, f = basis(view)
        for o in group("gillsym"):
            bpy.data.objects.remove(o, do_unlink=True)
        Mt = M3.materials()
        M3.gill("gillsym", Vector((0, 0, 0)), 0.0, 1, Mt["stalk"], Mt["gill"], d=u, nrm=-f, droop=False)
        setup_lines()
        sym = {"side": "gill", "down": "fgill", "up": "bgill"}[view]
        shoot(sym, "near", view, group("gillsym"), pivot=Vector((0, 0, 0)))
        if view == "side":
            shoot(sym, "far", view, group("gillsym"), pivot=Vector((0, 0, 0)))
        for o in group("gillsym"):
            bpy.data.objects.remove(o, do_unlink=True)


def rear_parts(views, bins, tails, stump=False):
    """the back half at each bend: its body, the hind legs; the tail at each curl"""
    sfx = "s" if stump else ""
    for bi, bend in enumerate(bins):
        M3.build(bend=bend, stump=stump)
        setup_lines()
        body, fins = ob("body"), [ob("fin_top")]
        J = M3.J3
        for view in views:
            bsym = {"side": "body", "down": "fhips", "up": "bhips"}[view]
            own = {1, 2} if stump else {1}        # (the stump's healed end is where the tail was)
            shoot(bsym, f"rear{bi}{sfx}" if view == "side" else f"{bi}{sfx}", view, [body] + fins,
                  faces={body: own, fins[0]: own}, pivot=J["body"])
            if stump:
                continue
            manifest["rear"].setdefault(view, {})[str(bi)] = {}
            if view == "side":
                shoot("leg_back", f"near{bi}", view, leg_objs("b", -1), hold=[body], pivot=J["leg_bL"])
                shoot("leg_back", f"far{bi}", view, leg_objs("b", 1), pivot=J["leg_bR"])
                manifest["rear"][view][str(bi)] = dict(leg_bn=proj(view, J["leg_bL"]), leg_bf=proj(view, J["leg_bR"]),
                                                       tail3=proj(view, J["tail3"]))
            else:
                for scr, k in (("l", "leg_bn"), ("r", "leg_bf")):
                    sd = side_of(view, scr)
                    shoot("fhind" if view == "down" else "bhind", f"{scr}{bi}", view, leg_objs("b", sd), hold=[body],
                          pivot=J[f"leg_b{'LR'[sd > 0]}"])
                    manifest["rear"][view][str(bi)][k] = proj(view, J[f"leg_b{'LR'[sd > 0]}"])
        if stump:
            continue
        for ti, t in enumerate(tails):
            M3.build(bend=bend, tail=t * TAIL_BEND)
            setup_lines()
            body = ob("body")
            draw = [body, ob("fin_top"), ob("fin_bot")]
            for view in views:
                tsym = {"side": "tail", "down": "ftail", "up": "btail"}[view]
                shoot(tsym, f"{bi}_{ti}", view, draw, faces={o: {2} for o in draw}, pivot=M3.J3["body"])


def decoy_parts():
    """the dropped tail, wriggling: DECOY_PHASES frames, and as many thrashing (bitten); seen from the side"""
    for tag, amp, hop in (("", 0.55, 0.12), ("h", 0.9, 0.5)):
        for i in range(M3.DECOY_PHASES):
            obs = M3.build_decoy(i / M3.DECOY_PHASES, amp, hop)
            setup_lines()
            shoot("decoy", f"{tag}{i}", "side", obs, pivot=Vector((0, 0, 0)))


def joints(views):
    """the joints in each view (the rig's build px, y up from the ground under the waist)"""
    M3.build(bend=0.0)
    J = M3.J3
    side = {k: proj("side", J[k]) for k in ("body", "head", "jaw", "tail", "tail1", "tail2", "tail3")}
    side["eye"] = proj("side", J["eye_L"])
    side.update(leg_fn=proj("side", J["leg_fL"]), leg_ff=proj("side", J["leg_fR"]),
                leg_bn=proj("side", J["leg_bL"]), leg_bf=proj("side", J["leg_bR"]))
    rest = {}
    for i in range(3):
        side[f"gill_n{i}"] = proj("side", J[f"gill_L{i}"])
        side[f"gill_f{i}"] = proj("side", J[f"gill_R{i}"])
        rest[str(i)] = screen_angle("side", J[f"gilldir_L{i}"], 1)
    manifest["joints"] = side
    manifest["gills"] = rest
    for view in views:
        if view == "side":
            continue
        V = {k: proj(view, J[k]) for k in ("body", "head", "lip", "tail")}
        grest = []
        for scr in ("l", "r"):
            sd = side_of(view, scr)
            s = "LR"[sd > 0]
            if view == "down":
                V[f"eye_{scr}"] = proj(view, J["eye_" + s])
            V["leg_fn" if scr == "l" else "leg_ff"] = proj(view, J["leg_f" + s])
            V["leg_bn" if scr == "l" else "leg_bf"] = proj(view, J["leg_b" + s])
            for i in range(3):
                V[f"gill_{scr}{i}"] = proj(view, J[f"gill_{s}{i}"])
                if scr == "l":
                    grest.append(screen_angle(view, J[f"gilldir_{s}{i}"], 1))
        manifest["views"][view] = dict(J=V, gill_rest=grest)


def screen_angle(view, d, outward):
    """a direction's angle on the screen from straight up, + anticlockwise (toward the screen's left)"""
    r, u, _ = basis(view)
    return math.degrees(math.atan2(-d.dot(r), d.dot(u)))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    views = argv[argv.index("--views") + 1].split(",") if "--views" in argv else list(VIEWS)
    quick = "--quick" in argv
    for o in list(bpy.data.objects):            # (the factory scene's cube and the like)
        if o.type == "MESH" and M3.COLL not in [c.name for c in o.users_collection]:
            bpy.data.objects.remove(o, do_unlink=True)
    if "--decoy" in argv or "--stump" in argv:      # (only the dropped tail, or the stump: redone in the manifest)
        global manifest
        path = os.path.join(OUT, "manifest.json")
        manifest = json.load(open(path))
        if "--decoy" in argv:
            manifest["parts"] = [p for p in manifest["parts"] if p["symbol"] != "decoy"]
            decoy_parts()
        else:
            manifest["parts"] = [p for p in manifest["parts"]
                                 if not (p["symbol"] in ("body", "fhips", "bhips") and p["frame"].endswith("s"))]
            rear_parts(views, manifest["bins"], manifest["tails"], stump=True)
        json.dump(manifest, open(path, "w"), indent=1)
        return
    os.makedirs(OUT, exist_ok=True)
    bins = [0.0, 50.0] if quick else BINS
    tails = [-1.0, 0.0, 1.0] if quick else TAILS
    manifest["bins"], manifest["tails"] = bins, tails
    joints(views)
    rest_parts(views)
    gill_parts(views)
    eye_parts(views, quick)
    rear_parts(views, bins, tails)
    rear_parts(views, bins, tails, stump=True)
    if "side" in views:
        decoy_parts()
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("rendered", len(manifest["parts"]), "parts", flush=True)


if __name__ == "__main__":
    main()
