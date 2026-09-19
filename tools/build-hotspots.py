"""
STANDARD · marker table builder for a photographed spin set
==============================================================================
Converts the hand-authored positions in tools/hotspots-views.json into the
runtime table the 360 screen loads.

    python tools/build-hotspots.py

The authored file is the thing to edit; this only reshapes it into the compact
[x, y, visible] rows the viewer expects and checks it against the markers that
actually exist in index.html, so a renamed or removed hotspot is caught here
rather than silently vanishing from the page.
"""

import json, os, re, sys

try:
    import numpy as np
    from PIL import Image
except ImportError as e:      # only needed for space='bbox'
    np = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

SRC = P("tools", "hotspots-views.json")
OUT = P("assets", "data", "hotspots-360.json")
HTML = P("index.html")


def ring_lerp(rows, n):
    """Spread K authored keyframes evenly around the turn and read off n frames.

    Marker positions move smoothly with azimuth even though the pixels do not,
    so interpolating them is sound where interpolating the IMAGES is not. This
    is what keeps a 48-frame set from needing 384 hand-placed markers.

    Visibility is deliberately conservative: a marker is drawn only where both
    surrounding keyframes agree it is visible, so it disappears for a whole arc
    rather than blinking on and off around the boundary.
    """
    k = len(rows)
    out = []
    for i in range(n):
        t = i * k / float(n)          # position along the keyframe ring
        a = int(t) % k
        b = (a + 1) % k
        f = t - int(t)
        ra, rb = rows[a], rows[b]
        if ra is None or rb is None:
            out.append(None)
            continue
        out.append([ra[0] + (rb[0] - ra[0]) * f,
                    ra[1] + (rb[1] - ra[1]) * f])
    return out


def frame_count():
    """However many frames the packed set actually has."""
    n = 0
    while os.path.exists(P("assets", "img", "spin", "f%03d.webp" % n)):
        n += 1
    return n


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    n = frame_count() or data.get("frames", 0)
    if not n:
        sys.exit("no frames found in assets/img/spin")
    keys_n = data.get("keyframes")

    html = open(HTML, encoding="utf-8").read()
    sec = re.search(r'id="s-view360".*?</section>', html, re.S)
    if not sec:
        sys.exit("#s-view360 not found in index.html")
    markup_keys = re.findall(r'data-hs="([^"]+)"', sec.group(0))

    authored = set(data["pos"])
    missing = [k for k in markup_keys if k not in authored]
    extra = [k for k in authored if k not in markup_keys]
    if missing:
        sys.exit("markers in index.html with no authored positions: %s" % ", ".join(missing))
    if extra:
        print("[hotspots] NOTE: authored but not in the markup, ignored:", ", ".join(extra))

    # Positions authored against the product's own bounds have to be converted
    # to frame fractions, which is what the viewer draws with. Measuring the
    # bounds here is what makes the table survive a re-pack.
    boxes = None
    if data.get("space") == "bbox":
        if np is None:
            sys.exit("space='bbox' needs numpy and Pillow")
        boxes = []
        for i in range(n):
            f = P("assets", "img", "spin", "f%03d.webp" % i)
            if not os.path.exists(f):
                sys.exit("missing frame " + f)
            a = np.asarray(Image.open(f).convert("RGBA").getchannel("A"))
            ys, xs = np.where(a > 24)
            h, w = a.shape
            boxes.append((xs.min() / w, ys.min() / h, (xs.max() + 1) / w, (ys.max() + 1) / h))

    pos = {}
    for k in markup_keys:
        rows = data["pos"][k]
        if keys_n:
            if len(rows) != keys_n:
                sys.exit("marker '%s' has %d keyframes, expected %d" % (k, len(rows), keys_n))
            rows = ring_lerp(rows, n)
        elif len(rows) != n:
            sys.exit("marker '%s' has %d positions, expected %d" % (k, len(rows), n))
        out = []
        for i, r in enumerate(rows):
            if r is None:
                out.append([0.5, 0.5, 0]); continue
            x, y = r[0], r[1]
            if boxes:
                x0, y0, x1, y1 = boxes[i]
                x = x0 + x * (x1 - x0)
                y = y0 + y * (y1 - y0)
            out.append([round(x, 4), round(y, 4), 1])
        pos[k] = out

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"frames": n, "step": 360.0 / n, "keys": markup_keys, "pos": pos},
              open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
    print("[hotspots] wrote assets/data/hotspots-360.json |",
          {k: sum(1 for r in v if r[2]) for k, v in pos.items()})


main()
