"""
STANDARD · studio-plate keyer
==============================================================================
Turns the supplied product shots (tractor on a black plate) into the
transparent, size-matched frames the 360 screen needs.

    python tools/key-frames.py --src "<folder of .png>" --out <work dir>

Three things have to happen, in this order:

1. CUT THE PRODUCT OUT WITHOUT LOSING THE TYRES.
   Measured on the supplied plates: the backdrop is luma 0-1, and large parts
   of the tyres are ALSO exactly 0. 55% of a frame is pure black. There is no
   threshold that separates them, and a border flood-fill leaks straight up
   the tyres into the chassis. The silhouette is therefore rebuilt from where
   signal exists, not carved out of where it does not -- see key_plate().

2. MATCH THE FRAMING.
   Each shot is an independent generation, so the tractor sits at a different
   size and place in every one. Every frame is scaled to ONE COMMON HEIGHT and
   parked on one baseline and one axis. Height, because a rigid body's height
   does not change as it turns -- fitting each frame to a box instead makes
   narrow views bigger than wide ones and the product pulses. See reframe().

3. GRADE TO ONE LOOK.
   Exposure drifts between generations too, so each frame is normalised
   towards a common median brightness. Subtle, but it is the difference
   between a spin and a flicker.
"""

import argparse, os, sys, glob, json

try:
    import numpy as np
    from PIL import Image
    from scipy import ndimage
except ImportError as e:
    sys.exit("needs numpy, scipy and Pillow: pip install numpy scipy Pillow  (%s)" % e)

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--thresh", type=float, default=1.5,
                help="luma above this counts as signal. Must sit just above the "
                     "backdrop (measured at 0-1), NOT at a 'dark' level -- the "
                     "tyres are pure black too.")
ap.add_argument("--close", type=int, default=11,
                help="radius that bridges black gaps inside a tyre, px")
ap.add_argument("--erode", type=int, default=8,
                help="pulled back in after closing so the matte hugs the product")
ap.add_argument("--feather", type=float, default=1.1, help="edge softening, px")
ap.add_argument("--fill", type=float, default=0.96,
                help="hard cap: fraction of canvas width a wide profile may span")
ap.add_argument("--height", type=float, default=0.80,
                help="fraction of canvas height the product is scaled to. This, "
                     "not width, is what keeps the size constant through a turn.")
ap.add_argument("--soften", type=float, default=0.0,
                help="0 = every frame exactly the same height (correct for a "
                     "rigid turntable). >0 keeps some of each plate's own "
                     "height, for plates with inconsistent camera distance.")
ap.add_argument("--canvas", default="1400x1000")
ap.add_argument("--baseline", type=float, default=0.94,
                help="where the wheels sit, as a fraction of canvas height")
ap.add_argument("--grade", action="store_true", default=True)
ap.add_argument("--no-grade", dest="grade", action="store_false")
A = ap.parse_args()

CW, CH = (int(v) for v in A.canvas.lower().split("x"))


def log(*a):
    print("[key]", *a, flush=True)


