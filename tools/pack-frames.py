"""
STANDARD · spin-set packer
==============================================================================
Turns the renderer's PNGs into the webp set the 360 screen actually loads:

    assets/img/spin/f000.webp ... f047.webp    the turntable
    assets/img/spin/top.webp                   the Top View still
    assets/img/spin/thumb-<view>.webp          the 9 strip thumbnails
    assets/data/hotspots-360.json              marker table, crop-corrected

Run (plain CPython, needs Pillow -- no Node, no package.json):

    python tools/pack-frames.py --src <render dir> --json <renderer json>

Why the crop matters
------------------------------------------------------------------------------
Every frame is cropped to ONE box: the union of all 48 alpha bounds. Cropping
each frame to its own bounds would resize the product on every step and make
the spin pulse as you drag. The union box throws away only the margin that no
frame ever uses, so the tractor keeps a rock-steady size and we stop paying for
empty pixels.

The marker coordinates are normalised to the full frame, so they are remapped
through the same crop -- otherwise every hotspot would sit slightly off the
part it names.
"""

import argparse, json, os, sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required:  pip install Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True, help="directory of rendered PNGs")
ap.add_argument("--json", default=None, help="hotspot table from the renderer")
ap.add_argument("--out", default="assets/img/spin")
ap.add_argument("--out-json", default="assets/data/hotspots-360.json", dest="out_json")
ap.add_argument("--frames", type=int, default=48)
ap.add_argument("--views", default=None,
                help="name:frame,... for the thumbnail strip")
ap.add_argument("--quality", type=int, default=82)
ap.add_argument("--width", type=int, default=1100, help="max width of a packed frame")
ap.add_argument("--thumb-width", type=int, default=300, dest="thumb_width")
ap.add_argument("--alpha-floor", type=int, default=16, dest="alpha_floor",
                help="alpha at or below this is cut to fully transparent")
ap.add_argument("--alpha-gamma", type=float, default=1.15, dest="alpha_gamma")
ap.add_argument("--pad", type=int, default=8, help="transparent margin kept around the union box")
A = ap.parse_args()

ap_views = A.views if hasattr(A, "views") else None
# name:frame for the thumbnail strip. Defaults to the 48-frame turntable; a
# 9-view set from supplied photography passes its own mapping.
VIEWS = [(p.split(":")[0], int(p.split(":")[1]))
         for p in (A.views or "front:0,front-left:6,left:12,rear-left:18,"
                              "rear:24,rear-right:30,right:36,front-right:42").split(",")]


def alpha_lut():
    """Shared by the crop measurement and the packer: both must agree on what
    counts as empty, or the crop is measured against a wash the output no
    longer contains."""
    lo = A.alpha_floor
    if lo <= 0:
        return None
    span = 255.0 - lo
    return [0 if v <= lo else min(255, int(255.0 * (((v - lo) / span) ** A.alpha_gamma)))
            for v in range(256)]


LUT = None


def clean_alpha(im):
    if LUT is None:
        return im
    im.putalpha(im.getchannel("A").point(LUT))
    return im


def log(*a):
    print("[pack]", *a, flush=True)


def frame_paths():
    out = []
    for i in range(A.frames):
        p = os.path.join(A.src, "f%03d.png" % i)
        if not os.path.exists(p):
            sys.exit("missing frame: " + p)
        out.append(p)
    return out


def union_box(paths):
    """The tightest box that contains the product in EVERY frame."""
    l = t = 10 ** 9
    r = b = -1
    size = None
    for p in paths:
        im = Image.open(p)
        if size is None:
            size = im.size
        elif im.size != size:
            sys.exit("frames differ in size: %s is %s, expected %s" % (p, im.size, size))
        bbox = clean_alpha(im.convert("RGBA")).getchannel("A").getbbox()
        if not bbox:
            continue
        l, t = min(l, bbox[0]), min(t, bbox[1])
        r, b = max(r, bbox[2]), max(b, bbox[3])
    if r < 0:
        sys.exit("every frame is empty -- did the render fail?")
    W, H = size
    l = max(0, l - A.pad); t = max(0, t - A.pad)
    r = min(W, r + A.pad); b = min(H, b + A.pad)
    return (l, t, r, b), size


