"""DST style for Blender renders: Klei's look for Don't Starve (Together) creatures and props, reusable in any project.

    import sys; sys.path.insert(0, r"C:/Users/seann/Projects/dst-mods/tools/blender")
    import importlib, dst_style as D; importlib.reload(D)
    D.setup_scene()                                    # (render settings, the light, the ink outline)
    skin = D.paint("skin", base=(212, 148, 148), spots=(138, 76, 92))
    obj.data.materials.append(skin)
    D.camera(target=(0, 0, 1), azimuth=-90, elevation=35, size=12)
    D.render("out.png")

What makes the look:
- paint(): flat painted colour, not lit 3D shading. The light is quantised (a soft two-tone toon ramp) and mixed
  with a top-to-bottom gradient (a lighter back, a deeper belly: DST's countershading), mottled, with freckles. It
  goes out as emission, so the colours you give are the colours you get (view transform Standard).
- ink(): a heavy, uneven, near-black outline (Freestyle). The silhouette and part borders are drawn thick, interior
  contours thinner. The strokes taper at their ends and wobble (Perlin noise), and a second, offset pass gives the
  sketched double line. Lines are drawn per object, so separate parts (a leg over the body) get their own outline,
  as in Klei's cut-out puppets.
- The palette is muted, dusty and low-saturation, with high value contrast; colours are 0-255 RGB tuples.

Freestyle only shows in final renders (F12 / render()), not in the viewport.
"""
import math

import bpy
from mathutils import Euler, Vector

INK = (22, 14, 16)


def _rgb(c, a=1.0):
    return (*[(v / 255.0) ** 2.2 for v in c], a)          # (sRGB 0-255 -> linear)


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


# --- render settings -------------------------------------------------------------------------------------------------

def setup_scene(scene=None, resolution=(1600, 1000), transparent=True, light_dir=(-0.35, 0.6, 1.0),
                line_px=13.0, line_color=INK, sketch=True):
    """EEVEE, colours as given (Standard view transform), transparent film, one sun from above and slightly toward
    the camera's left (DST's light), and the ink outline"""
    scene = scene or bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    try:
        scene.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    sun(light_dir)
    ink(scene, line_px, line_color, sketch)
    return scene


def sun(direction=(-0.35, 0.6, 1.0), name="DST_Sun", strength=3.0):
    """the light: a sun shining along -direction (direction points from the scene toward the sun)"""
    for o in list(bpy.data.objects):
        if o.type == "LIGHT" and o.name != name and o.data.type in ("POINT", "SUN", "SPOT", "AREA"):
            o.hide_render = True
    ob = bpy.data.objects.get(name)
    if ob is None:
        ld = bpy.data.lights.new(name, "SUN")
        ob = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(ob)
    ob.data.energy = strength
    ob.data.angle = math.radians(8)
    d = Vector(direction).normalized()
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return ob


# --- the outline -----------------------------------------------------------------------------------------------------

def _linestyle(name, px, color, seed, amp, alpha=1.0, along=((0.0, 0.25), (0.12, 1.0), (0.88, 1.0), (1.0, 0.3))):
    ls = bpy.data.linestyles.get(name) or bpy.data.linestyles.new(name)
    ls.color = _rgb(color)[:3]
    ls.alpha = alpha
    ls.thickness = px
    ls.thickness_position = "CENTER"
    ls.caps = "ROUND"
    ls.chaining = "PLAIN"
    ls.use_same_object = True
    ls.use_split_length = False
    for coll in (ls.thickness_modifiers, ls.geometry_modifiers, ls.alpha_modifiers, ls.color_modifiers):
        for m in list(coll):
            coll.remove(m)
    # (thick through the middle of a stroke, tapering to its ends: a brush, not a pen)
    t = ls.thickness_modifiers.new("taper", "ALONG_STROKE")
    t.mapping = "CURVE"
    t.blend = "MULTIPLY"
    t.value_min, t.value_max = 0.0, 1.0
    cm = t.curve
    pts = cm.curves[0].points
    while len(pts) > 2:
        pts.remove(pts[1])
    pts[0].location = along[0]
    pts[-1].location = along[-1]
    for p in along[1:-1]:
        pts.new(*p)
    cm.update()
    # (a brush's weight: heavier across one direction than along it, as a flat brush held at an angle)
    n = ls.thickness_modifiers.new("weight", "CALLIGRAPHY")
    n.blend = "MULTIPLY"
    n.orientation = math.radians(60)
    n.thickness_min, n.thickness_max = 0.55, 1.25
    # (a hand's wobble)
    g = ls.geometry_modifiers.new("sample", "SAMPLING")
    g.sampling = 3.0
    w = ls.geometry_modifiers.new("wobble", "PERLIN_NOISE_1D")
    w.frequency, w.amplitude, w.octaves, w.seed = 0.04, amp * 1.6, 1, seed
    return ls


