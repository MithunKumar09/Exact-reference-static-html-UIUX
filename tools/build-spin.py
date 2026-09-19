"""
STANDARD · one-command spin build
==============================================================================
Turns a folder of product plates into the finished 360 set the page loads.

    python tools/build-spin.py                       # _source-photography
    python tools/build-spin.py --src <folder>

Plates are taken **in filename order** and that order IS the turn order, so
name them turn-00.png, turn-01.png, ... See _source-photography/SHOT-LIST.md.
An optional `top.png` becomes the Top View still and is kept out of the turn.

It runs the three existing steps and then syncs the front end, so no frame
count is ever left stale:

    key-frames.py     cut off the black plate, match size / baseline / exposure
    pack-frames.py    crop, resize, webp, half-size set, strip thumbnails
    build-hotspots.py interpolate the eight authored keyframes to N frames
    (then) config.js + parts/05-view-360.html are re-pointed at the set just
           built, and build-html.py regenerates index.html from parts/

Any frame count works -- 8, 10, 16, 24, 48 -- and the thumbnail strip is mapped
onto the eight named views automatically.
"""

import argparse, glob, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument("--src", default="_source-photography")
ap.add_argument("--work", default=None, help="scratch dir (default: <src>/.work)")
ap.add_argument("--width", type=int, default=1200)
ap.add_argument("--keep-work", action="store_true", dest="keep_work")
A = ap.parse_args()

NAMED = ["front", "front-left", "left", "rear-left",
         "rear", "rear-right", "right", "front-right"]
SKIP = ("top.png", "reference-plate.png")


def run(*cmd):
    print("\n$ " + " ".join(os.path.basename(str(c)) for c in cmd[1:]), flush=True)
    if subprocess.run(cmd, cwd=ROOT).returncode:
        sys.exit("step failed: " + " ".join(str(c) for c in cmd[1:]))


def sync_front_end(n, views):
    """Point config.js and the thumbnail strip at the set just built.

    The frame count necessarily lives in two places -- the runtime needs the
    ring size, the markup needs a target per thumbnail -- and leaving either
    behind after a rebuild breaks the strip silently. So the build owns both.
    Only those values are touched; nothing else in either file moves.

    The markup edit goes into the 360 part, not index.html: index.html is
    generated from parts/ by build-html.py, so writing it here would be undone
    by the next page build. The page is rebuilt straight after instead.
    """
    start = min(n - 1, max(0, int(round(n / 8.0))))      # open on front-left

    cfg = P("assets", "js", "config.js")
    t = open(cfg, encoding="utf-8").read()
    t2 = re.sub(r"(\bframes:\s*)\d+", lambda m: m.group(1) + str(n), t, count=1)
    t2 = re.sub(r"(\bstart:\s*)\d+", lambda m: m.group(1) + str(start), t2, count=1)
    if t2 != t:
        open(cfg, "w", encoding="utf-8").write(t2)
        print("[build] config.js: frames %d, start %d" % (n, start))

    html = P("parts", "05-view-360.html")
    h = open(html, encoding="utf-8").read()
    m = re.search(r'(<div class="thumbstrip v360__thumbs">)(.*?)(\n  </div>)', h, re.S)
    if not m:
        print("[build] WARNING: 360 thumbnail strip not found in "
              "parts/05-view-360.html")
        return
    block = m.group(2)
    for pair in views.split(","):
        name, idx = pair.split(":")
        block = re.sub(r'(data-view="%s") data-frame="[^"]*"' % re.escape(name),
                       lambda mm, i=idx: mm.group(1) + ' data-frame="%s"' % i, block)
    h2 = h[:m.start(2)] + block + h[m.end(2):]
    h2 = re.sub(r'(class="v360__fallback" src="assets/img/spin/)f\d+(\.webp")',
                lambda mm: mm.group(1) + "f%03d" % start + mm.group(2), h2, count=1)
    if h2 != h:
        open(html, "w", encoding="utf-8").write(h2)
        print("[build] parts/05-view-360.html: thumbnail strip + poster re-pointed")

    #  index.html is the concatenation of parts/; regenerate it so the page on
    #  disk matches the set that was just built.
    run(PY, P("tools", "build-html.py"))


def main():
    src = P(A.src)
    if not os.path.isdir(src):
        sys.exit("no such folder: " + src)

    plates = sorted(f for f in glob.glob(os.path.join(src, "*.png"))
                    if os.path.basename(f).lower() not in SKIP)
    if len(plates) < 4:
        sys.exit("found only %d plates in %s -- need at least 4" % (len(plates), src))
    top = os.path.join(src, "top.png")

    n = len(plates)
    print("[build] %d plates -> %d frames" % (n, n))
    if n < 16:
        print("[build] NOTE: under 16 frames the turn will step visibly.")

    work = P(A.work) if A.work else os.path.join(src, ".work")
    keyed, stage = os.path.join(work, "keyed"), os.path.join(work, "stage")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(stage)

    # Key ONLY the turn plates, from a folder holding nothing else. Pointing
    # the keyer at the source folder sweeps top.png and any reference image
    # into the turn as extra frames.
    turn = os.path.join(work, "turn")
    os.makedirs(turn)
    for i, f in enumerate(plates):
        shutil.copy(f, os.path.join(turn, "t%03d.png" % i))
    run(PY, P("tools", "key-frames.py"), "--src", turn, "--out", keyed)

    keys = sorted(glob.glob(os.path.join(keyed, "k*.png")))
    if len(keys) != n:
        print("[build] WARNING: %d plates in, %d keyed out -- a plate keyed to "
              "nothing. Check --thresh against the backdrop." % (n, len(keys)))
    for i, k in enumerate(keys):
        shutil.copy(k, os.path.join(stage, "f%03d.png" % i))

    if os.path.exists(top):
        # Keyed in isolation: an overhead shot has a very different silhouette
        # height, and letting it into the turn's common scale would drag that
        # scale off for every other frame.
        tdir = os.path.join(work, "topsrc")
        os.makedirs(tdir)
        shutil.copy(top, os.path.join(tdir, "top.png"))
        run(PY, P("tools", "key-frames.py"), "--src", tdir,
            "--out", os.path.join(work, "topkey"))
        tk = sorted(glob.glob(os.path.join(work, "topkey", "k*.png")))
        if tk:
            shutil.copy(tk[0], os.path.join(stage, "top.png"))
    else:
        print("[build] NOTE: no top.png supplied -- the Top View thumbnail will "
              "404. Add one (straight down, same lighting) and re-run.")

    m = len(keys)
    views = ",".join("%s:%d" % (v, min(m - 1, int(round(i * m / 8.0))))
                     for i, v in enumerate(NAMED))
    run(PY, P("tools", "pack-frames.py"), "--src", stage, "--frames", str(m),
        "--width", str(A.width), "--views", views)
    run(PY, P("tools", "build-hotspots.py"))
    sync_front_end(m, views)

    if not A.keep_work:
        shutil.rmtree(work, ignore_errors=True)

    print("\n[build] done -> assets/img/spin  (%d frames)" % m)
    print("[build] Check it turns as ONE machine. If decals, grille or tyres")
    print("[build] change between frames the plates are different tractors,")
    print("[build] and no processing fixes that -- see SHOT-LIST.md.")


main()
