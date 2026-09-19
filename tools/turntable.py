"""
STANDARD · 360° turntable renderer
==============================================================================
Renders the product spin set consumed by the 360° screen:

    assets/img/spin/f000.png ... f047.png     48 frames, 7.5 deg apart
    assets/img/spin/top.png                   the Top View still
    assets/data/hotspots-360.json             per-frame marker coordinates

Run (Blender 4.x / 5.x, headless):

    blender -b -P tools/turntable.py -- --model assets/models/tractor-di470.glb
    blender -b -P tools/turntable.py -- --test          # one frame, fast

Conventions that MUST stay in step with the front end
------------------------------------------------------------------------------
* Frame 0 is Front and the azimuth increases exactly as <model-viewer>'s
  camera-orbit theta did, so assets/js/config.js `viewer3d.angles` still
  describes the same nine views:
      front 0 . front-left 6 . left 12 . rear-left 18 . rear 24 .
      rear-right 30 . right 36 . front-right 42
* Elevation is 12 deg above the horizon, i.e. model-viewer's polar angle of
  78deg (measured from +Y), and the lens is 26 deg to match data-fov.
* The marker anchors are read straight out of index.html, so the markup stays
  the single source of truth. Move a data-position there and re-run this.
* Film is transparent: the 360 screen composites the product over its own
  --bg-pad backdrop.
"""

import bpy, bmesh, sys, os, json, math, re, argparse
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

# --------------------------------------------------------------------------- args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--model",  default="assets/models/tractor-di470.glb")
ap.add_argument("--out",    default="assets/img/spin")
ap.add_argument("--json",   default="assets/data/hotspots-360.json")
ap.add_argument("--html",   default="index.html")
ap.add_argument("--frames", type=int, default=48)
ap.add_argument("--res",    type=int, default=1400)
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--fov",    type=float, default=26.0)
ap.add_argument("--polar",  type=float, default=78.0)   # from +Y, matches data-orbit
ap.add_argument("--smooth", action="store_true", default=True,
                help="shade-smooth + weighted normals; hides low-poly faceting")
ap.add_argument("--no-smooth", dest="smooth", action="store_false")
ap.add_argument("--test",   action="store_true", help="render frame 6 only")
ap.add_argument("--project-only", action="store_true", dest="project_only",
                help="rebake the hotspot table without re-rendering a single frame")
ap.add_argument("--occlude-tol", type=float, default=0.35, dest="occlude_tol",
                help="depth gap counted as 'hidden behind the machine', x model size")
ap.add_argument("--device", default="AUTO",
                choices=["AUTO", "CPU", "CUDA", "OPTIX", "HIP", "ONEAPI", "METAL"])
ap.add_argument("--exposure", type=float, default=0.0, help="stops, +/- on the film")
ap.add_argument("--ambient",  type=float, default=0.30, help="studio dome strength")
ap.add_argument("--yaw",      type=float, default=0.0,
                help="degrees about Z to bring the model's nose to 'front'")
ap.add_argument("--margin",   type=float, default=0.82,
                help="<1 fills more of the frame, >1 leaves more air")
ap.add_argument("--repaint",  action="store_true",
                help="shift the body paint to the brand hue, keeping its texture detail")
# #0068FE -> hue 0.598 in Blender's 0-1 space. tokens.css --seed-primary.
ap.add_argument("--brand-hue", type=float, default=0.598, dest="brand_hue")
ap.add_argument("--paint-band", default="0.18,0.48", dest="paint_band",
                help="hue window treated as body paint, e.g. green 0.18,0.48 / red 0.92,0.06")
ap.add_argument("--repaint-mode", default="tint", choices=["tint", "hue"],
                dest="repaint_mode",
                help="tint keeps texture luminance under one flat brand colour; "
                     "hue rotates the original colour and keeps its blotches")