def ink(scene=None, px=13.0, color=INK, sketch=True, crease_deg=130.0):
    """Freestyle: the silhouette and each part's outline heavy, interior contours lighter; a second, offset, fainter
    pass for the sketched double line"""
    scene = scene or bpy.context.scene
    scene.render.use_freestyle = True
    scene.render.line_thickness_mode = "ABSOLUTE"
    scene.render.line_thickness = 1.0
    vl = scene.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(crease_deg)
    fs.use_smoothness = True
    for l in list(fs.linesets):
        fs.linesets.remove(l)

    def lineset(name, style, contour=False):
        l = fs.linesets.new(name)
        l.select_by_visibility = True
        l.visibility = "VISIBLE"
        l.select_by_edge_types = True
        l.select_silhouette = True
        l.select_border = True
        l.select_external_contour = True
        l.select_contour = contour
        l.select_crease = contour
        l.select_suggestive_contour = False
        l.select_by_face_marks = False
        l.select_by_collection = False
        l.linestyle = style
        return l

    lineset("DST_ink", _linestyle("DST_ink", px, color, 1, 1.5))
    if sketch:
        lineset("DST_sketch", _linestyle("DST_sketch", px * 0.4, color, 7, 3.0, alpha=0.5,
                                         along=((0.0, 0.0), (0.3, 1.0), (0.7, 1.0), (1.0, 0.0))))
    return fs