def key_plate(im):
    """Alpha by silhouette reconstruction, not by thresholding.

    These plates defeat ordinary keying: the backdrop is pure black and so are
    large parts of the tyres -- measured, the tyre interiors sit at luma 0.0,
    exactly the same value as the background, and 55% of the frame is pure 0.
    No threshold can separate them, because there is no signal to separate.

    So the subject is rebuilt from where signal DOES exist:

      1. mark every pixel with any signal at all (luma > `thresh`)
      2. morphologically CLOSE it, bridging the black gaps between the lighter
         tread lugs, rim and sidewall highlights so a tyre becomes one solid
         blob instead of a constellation
      3. keep the largest connected component -- the machine
      4. fill enclosed holes, which recovers the black tyre interiors and the
         shadowed chassis wholesale

    The outer edge of a black tyre against black is genuinely unknowable, so
    step 2's radius decides it. Too small and the tyres come out moth-eaten;
    too large and the silhouette turns into a balloon.
    """
    rgb = np.asarray(im.convert("RGB")).astype(np.int16)
    luma = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2])

    signal = luma > A.thresh

    r = A.close
    if r > 0:
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        disk = (xx * xx + yy * yy) <= r * r
        signal = ndimage.binary_closing(signal, structure=disk)

    lab, n = ndimage.label(signal)
    if n > 1:
        sizes = ndimage.sum(signal, lab, range(1, n + 1))
        signal = lab == (int(np.argmax(sizes)) + 1)
    elif n == 0:
        signal = np.zeros_like(signal)

    subject = ndimage.binary_fill_holes(signal)

    # Undo the dilation half of the closing so the silhouette hugs the product
    # again rather than sitting a radius proud of it.
    if r > 0 and A.erode > 0:
        e = A.erode
        yy, xx = np.mgrid[-e:e + 1, -e:e + 1]
        disk = (xx * xx + yy * yy) <= e * e
        subject = ndimage.binary_erosion(subject, structure=disk)

    alpha = subject.astype(np.float32) * 255.0
    if A.feather > 0:
        alpha = ndimage.gaussian_filter(alpha, A.feather)

    out = np.dstack([np.asarray(im.convert("RGB")), alpha.astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


def content_box(im, floor=12):
    a = np.asarray(im.getchannel("A"))
    ys, xs = np.where(a > floor)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def reframe(im, target_h, cap_w):
    """One scale, one baseline, one axis — for every frame.

    The earlier version fitted each frame into a box. That is wrong for a
    turntable: a front view is narrow and a profile is wide, so fitting to
    width scaled the front view up and the tractor visibly PULSED as it turned
    (measured at ~10% over the shipped set).

    A rigid body's HEIGHT does not change as it rotates about a vertical axis,
    so height is what drives the scale, and every frame gets the same one.
    Vertically the wheels are parked on a fixed baseline; horizontally the
    frame is centred on the alpha CENTROID rather than the bounding box, which
    is far steadier when the silhouette gains a long nose or a wide fender.
    """
    box = content_box(im)
    if not box:
        return None
    crop = im.crop(box)
    w, h = crop.size

    scale = target_h / float(h)
    if cap_w and w * scale > cap_w:          # a very wide profile still has to fit
        scale = cap_w / float(w)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    crop = crop.resize((nw, nh), Image.LANCZOS)

    a = np.asarray(crop.getchannel("A")).astype(np.float32)
    col = a.sum(axis=0)
    cx = float((col * np.arange(nw)).sum() / max(col.sum(), 1.0))

    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    x = int(round(CW * 0.5 - cx))
    y = int(round(CH * A.baseline)) - nh
    canvas.alpha_composite(crop, (max(min(x, CW - nw), 0) if nw <= CW else 0,
                                  max(min(y, CH - nh), 0) if nh <= CH else 0))
    return canvas


def measure_heights(files):
    """The common height every frame is scaled to. Taken as the MEDIAN raw
    silhouette height so one oddly framed plate cannot drag the whole set."""
    hs = []
    for f in files:
        b = content_box(key_plate(Image.open(f)))
        if b:
            hs.append(b[3] - b[1])
    return hs


def grade(im, target):
    """Nudge each frame towards a shared median brightness."""
    arr = np.asarray(im).astype(np.float32)
    a = arr[..., 3]
    m = a > 40
    if not m.any():
        return im
    cur = np.median(arr[..., :3][m])
    if cur <= 1:
        return im
    k = float(np.clip(target / cur, 0.82, 1.22))
    arr[..., :3] = np.clip(arr[..., :3] * k, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def main():
    files = sorted(glob.glob(os.path.join(A.src, "*.png")) +
                   glob.glob(os.path.join(A.src, "*.jpg")) +
                   glob.glob(os.path.join(A.src, "*.webp")))
    if not files:
        sys.exit("no images in " + A.src)
    os.makedirs(A.out, exist_ok=True)
    log("keying", len(files), "images ->", A.out)

    # One pass to learn the common scale, a second to apply it. The keying is
    # repeated, which is cheap next to getting the scale wrong.
    raw = measure_heights(files)
    if not raw:
        sys.exit("nothing keyed — check --thresh against the backdrop")
    med = float(np.median(raw))
    target_h = CH * A.height
    cap_w = CW * A.fill
    log("silhouette heights: min %d max %d median %d -> all scaled to %d px"
        % (min(raw), max(raw), med, target_h))

    staged, meds = [], []
    for f in files:
        im = Image.open(f)
        cut = key_plate(im)
        b = content_box(cut)
        if not b:
            log("SKIP (keyed to nothing):", os.path.basename(f))
            continue
        # Scale each frame by the COMMON target, not by its own extent, or the
        # pulse simply comes back in a different guise.
        fr = reframe(cut, target_h * ((b[3] - b[1]) / med) ** A.soften, cap_w)
        if fr is None:
            continue
        arr = np.asarray(fr)
        m = arr[..., 3] > 40
        meds.append(float(np.median(arr[..., :3][m])) if m.any() else 0.0)
        staged.append((f, fr))

    target = float(np.median([m for m in meds if m > 0])) if meds else 0.0
    manifest = []
    for i, (f, fr) in enumerate(staged):
        if A.grade and target > 0:
            fr = grade(fr, target)
        name = "k%03d.png" % i
        fr.save(os.path.join(A.out, name))
        manifest.append({"i": i, "file": name, "source": os.path.basename(f)})

    json.dump(manifest, open(os.path.join(A.out, "manifest.json"), "w"), indent=1)
    log("wrote", len(manifest), "keyed frames at %dx%d" % (CW, CH))


main()