ap.add_argument("--repaint-sat", type=float, default=1.45, dest="repaint_sat",
                help="saturation applied AFTER the tint multiply. This is the knob "
                     "that makes the brand blue vivid -- raising --repaint-lift "
                     "only makes it paler.")
ap.add_argument("--repaint-lift", type=float, default=1.45, dest="repaint_lift",
                help="brightens the greyscale before tinting; multiply darkens")
ap.add_argument("--clean", action="store_true",
                help="desaturate field grime on non-body materials (showroom look)")
ap.add_argument("--clean-sat", type=float, default=0.35, dest="clean_sat")
ap.add_argument("--clean-val", type=float, default=1.30, dest="clean_val")
A = ap.parse_args(argv)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

BRAND_BLUE = (0.0, 0.156, 0.94)      # #0068FE linear-ish, tokens.css --seed-primary


def log(*a):
    print("[turntable]", *a, flush=True)


# ------------------------------------------------------------------- scene reset
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.render.resolution_x = A.res
    sc.render.resolution_y = int(A.res * 0.72)
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.compression = 20

    cy = sc.cycles
    cy.samples = A.samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.01
    cy.use_denoising = True
    cy.max_bounces = 8
    cy.transparent_max_bounces = 8

    # Use whatever accelerator this box has; fall back to CPU silently.
    # CUDA is tried before OPTIX: OptiX kernel compilation fails outright on
    # some driver/GPU combinations, and a failed kernel aborts the render.
    if A.device == "CPU":
        sc.cycles.device = "CPU"
        log("device: CPU (forced)")
        return
    order = ("CUDA", "OPTIX", "HIP", "ONEAPI", "METAL") if A.device == "AUTO" else (A.device,)
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in order:
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            usable = [d for d in prefs.devices if d.type == kind]
            if usable:
                for d in prefs.devices:
                    d.use = (d.type == kind)
                sc.cycles.device = "GPU"
                log("GPU:", kind, "x", len(usable))
                return
    except Exception as e:                                    # noqa: BLE001
        log("GPU probe failed, using CPU:", e)
    sc.cycles.device = "CPU"
    log("device: CPU")


# ------------------------------------------------------------------- model load
def load_model():
    path = P(A.model) if not os.path.isabs(A.model) else A.model
    if not os.path.exists(path):
        raise SystemExit("model not found: " + path)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".blend":
        with bpy.data.libraries.load(path) as (src, dst):
            dst.objects = src.objects
        for o in dst.objects:
            if o:
                bpy.context.collection.objects.link(o)
    else:
        raise SystemExit("unsupported model format: " + ext)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("no mesh in " + path)
    log("meshes:", len(meshes), "tris:", tri_count(meshes))
    return meshes


def tri_count(objs):
    n = 0
    for o in objs:
        me = o.data
        try:
            me.calc_loop_triangles()
            n += len(me.loop_triangles)
        except Exception:                                       # noqa: BLE001
            n += len(me.polygons)
    return n