def _group(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        c.use_fake_user = True             # (not in the scene: kept for Freestyle's line sets to name)
    return c


def _own_lines(obj):
    """take obj out of the main outline (the DST_ink and DST_sketch line sets skip DST_not_main)"""
    fs = bpy.context.scene.view_layers[0].freestyle_settings
    coll = _group("DST_not_main")
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    for name in ("DST_ink", "DST_sketch"):
        l = fs.linesets.get(name)
        if l:
            l.select_by_collection = True
            l.collection = coll
            l.collection_negation = "EXCLUSIVE"


def no_ink(obj):
    """leave an object out of the outline (a glint, an inner detail drawn in paint)"""
    _own_lines(obj)


def fine_ink(obj, px=3.0, color=INK):
    """a finer outline of its own for busy small parts (feathery gills, fur tufts, fringes), so they don't go solid
    black under the heavy line"""
    _own_lines(obj)
    coll = _group("DST_fine")
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    fs = bpy.context.scene.view_layers[0].freestyle_settings
    l = fs.linesets.get("DST_fine")
    if l is None:
        l = fs.linesets.new("DST_fine")
        l.select_by_visibility = True
        l.visibility = "VISIBLE"
        l.select_by_edge_types = True
        l.select_silhouette = l.select_border = l.select_external_contour = True
        l.select_contour = l.select_crease = False
        l.select_by_collection = True
        l.collection = coll
        l.collection_negation = "INCLUSIVE"
    l.linestyle = _linestyle("DST_fine", px, color, 3, 0.6)


# --- the paint -------------------------------------------------------------------------------------------------------

def paint(name, base, light=None, shade=None, top=None, belly=None, spots=None, spot_scale=2.2, spot_size=0.22,
          mottle=0.1, toon=0.45, brush=0.1, highlight=0.55, under=0.35, hatch=0.6, hatch_scale=6.0, glow=False,
          alpha=1.0, coords="OBJECT", ink_tone=None):
    """a DST painted material: flat colour, two tones and a highlight, not lit 3D shading.
    base: the colour in the light; shade: the colour in shadow (default: base toward a dusky purple, as Klei's
    shadows are); light: the highlight on what faces the light and up (default: base lightened); top: a deeper colour
    where it faces straight up (a countershaded back); belly: a paler underside;
    toon: where the light turns to shadow (0-1 of the light); brush: how ragged that edge is, as a brush's (0: clean);
    highlight: how much of the lit side gets the light colour; under: how much deeper the underside goes;
    hatch: hatching strokes in the shadow (0: none), hatch_scale: their density (per unit);
    spots: freckle colour (None: none), spot_scale: how many (per unit), spot_size: how big (0-0.5);
    mottle: a blotchy unevenness; glow: unlit (eyes' glints, fire); alpha < 1: a little see-through (fins)."""
    light = light or _mix(base, (255, 246, 230), 0.25)
    shade = shade or _mix(base, (60, 40, 70), 0.42)
    ink_tone = ink_tone or _mix(shade, INK, 0.45)
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N, L = nt.nodes, nt.links
    pos = [0]

    def node(t, **kw):
        n = N.new(t)
        n.location = (pos[0] * 180 - 1200, 0)
        pos[0] += 1
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def math_(op, a, b=None, clamp=False):
        n = node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    def remap(v, a, b, lo=0.0, hi=1.0):
        n = node("ShaderNodeMapRange", clamp=True)
        n.inputs["From Min"].default_value, n.inputs["From Max"].default_value = a, b
        n.inputs["To Min"].default_value, n.inputs["To Max"].default_value = lo, hi
        L.new(v, n.inputs["Value"])
        return n.outputs["Result"]

    def mix(fac, a, b):
        n = node("ShaderNodeMix", data_type="RGBA")
        for sock, v in (("Factor", fac), ("A", a), ("B", b)):
            if isinstance(v, tuple):
                n.inputs[sock].default_value = _rgb(v)
            elif isinstance(v, (int, float)):
                n.inputs[sock].default_value = v
            else:
                L.new(v, n.inputs[sock])
        return n.outputs["Result"]

    def noise(scale, detail=2.0, vec=None):
        n = node("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        L.new(vec or co, n.inputs["Vector"])
        return n.outputs["Fac"]

    out = node("ShaderNodeOutputMaterial")
    if glow:
        e = node("ShaderNodeEmission")
        e.inputs["Color"].default_value = _rgb(base)
        L.new(e.outputs[0], out.inputs["Surface"])
        return m
    tc = node("ShaderNodeTexCoord")
    co = tc.outputs["Object" if coords == "OBJECT" else "Generated"]

    # (the light, shadows cast included: its brightness, the edge roughened by noise as a brush leaves it)
    dif = node("ShaderNodeBsdfDiffuse")
    s2r = node("ShaderNodeShaderToRGB")
    L.new(dif.outputs[0], s2r.inputs[0])
    bw = node("ShaderNodeRGBToBW")
    L.new(s2r.outputs["Color"], bw.inputs[0])
    raw = bw.outputs[0]
    rough = math_("ADD", raw, math_("MULTIPLY", math_("SUBTRACT", noise(3.0, 2.5), 0.5), brush * 2))
    lit = remap(rough, toon - 0.03, toon + 0.03)                  # (two tones: lit, or in shadow)
    geo = node("ShaderNodeNewGeometry")
    sep = node("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sep.inputs[0])
    nz = sep.outputs["Z"]                                         # (which way it faces: up 1, down -1)

    col = mix(lit, shade, base)
    # (the highlight: on what faces both the light and up, a soft-edged patch)
    if highlight:
        h = remap(math_("ADD", math_("MULTIPLY", raw, 0.6), math_("MULTIPLY", nz, 0.4)), 0.62, 0.7, 0.0, highlight)
        col = mix(math_("MULTIPLY", h, lit), col, light)
    # (countershading: a deeper back where it faces straight up ...)
    if top:
        col = mix(remap(nz, 0.8, 0.97, 0.0, 0.75), col, top)
    # (... a deeper underside, and a paler belly)
    if under:
        col = mix(remap(nz, -0.05, -0.55, 0.0, under), col, shade)
    if belly:
        bcol = mix(lit, _mix(belly, (60, 40, 70), 0.35), belly)
        col = mix(remap(nz, -0.45, -0.62), col, bcol)

    # (mottling: soft blotches a little darker)
    if mottle:
        col = mix(remap(noise(1.6, 3.0), 0.45, 0.7, 0.0, mottle), col, shade)

    # (freckles: voronoi cells, their size varied by noise, clustered)
    if spots:
        vo = node("ShaderNodeTexVoronoi")
        vo.inputs["Scale"].default_value = spot_scale
        vo.inputs["Randomness"].default_value = 1.0
        L.new(co, vo.inputs["Vector"])
        size = remap(noise(0.9), 0.35, 0.65, 0.0, spot_size)
        inside = math_("LESS_THAN", vo.outputs["Distance"], size)
        spc = mix(lit, _mix(spots, (40, 24, 40), 0.35), spots)
        col = mix(math_("MULTIPLY", inside, 0.8), col, spc)

    # (hatching: Klei's diagonal strokes in the shadows, in patches along the shadow's edge, broken)
    if hatch:
        # (laid out on the picture's plane, but fixed to the world - the same strokes on every part rendered on its
        #  own: the world's position turned to the camera's frame, camera() keeps the turn up to date)
        geo2 = node("ShaderNodeNewGeometry")
        rot = node("ShaderNodeVectorRotate", rotation_type="EULER_XYZ", invert=True)
        rot.name = "DST_hatch_rot"
        L.new(geo2.outputs["Position"], rot.inputs["Vector"])
        win = rot.outputs["Vector"]
        wave = node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="DIAGONAL", wave_profile="SIN")
        wave.inputs["Scale"].default_value = hatch_scale
        wave.inputs["Distortion"].default_value = 2.0
        wave.inputs["Detail Scale"].default_value = 3.0
        L.new(win, wave.inputs["Vector"])
        strokes = remap(wave.outputs["Fac"], 0.66, 0.8)
        near_edge = remap(rough, toon - 0.35, toon - 0.02)          # (toward the lit side: the shadow's edge)
        patch = remap(noise(2.2, 1.0), 0.42, 0.55)
        broken = remap(noise(14.0, 1.0), 0.35, 0.5)
        k = math_("MULTIPLY", math_("MULTIPLY", strokes, near_edge), math_("MULTIPLY", patch, broken))
        k = math_("MULTIPLY", math_("MULTIPLY", k, math_("SUBTRACT", 1.0, lit)), hatch)
        col = mix(k, col, ink_tone)

    em = node("ShaderNodeEmission")
    L.new(col, em.inputs["Color"])
    if alpha < 1.0:
        tr = node("ShaderNodeBsdfTransparent")
        mx = node("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = alpha
        L.new(tr.outputs[0], mx.inputs[1])
        L.new(em.outputs[0], mx.inputs[2])
        L.new(mx.outputs[0], out.inputs["Surface"])
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            pass
    else:
        L.new(em.outputs[0], out.inputs["Surface"])
    m.diffuse_color = _rgb(base)
    return m


# --- the camera ------------------------------------------------------------------------------------------------------

def camera(target=(0, 0, 1), azimuth=-90.0, elevation=35.0, size=12.0, name="DST_Cam", distance=40.0,
           light=(-0.55, 0.6, 0.85)):
    """an orthographic camera looking at target from azimuth (degrees about Z, 0 = from +X, -90 = from -Y) and
    elevation (DST's camera pitch is about 30-45 degrees: Klei draws its side views a little from above).
    light: the sun's direction in the camera's frame (x right, y toward the camera, z up) - DST's art is lit the
    same in every view (from above, a little from the left and the front), so the sun turns with the camera"""
    ob = bpy.data.objects.get(name)
    if ob is None:
        cd = bpy.data.cameras.new(name)
        ob = bpy.data.objects.new(name, cd)
        bpy.context.scene.collection.objects.link(ob)
    ob.data.type = "ORTHO"
    ob.data.ortho_scale = size
    ob.data.clip_end = distance * 3
    a, e = math.radians(azimuth), math.radians(elevation)
    t = Vector(target)
    ob.location = t + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * distance
    ob.rotation_euler = (t - ob.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    for m in bpy.data.materials:                 # (the hatching: on the picture's plane)
        if m.node_tree and "DST_hatch_rot" in m.node_tree.nodes:
            m.node_tree.nodes["DST_hatch_rot"].inputs["Rotation"].default_value = ob.rotation_euler
    if light:
        right = Vector((-math.sin(a), math.cos(a), 0.0))
        toward = Vector((math.cos(a), math.sin(a), 0.0))
        sun(tuple(right * light[0] + toward * light[1] + Vector((0, 0, 1)) * light[2]))
    return ob


def render(path, scene=None):
    scene = scene or bpy.context.scene
    scene.render.filepath = path
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    bpy.ops.render.render(write_still=True)
    return path