def main():
    global LUT
    LUT = alpha_lut()
    paths = frame_paths()
    box, (W, H) = union_box(paths)
    cw, ch = box[2] - box[0], box[3] - box[1]
    scale = min(1.0, A.width / cw)
    tw, th = round(cw * scale), round(ch * scale)
    log("source %dx%d -> crop %dx%d -> packed %dx%d" % (W, H, cw, ch, tw, th))

    out_dir = P(A.out)
    os.makedirs(out_dir, exist_ok=True)

    # Clear frames from any previous build first. Without this a SMALLER set
    # leaves the tail of a larger one behind, and everything downstream (the
    # hotspot table, the viewer's frame count) then believes in frames that
    # are no longer part of the turn.
    import glob as _glob
    stale = (_glob.glob(os.path.join(out_dir, "f[0-9][0-9][0-9].webp")) +
             _glob.glob(os.path.join(out_dir, "half", "f[0-9][0-9][0-9].webp")))
    for f in stale:
        os.remove(f)
    if stale:
        log("cleared %d frame(s) from the previous build" % len(stale))
    total = 0

    def pack(src, dst, width=None):
        im = clean_alpha(Image.open(src).convert("RGBA")).crop(box)
        if width:
            im = im.resize((width, max(1, round(ch * width / cw))), Image.LANCZOS)
        elif scale < 1.0:
            im = im.resize((tw, th), Image.LANCZOS)
        im.save(dst, "WEBP", quality=A.quality, method=6)
        return os.path.getsize(dst)

    for i, p in enumerate(paths):
        total += pack(p, os.path.join(out_dir, "f%03d.webp" % i))
    log("%d frames, %.2f MB, avg %.0f KB"
        % (A.frames, total / 1e6, total / A.frames / 1e3))

    # Half-size set for phones. The viewer also skips every other frame there,
    # so only the even ones are ever requested -- but all of them are written,
    # so smallStep can be retuned in config.js without a re-pack.
    half_dir = os.path.join(out_dir, "half")
    os.makedirs(half_dir, exist_ok=True)
    half_total = 0
    for i, p in enumerate(paths):
        half_total += pack(p, os.path.join(half_dir, "f%03d.webp" % i),
                           width=max(1, A.width // 2))
    log("half set, %.2f MB, avg %.0f KB"
        % (half_total / 1e6, half_total / A.frames / 1e3))

    # the 9 strip thumbnails come straight off the matching frames, so the
    # strip can never drift out of step with what the viewer shows
    for name, idx in VIEWS:
        pack(paths[idx], os.path.join(out_dir, "thumb-%s.webp" % name), width=A.thumb_width)

    top = os.path.join(A.src, "top.png")
    if os.path.exists(top):
        # Top View is framed differently, so it gets its own bounds
        im = clean_alpha(Image.open(top).convert("RGBA"))
        tb = im.getchannel("A").getbbox()
        if tb:
            im = im.crop(tb)
        im.thumbnail((A.width, A.width), Image.LANCZOS)
        im.save(os.path.join(out_dir, "top.webp"), "WEBP", quality=A.quality, method=6)
        im.thumbnail((A.thumb_width, A.thumb_width), Image.LANCZOS)
        im.save(os.path.join(out_dir, "thumb-top.webp"), "WEBP", quality=A.quality, method=6)
        log("top view packed")
    else:
        log("WARN: no top.png -- Top View thumbnail will 404")

    # remap the marker table through the crop
    if A.json and os.path.exists(A.json):
        data = json.load(open(A.json, encoding="utf-8"))
        lx, ty = box[0] / W, box[1] / H
        sx, sy = cw / W, ch / H
        for key, rows in data.get("pos", {}).items():
            for r in rows:
                r[0] = round((r[0] - lx) / sx, 4)
                r[1] = round((r[1] - ty) / sy, 4)
                # a marker cropped out of the packed frame must not be drawn
                if not (0.0 <= r[0] <= 1.0 and 0.0 <= r[1] <= 1.0):
                    r[2] = 0
        data["crop"] = [box[0], box[1], box[2], box[3]]
        dst = P(A.out_json)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        json.dump(data, open(dst, "w", encoding="utf-8"), separators=(",", ":"))
        vis = {k: sum(1 for r in v if r[2]) for k, v in data.get("pos", {}).items()}
        log("hotspots ->", A.out_json, "| frames visible per marker:", vis)
    else:
        log("WARN: no hotspot table given -- markers will not follow the spin")

    log("done ->", A.out)


main()