def world_bbox(objs):
    lo = Vector(( 1e9,  1e9,  1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector((min(lo[i], w[i]) for i in range(3)))
            hi = Vector((max(hi[i], w[i]) for i in range(3)))
    return lo, hi


def ground_and_centre(objs):
    """Sit the product on Z=0 and centre it on the turntable axis, so the
    silhouette never drifts between frames."""
    if A.yaw:
        rot = Matrix.Rotation(math.radians(A.yaw), 4, "Z")
        for o in bpy.context.scene.objects:
            if o.parent is None:
                o.matrix_world = rot @ o.matrix_world
        bpy.context.view_layer.update()

    lo, hi = world_bbox(objs)
    mid = (lo + hi) * 0.5
    shift = Vector((-mid.x, -mid.y, -lo.z))
    for o in bpy.context.scene.objects:
        if o.parent is None:
            o.location += shift
    bpy.context.view_layer.update()
    return world_bbox(objs) + (shift,)


# ------------------------------------------------------------------- materials
def classify(mat):
    """Bucket a material by its existing base colour. The placeholder model has
    no textures, only flat colours, so colour is all we have to go on."""
    col = (0.5, 0.5, 0.5, 1)
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                col = tuple(n.inputs["Base Color"].default_value)
                break
    r, g, b = col[0], col[1], col[2]
    mx, mn = max(r, g, b), min(r, g, b)
    if b > 0.12 and b > r * 1.6 and b > g * 1.25:
        return "paint"
    if mx < 0.10:
        return "rubber"
    if mx - mn < 0.08 and mx > 0.55:
        return "metal"
    if mx - mn < 0.10:
        return "dark"
    return "paint" if b >= max(r, g) else "metal"


def is_textured(mat):
    """A material driven by image maps already carries the detail we are after.
    Overwriting its Base Color would throw away the very thing that makes a
    good model look photoreal, so those are left alone."""
    if not mat or not mat.use_nodes:
        return False
    return any(n.type in ("TEX_IMAGE", "TEX_ENVIRONMENT") for n in mat.node_tree.nodes)


def dress(mat):
    """Give untextured surfaces real PBR behaviour. Photorealism is mostly light
    and material response, not polygon count -- this is where most of the
    'cartoon' goes away on a flat-shaded model.

    Textured materials are skipped entirely unless --repaint is passed."""
    if not mat or not mat.use_nodes:
        return
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        return
    if is_textured(mat) and not A.repaint:
        mat["std_kind"] = "textured"
        return
    kind = classify(mat)
    I = bsdf.inputs

    def put(name, val):
        if name in I:
            I[name].default_value = val

    if kind == "paint":                       # automotive clearcoat
        put("Base Color", (*BRAND_BLUE, 1))
        put("Metallic", 0.35)
        put("Roughness", 0.18)
        put("Coat Weight", 1.0)
        put("Coat Roughness", 0.04)
        put("IOR", 1.5)
    elif kind == "rubber":                    # tyres / hoses
        put("Base Color", (0.022, 0.022, 0.024, 1))
        put("Metallic", 0.0)
        put("Roughness", 0.72)
        put("Specular IOR Level", 0.25)
        put("Sheen Weight", 0.12)
    elif kind == "metal":                     # rims, brightwork
        put("Base Color", (0.82, 0.83, 0.85, 1))
        put("Metallic", 1.0)
        put("Roughness", 0.26)
    else:                                     # grille, castings, shadowed trim
        put("Base Color", (0.055, 0.058, 0.062, 1))
        put("Metallic", 0.55)
        put("Roughness", 0.42)
    mat["std_kind"] = kind


# ------------------------------------------------------------------- repaint
def img_avg_hsv(img):
    """Average hue/sat/val of an image, measured on a 24px copy so this stays
    cheap even for 4K maps."""
    try:
        c = img.copy()
        c.scale(24, 24)
        px = list(c.pixels)
        bpy.data.images.remove(c)
    except Exception:                                          # noqa: BLE001
        return None
    n = len(px) // 4
    if not n:
        return None
    r = g = b = wsum = 0.0
    for i in range(n):
        a = px[i * 4 + 3]
        if a < 0.25:
            continue
        r += px[i * 4] * a
        g += px[i * 4 + 1] * a
        b += px[i * 4 + 2] * a
        wsum += a
    if wsum <= 0:
        return None
    import colorsys
    return colorsys.rgb_to_hsv(r / wsum, g / wsum, b / wsum)


def base_colour_source(bsdf):
    """The image node feeding Base Color, following one hop through the usual
    Mix/Gamma/Bright-Contrast helpers exporters like to insert."""
    inp = bsdf.inputs.get("Base Color")
    if not inp or not inp.is_linked:
        return None, None
    sock = inp.links[0].from_socket
    node = sock.node
    seen = 0
    while node and node.type != "TEX_IMAGE" and seen < 4:
        nxt = None
        for i in node.inputs:
            if i.is_linked and i.type == "RGBA":
                nxt = i.links[0].from_node
                break
        node, seen = nxt, seen + 1
    return sock, (node if node and node.type == "TEX_IMAGE" else None)


def repaint_body(mat, brand_hue, band=(0.18, 0.48), min_sat=0.22):
    """Shift the body paint to the brand hue while keeping every bit of the
    texture's weathering, dirt and panel shading.

    Only materials whose average hue sits inside `band` and that are actually
    saturated get touched, so black tyres, grey castings, glass and the yellow
    rims are all left exactly as the artist made them. Flat-filling the colour
    instead would throw the detail away and put us straight back to 'painted'.
    """
    if not mat or not mat.use_nodes:
        return False
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        return False

    sock, tex = base_colour_source(bsdf)

    if sock is None:                       # flat colour, no texture
        col = bsdf.inputs["Base Color"].default_value
        import colorsys
        h, s, v = colorsys.rgb_to_hsv(col[0], col[1], col[2])
        if not (band[0] <= h <= band[1] and s >= min_sat):
            return False
        r, g, b = colorsys.hsv_to_rgb(brand_hue, min(1.0, s * 1.25), v)
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        mat["std_repaint"] = "flat"
        return True

    if tex is None or not tex.image:
        return False
    hsv = img_avg_hsv(tex.image)
    if not hsv:
        return False
    h, s, _ = hsv
    if not (band[0] <= h <= band[1] and s >= min_sat):
        return False

    if A.repaint_mode == "hue":
        # Rotate the hue. Keeps every bit of the original colour variation --
        # including the weathering blotches, which read as patchy paint.
        hs = nt.nodes.new("ShaderNodeHueSaturation")
        hs.location = (bsdf.location.x - 260, bsdf.location.y + 120)
        hs.inputs["Hue"].default_value = (0.5 + (brand_hue - h)) % 1.0
        hs.inputs["Saturation"].default_value = 1.35
        hs.inputs["Value"].default_value = 1.0
        nt.links.new(sock, hs.inputs["Color"])
        nt.links.new(hs.outputs["Color"], bsdf.inputs["Base Color"])
        mat["std_repaint"] = "hue %.3f -> %.3f" % (h, brand_hue)
        return True

    # tint (default): throw the texture's colour away but keep its luminance,
    # then multiply a single flat brand blue through it. Panel shading, dirt
    # shadows and edge wear all survive as light and shade, while the colour
    # comes out one consistent brand blue instead of mottled paint.
    grey = nt.nodes.new("ShaderNodeHueSaturation")
    grey.location = (bsdf.location.x - 480, bsdf.location.y + 120)
    grey.inputs["Saturation"].default_value = 0.0
    grey.inputs["Value"].default_value = A.repaint_lift

    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.location = (bsdf.location.x - 260, bsdf.location.y + 120)
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 1.0

    import colorsys
    r, g, b = colorsys.hsv_to_rgb(brand_hue, 1.0, 1.0)
    mix.inputs["Color2"].default_value = (r, g, b, 1)

    nt.links.new(sock, grey.inputs["Color"])
    nt.links.new(grey.outputs["Color"], mix.inputs["Color1"])

    # A multiply carries the greyscale's LIGHTNESS through, which pulls the
    # result toward pastel — brightening the greyscale makes it paler, not more
    # vivid. Saturation has to be put back explicitly, after the multiply.
    sat = nt.nodes.new("ShaderNodeHueSaturation")
    sat.location = (bsdf.location.x - 130, bsdf.location.y + 120)
    sat.inputs["Saturation"].default_value = A.repaint_sat
    nt.links.new(mix.outputs["Color"], sat.inputs["Color"])
    nt.links.new(sat.outputs["Color"], bsdf.inputs["Base Color"])
    mat["std_repaint"] = "tint %.3f sat %.2f" % (brand_hue, A.repaint_sat)
    return True


def clean_material(mat, sat, val):
    """Pull the field grime out of a used-equipment texture.

    Stock models are usually weathered, because that is what sells on an asset
    store. The reference is showroom stock, so the mud tint is desaturated and
    the whole map lifted. Body materials are skipped: they already carry the
    brand repaint and must not be washed out by a second pass.
    """
    if not mat or not mat.use_nodes or mat.get("std_repaint"):
        return False
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        return False
    sock, tex = base_colour_source(bsdf)
    if sock is None:
        return False
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.location = (bsdf.location.x - 260, bsdf.location.y - 160)
    hs.inputs["Saturation"].default_value = sat
    hs.inputs["Value"].default_value = val
    nt.links.new(sock, hs.inputs["Color"])
    nt.links.new(hs.outputs["Color"], bsdf.inputs["Base Color"])
    mat["std_clean"] = 1
    return True


def smooth(objs):
    """Faceted low-poly silhouettes read as 'cartoon' more than anything else.
    Auto-smooth keeps real creases sharp while killing the shading facets."""
    for o in objs:
        me = o.data
        for p in me.polygons:
            p.use_smooth = True
        has = {m.type for m in o.modifiers}
        if "WEIGHTED_NORMAL" not in has:
            wn = o.modifiers.new("std_wn", "WEIGHTED_NORMAL")
            wn.keep_sharp = True
        if "BEVEL" not in has:
            bv = o.modifiers.new("std_bevel", "BEVEL")
            bv.width = 0.012
            bv.segments = 2
            bv.limit_method = "ANGLE"
            bv.angle_limit = math.radians(40)
            bv.harden_normals = True


# ------------------------------------------------------------------- lighting
def studio(size):
    """Three-softbox product studio over a neutral dome, plus a shadow-only
    floor so the product sits on the turntable instead of floating.

    The lights orbit WITH the camera, so every frame is lit identically. A
    fixed rig would swing the key across the body as the turntable spun and
    make the sequence strobe when dragged.

    Power is given in watts at a reference distance, then scaled by size^2:
    illuminance falls off with distance^2 and the rig is placed in multiples
    of the product's size, so this keeps exposure constant whatever units the
    model happens to be authored in.
    """
    sc = bpy.context.scene
    sc.view_settings.view_transform = "AgX"     # filmic highlight rolloff
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = A.exposure

    w = bpy.data.worlds.new("std")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.42, 0.47, 0.55, 1)   # cool studio dome
    bg.inputs["Strength"].default_value = A.ambient
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs["Surface"])

    rig = bpy.data.objects.new("rig", None)      # spun with the camera
    bpy.context.collection.objects.link(rig)

    tgt = bpy.data.objects.new("aim", None)
    tgt.location = (0, 0, size * 0.42)
    bpy.context.collection.objects.link(tgt)

    def area(name, loc, watts, dim):
        d = bpy.data.lights.new(name, "AREA")
        d.energy = watts * size * size
        d.shape = "RECTANGLE"
        d.size = dim * size
        d.size_y = dim * size * 0.62
        o = bpy.data.objects.new(name, d)
        o.location = (loc[0] * size, loc[1] * size, loc[2] * size)
        bpy.context.collection.objects.link(o)
        o.parent = rig
        c = o.constraints.new("TRACK_TO")
        c.track_axis = "TRACK_NEGATIVE_Z"
        c.up_axis = "UP_Y"
        c.target = tgt
        return o

    area("key",  ( 1.35, -1.55,  1.55),  55, 2.4)   # front-right, high
    area("fill", (-1.85, -1.05,  0.80),  16, 3.0)   # broad, soft, opposite
    area("rim",  (-0.70,  1.95,  1.35),  34, 1.8)   # kicker, separates the body

    bpy.ops.mesh.primitive_plane_add(size=size * 14, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "shadow_floor"
    floor.is_shadow_catcher = True
    return rig


# ------------------------------------------------------------------- camera
def camera(radius, height_aim):
    d = bpy.data.cameras.new("cam")
    d.sensor_fit = "HORIZONTAL"
    d.sensor_width = 36.0
    d.angle = math.radians(A.fov)
    cam = bpy.data.objects.new("cam", d)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    aim = bpy.data.objects.new("cam_aim", None)
    aim.location = (0, 0, height_aim)
    bpy.context.collection.objects.link(aim)
    c = cam.constraints.new("TRACK_TO")
    c.target = aim
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return cam, radius


def place(cam, radius, theta_deg, rig=None):
    """model-viewer's orbit, in Blender's Z-up world.

    theta is measured about the up axis starting at the camera on +Y_blender
    (which is the glTF +Z the model calls 'front'), increasing the same way
    model-viewer's camera-orbit theta does.  polar is from the up axis, so
    78deg puts the lens 12deg above the horizon.
    """
    phi = math.radians(A.polar)
    th = math.radians(theta_deg)
    r = radius
    horiz = r * math.sin(phi)
    cam.location = (horiz * math.sin(th), -horiz * math.cos(th), r * math.cos(phi))
    if rig is not None:
        rig.rotation_euler = (0.0, 0.0, th)   # lighting rides with the camera
    bpy.context.view_layer.update()


# ------------------------------------------------------------------- hotspots
def read_anchors(html_path, lo, hi):
    """Pull the marker anchors out of the 360 section of index.html so the
    markup stays authoritative.

    data-position is a FRACTION of the product's bounding box, not a distance:

        x  0 = left      1 = right
        y  0 = front     1 = rear      (the camera starts in front, at -Y)
        z  0 = ground    1 = roofline

    Absolute coordinates would be tied to whatever units one particular mesh
    happened to be authored in, so swapping the model would fling every marker
    into mid-air. Fractions survive the swap.
    """
    src = open(html_path, encoding="utf-8").read()
    sec = re.search(r'id="s-view360".*?</section>', src, re.S)
    if not sec:
        log("WARN: #s-view360 not found, no hotspots baked")
        return []
    span = hi - lo
    out = []
    for m in re.finditer(r'data-hs="([^"]+)"[^>]*?data-position="([^"]+)"', sec.group(0), re.S):
        key = m.group(1)
        try:
            fx, fy, fz = (float(v) for v in m.group(2).split())
        except ValueError:
            continue
        if not all(-0.05 <= f <= 1.05 for f in (fx, fy, fz)):
            log("WARN: anchor '%s' is outside 0..1 -- data-position is a bbox "
                "fraction, not a distance" % key)
        out.append((key, Vector((lo.x + span.x * fx,
                                 lo.y + span.y * fy,
                                 lo.z + span.z * fz))))
    log("anchors:", ", ".join(k for k, _ in out) or "none")
    return out


def project(cam, anchors, xform, depsgraph, size):
    """Normalised image-space x/y plus a visibility flag per anchor.

    Visibility is judged by DEPTH GAP, not by "was anything hit". An anchor is
    a point in the middle of the part it names, so it is nearly always a little
    way inside the bodywork -- a naive hit test hides every one of them. (That
    is exactly what happened to Operator Station: its anchor sits inside the
    cab, so the roof was always hit first and the marker never appeared.)

    So: measure how far in FRONT of the anchor the ray hit. A near-surface hit
    is the part's own skin and the marker stays; a hit a long way in front means
    the whole machine is between us and the part, and it is hidden.
    """
    sc = bpy.context.scene
    row = {}
    origin = cam.matrix_world.translation
    tol = A.occlude_tol * size
    for key, p in anchors:
        w = xform @ p
        co = world_to_camera_view(sc, cam, w)
        vis = 1
        if not (0.0 <= co.x <= 1.0 and 0.0 <= co.y <= 1.0) or co.z <= 0:
            vis = 0                       # off frame or behind the lens
        else:
            d = (w - origin)
            dist = d.length
            hit, loc, *_ = sc.ray_cast(depsgraph, origin, d.normalized(),
                                       distance=dist * 0.995)
            if hit and (dist - (loc - origin).length) > tol:
                vis = 0                   # the far side of the machine
        # Blender's Y is bottom-up; CSS top is top-down
        row[key] = [round(co.x, 4), round(1.0 - co.y, 4), vis]
    return row


# ------------------------------------------------------------------- render
def shoot(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    reset()
    meshes = load_model()
    lo, hi, _shift = ground_and_centre(meshes)
    dims = hi - lo
    size = max(dims.x, dims.y, dims.z)
    log("bbox %.2f x %.2f x %.2f" % (dims.x, dims.y, dims.z))

    for m in bpy.data.materials:
        dress(m)

    if A.repaint:
        lo_h, hi_h = (float(v) for v in A.paint_band.split(","))
        done = [m.name for m in bpy.data.materials
                if repaint_body(m, A.brand_hue, (lo_h, hi_h))]
        log("repainted:", ", ".join(done) if done else "nothing matched the paint band")

    if A.clean:
        n = sum(1 for m in bpy.data.materials
                if clean_material(m, A.clean_sat, A.clean_val))
        log("degrimed %d material(s)" % n)

    # Bevel + weighted normals rescue a faceted low-poly silhouette, but on a
    # dense mesh they cost minutes per frame and buy nothing, so they are only
    # worth it below the threshold.
    tris = tri_count(meshes)
    if A.smooth and tris < 60000:
        smooth(meshes)
        log("smoothing applied (%d tris)" % tris)
    else:
        log("smoothing skipped (%d tris)" % tris)

    rig = studio(size)
    # Frame from the bounding sphere against the TIGHTER of the horizontal and
    # vertical field angles, so the product is never cropped and never lost in
    # the distance regardless of how the model is proportioned.
    sc = bpy.context.scene
    hfov = math.radians(A.fov)
    vfov = 2.0 * math.atan(math.tan(hfov / 2.0) * sc.render.resolution_y / sc.render.resolution_x)
    sphere = (hi - lo).length / 2.0
    radius = sphere / math.sin(min(hfov, vfov) / 2.0) * A.margin
    cam, radius = camera(radius, lo.z + dims.z * 0.46)
    log("radius %.2f  sphere %.2f" % (radius, sphere))

    # The anchors are authored against the model's own origin, so they have to
    # follow the same recentring that put it on the turntable.
    # Anchors are bbox fractions resolved against the PLACED bounding box, so
    # they are already in world space -- no further correction needed.
    anchors_raw = read_anchors(P(A.html), lo, hi)
    xform = Matrix.Identity(4)

    out_dir = P(A.out)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(P(A.json)), exist_ok=True)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    step = 360.0 / A.frames
    table = {k: [] for k, _ in anchors_raw}

    idx = [6] if A.test else range(A.frames)
    for i in idx:
        place(cam, radius, i * step, rig)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        if anchors_raw:
            row = project(cam, anchors_raw, xform, depsgraph, sphere * 2.0)
            for k, v in row.items():
                while len(table[k]) < i:
                    table[k].append([0.5, 0.5, 0])
                table[k].append(v)
        if not A.project_only:
            shoot(os.path.join(out_dir, "f%03d" % i))
        log("frame %02d / %d" % (i, A.frames))

    if not A.test:
        if not A.project_only:
            # Top View is not on the turntable: straight down, matching angles.top
            saved = A.polar
            A.polar = 6.0
            place(cam, radius * 1.02, 0.0, rig)
            shoot(os.path.join(out_dir, "top"))
            A.polar = saved

        with open(P(A.json), "w", encoding="utf-8") as f:
            json.dump({"frames": A.frames,
                       "step": step,
                       "keys": [k for k, _ in anchors_raw],
                       "pos": table}, f, separators=(",", ":"))
        log("wrote", A.json)

    log("done ->", out_dir)


main()
