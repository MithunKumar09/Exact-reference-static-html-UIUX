#!/usr/bin/env python3
"""
tools/build-menu-art.py  —  supplied menu photography  ->  shipped assets

ONE COMMAND:  python tools/build-menu-art.py

Reads the client's menu plates from  all the menu images/  (unshipped, like
_source-photography/) and writes every derived asset the page uses:

  product/engine · operator · hydraulics · showcase · cutaway · schematic
      the four photographed screens and the two diagram canvases
  part/bp-*            the four blueprint views and three detail views,
                       cropped out of the Engineering Drawing sheet
  part/part-*          component close-ups, cropped out of the exploded plate
  product/<view>       the eight named product views + thumbnails, taken from
                       the 360 spin set so every screen shows the same tractor
                       as the turntable
  scene/*              the tractor-in-field composites: the real cut-outs
                       dropped onto the generated backdrops

WHY THE CLEANING STEP EXISTS
Four of the supplied plates carry callout cards baked into the pixels, and the
lettering in them is generated rather than typeset — it does not spell the
parts it points at. The page draws its own hotspots over the same positions
with the real copy, so the baked ones are painted out first. `exemplar_fill`
replaces each one with the best-matching block from the same horizontal band
of the photograph, or of its mirror, which is what makes a symmetric rear view
fill convincingly. Whatever it leaves behind ends up underneath the live
marker that replaced it.

The schematic is the exception: its callouts sit on flat, pale background
where a diffusion inpaint is cleaner than a block copy, and the machine is not
symmetric, so mirroring would clone the grille.

Requires: opencv-python, numpy, pillow.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'all the menu images')
IMG = os.path.join(ROOT, 'assets', 'img')
K3 = np.ones((3, 3), np.uint8)


# ---------------------------------------------------------------- inpainting
def _valid_positions(hole, sy0, sy1, P):
    """True where a PxP donor window rooted at (y, x) touches no hole pixel."""
    band = hole[sy0:sy1, :].astype(np.float32)
    integ = cv2.integral(band)
    h, w = band.shape
    oh, ow = h - P + 1, w - P + 1
    if oh <= 0 or ow <= 0:
        return None
    return (integ[P:P + oh, P:P + ow] - integ[0:oh, P:P + ow]
            - integ[P:P + oh, 0:ow] + integ[0:oh, 0:ow]) < 0.5


def exemplar_fill(img, mask, P=19, band=120, mirror=True, max_iter=4000):
    """Criminisi-style onion peel — see the module docstring."""
    H, W = img.shape[:2]
    out = img.astype(np.float32).copy()
    hole = mask > 0
    r = P // 2
    mir = cv2.flip(img, 1).astype(np.float32)
    mir_hole = cv2.flip(hole.astype(np.uint8), 1) > 0

    for _ in range(max_iter):
        if not hole.any():
            break
        known = (~hole).astype(np.uint8)
        bnd = hole & (cv2.dilate(known, K3) > 0)
        if not bnd.any():
            break
        cnt = cv2.boxFilter(known.astype(np.float32), -1, (P, P),
                            normalize=False, borderType=cv2.BORDER_CONSTANT)
        cnt[~bnd] = -1.0
        y, x = np.unravel_index(int(np.argmax(cnt)), cnt.shape)
        y = int(np.clip(y, r, H - r - 1))
        x = int(np.clip(x, r, W - r - 1))
        ty0, tx0 = y - r, x - r
        templ = out[ty0:ty0 + P, tx0:tx0 + P]
        tmask = known[ty0:ty0 + P, tx0:tx0 + P].astype(np.float32)
        if tmask.sum() < 4:
            hole[ty0:ty0 + P, tx0:tx0 + P] = False
            continue
        tmask3 = cv2.merge([tmask] * 3)

        best = None
        for src, shole, flip in ((out, hole, False), (mir, mir_hole, True)):
            if flip and not mirror:
                continue
            base = (H - ty0 - P) if flip else ty0
            sy0, sy1 = max(0, base - band), min(H, base + P + band)
            if sy1 - sy0 < P:
                continue
            res = cv2.matchTemplate(src[sy0:sy1], templ, cv2.TM_SQDIFF, mask=tmask3)
            ok = _valid_positions(shole, sy0, sy1, P)
            if ok is None:
                continue
            res = np.where(ok, res, np.inf)
            if not flip:
                y0l = ty0 - sy0
                res[max(0, y0l - r):y0l + r + 1, max(0, tx0 - r):tx0 + r + 1] = np.inf
            if not np.isfinite(res).any():
                continue
            i = int(np.nanargmin(res))
            sy, sx = np.unravel_index(i, res.shape)
            if best is None or float(res[sy, sx]) < best[0]:
                best = (float(res[sy, sx]), src, sy0 + sy, sx)
        if best is None:
            hole[ty0:ty0 + P, tx0:tx0 + P] = False
            continue
        _, src, sy, sx = best
        donor = src[sy:sy + P, sx:sx + P]
        hp = hole[ty0:ty0 + P, tx0:tx0 + P]
        out[ty0:ty0 + P, tx0:tx0 + P][hp] = donor[hp]
        hole[ty0:ty0 + P, tx0:tx0 + P] = False
        mir_hole = cv2.flip(hole.astype(np.uint8), 1) > 0
        mir = cv2.flip(out, 1)

    res = np.clip(out, 0, 255).astype(np.uint8)
    soft = cv2.bilateralFilter(res, 7, 28, 7)
    m = np.clip(cv2.GaussianBlur((mask > 0).astype(np.float32), (0, 0), 1.6), 0, 1)[:, :, None]
    return np.clip(res * (1 - m * .55) + soft * (m * .55), 0, 255).astype(np.uint8)


# ------------------------------------------------- where the baked cards are
# rect = (x0, y0, x1, y1)   puck = (cx, cy, r)   measured on the 1248x832
# plates as supplied; re-measure if the plates are ever regenerated.
CALLOUTS = {
    'hydraulics': dict(
        rects=[(455, 94, 634, 176), (808, 150, 1002, 228), (319, 303, 498, 382),
               (826, 297, 1006, 380), (691, 483, 924, 565), (239, 598, 441, 662)],
        pucks=[(636, 128, 24), (805, 187, 24), (497, 341, 24), (820, 338, 24),
               (685, 506, 24), (450, 633, 24)],
        mirror=True),
    'Operator station': dict(
        rects=[(870, 126, 996, 194), (405, 197, 540, 262), (757, 277, 921, 342),
               (290, 291, 404, 353), (860, 359, 1004, 423), (900, 462, 1052, 527),
               (290, 470, 416, 533), (672, 524, 824, 588)],
        pucks=[(857, 156, 24), (558, 231, 24), (738, 309, 24), (413, 330, 24),
               (849, 384, 24), (890, 484, 24), (432, 504, 24), (658, 551, 24)],
        mirror=True),
    'Exploded View': dict(
        rects=[],
        pucks=[(236, 240, 22), (381, 183, 22), (530, 190, 22), (514, 300, 22),
               (685, 345, 22), (95, 383, 22), (378, 395, 22), (520, 465, 22),
               (735, 440, 22), (852, 398, 22), (810, 113, 22), (1054, 210, 22),
               (1101, 318, 22), (816, 549, 22), (523, 571, 22), (237, 682, 22),
               (662, 704, 22), (540, 201, 20), (684, 331, 20), (237, 215, 20),
               (494, 291, 18)],
        mirror=False),
}
# flat, pale surroundings and no symmetry — diffusion beats a block copy here
SCHEMATIC_RECTS = [(190, 122, 286, 160), (368, 123, 460, 161), (526, 143, 644, 181),
                   (820, 109, 959, 149), (688, 261, 832, 300), (1010, 241, 1162, 305),
                   (112, 279, 198, 318), (56, 364, 205, 403), (418, 564, 498, 603),
                   (540, 555, 676, 595), (312, 609, 418, 649), (739, 603, 839, 642)]

_clean_cache = {}


def plate(name):
    """The supplied plate, as-is."""
    img = cv2.imread(os.path.join(SRC, name + '.png'))
    if img is None:
        sys.exit('missing plate "%s.png" — put the supplied menu images in %r'
                 % (name, os.path.relpath(SRC, ROOT)))
    return img


def clean(name):
    """The supplied plate with its baked-in callouts painted out."""
    if name in _clean_cache:
        return _clean_cache[name]
    img = plate(name)
    if name == 'Schematic Diagram':
        m = np.zeros(img.shape[:2], np.uint8)
        for (x0, y0, x1, y1) in SCHEMATIC_RECTS:
            cv2.rectangle(m, (x0 - 6, y0 - 6), (x1 + 6, y1 + 6), 255, -1)
        m = cv2.dilate(m, np.ones((9, 9), np.uint8))
        out = cv2.addWeighted(cv2.inpaint(img, m, 14, cv2.INPAINT_TELEA), .5,
                              cv2.inpaint(img, m, 14, cv2.INPAINT_NS), .5, 0)
    else:
        spec = CALLOUTS[name]
        m = np.zeros(img.shape[:2], np.uint8)
        for (x0, y0, x1, y1) in spec['rects']:
            cv2.rectangle(m, (x0, y0), (x1, y1), 255, -1)
        for (cx, cy, r) in spec['pucks']:
            cv2.circle(m, (cx, cy), r, 255, -1)
        out = exemplar_fill(img, cv2.dilate(m, np.ones((7, 7), np.uint8)),
                            mirror=spec['mirror'])
    _clean_cache[name] = out
    return out


# ------------------------------------------------------------------- helpers
def _say(rel, size):
    print('  %-40s %s' % (rel, size))


def save_bgr(bgr, rel, maxw=1280, q=86, thumb=None):
    im = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    im.save(os.path.join(IMG, rel), 'WEBP', quality=q, method=6)
    _say(rel, im.size)
    if thumb:
        t = im.copy()
        t.thumbnail((360, 360), Image.LANCZOS)
        t.save(os.path.join(IMG, thumb), 'WEBP', quality=84, method=6)


def line_art(img, box, rel, scale=2.2, write=True):
    """Crop a blueprint view and lift it off its paper into an alpha channel."""
    x0, y0, x1, y1 = box
    c = cv2.resize(img[y0:y1, x0:x1], None, fx=scale, fy=scale,
                   interpolation=cv2.INTER_CUBIC)
    c = np.clip(cv2.addWeighted(c, 1.55, cv2.GaussianBlur(c, (0, 0), 1.1), -.55, 0),
                0, 255).astype(np.float32)
    a = np.clip((255.0 - c.min(axis=2)) * 1.25, 0, 255)
    a[a < 14] = 0
    rgba = np.dstack([cv2.cvtColor(c.astype(np.uint8), cv2.COLOR_BGR2RGB).astype(np.float32), a])
    out = Image.fromarray(rgba.astype(np.uint8), 'RGBA')
    if write:
        out.save(os.path.join(IMG, rel), 'WEBP', quality=92, method=6)
        _say(rel, out.size)
    return out


def part_cut(src, box, rel, scale=2):
    """Crop a component off the exploded plate; its pale paper becomes alpha."""
    c = src.crop(box)
    c = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
    a = np.asarray(c).astype(np.float32)
    alpha = np.clip((250.0 - a.min(axis=2)) * 6.0, 0, 255)
    Image.fromarray(np.dstack([a, alpha]).astype(np.uint8), 'RGBA') \
         .save(os.path.join(IMG, rel), 'WEBP', quality=88, method=6)
    _say(rel, c.size)


def scene(bg_rel, plate_rel, out_rel, scale=.72, cx=.50, base=.94, thumb=None):
    bg = Image.open(os.path.join(IMG, bg_rel)).convert('RGB')
    W, H = bg.size
    pl = Image.open(os.path.join(IMG, plate_rel)).convert('RGBA')
    bb = pl.getbbox()
    if bb:
        pl = pl.crop(bb)
    th = int(H * scale)
    tw = max(1, round(pl.width * th / pl.height))
    if tw > W * .94:
        tw = int(W * .94)
        th = round(pl.height * tw / pl.width)
    pl = pl.resize((tw, th), Image.LANCZOS)
    x, y = int(W * cx - tw / 2), int(H * base - th)
    # contact shadow, cast from the plate's own silhouette
    sh = Image.new('L', (W, H), 0)
    foot = pl.split()[3].point(lambda v: 170 if v > 40 else 0) \
             .crop((0, int(th * .80), tw, th)) \
             .resize((int(tw * 1.02), max(6, int(th * .10))))
    sh.paste(foot, (int(x - tw * .01), int(y + th - foot.height * .45)))
    sh = sh.filter(ImageFilter.GaussianBlur(max(3, int(H * .018))))
    out = bg.copy()
    out.paste(Image.new('RGB', (W, H), (26, 34, 26)), (0, 0), sh)
    out.paste(pl, (x, y), pl)
    out.save(os.path.join(IMG, out_rel), 'WEBP', quality=86, method=6)
    _say(out_rel, out.size)
    if thumb:
        t = out.copy()
        t.thumbnail((360, 360), Image.LANCZOS)
        t.save(os.path.join(IMG, thumb), 'WEBP', quality=84, method=6)


# ---------------------------------------------------------------------- main
# frame order IS the turn order — the same mapping the 360 thumbnails use
SPIN_VIEWS = (('front', 'f000'), ('front-left', 'f001'), ('left', 'f002'),
              ('rear-left', 'f004'), ('rear', 'f005'), ('rear-right', 'f006'),
              ('right', 'f008'), ('front-right', 'f009'))

BLUEPRINTS = (((104, 96, 300, 322), 'part/bp-front.webp'),
              ((392, 96, 842, 322), 'part/bp-side.webp'),
              ((952, 96, 1200, 322), 'part/bp-rear.webp'),
              ((58, 462, 366, 642), 'part/bp-top.webp'),
              ((722, 478, 842, 614), 'part/bp-axle.webp'),
              ((866, 480, 1026, 612), 'part/bp-hitch.webp'))

PARTS = (((62, 344, 236, 528), 'part/part-radiator.webp'),
         ((250, 340, 480, 540), 'part/part-engine.webp'),
         ((620, 358, 850, 512), 'part/part-gearbox.webp'),
         ((1008, 300, 1195, 486), 'part/part-linkage.webp'),
         ((852, 320, 995, 480), 'part/part-axle-rear.webp'),
         ((190, 580, 510, 726), 'part/part-front-axle.webp'),
         ((316, 498, 726, 604), 'part/part-chassis.webp'),
         ((848, 430, 1110, 690), 'part/part-wheel.webp'),
         ((676, 96, 886, 310), 'part/part-cab.webp'),
         ((580, 292, 690, 372), 'part/part-battery.webp'),
         ((462, 250, 596, 352), 'part/part-fueltank.webp'),
         ((458, 102, 548, 240), 'part/part-exhaust.webp'),
         ((300, 132, 400, 240), 'part/part-aircleaner.webp'))

SCENES = (('bg/soil-field.webp', 'spin/f000.webp', 'scene/action.webp'),
          ('bg/crop-rows.webp', 'spin/f001.webp', 'scene/cultivation.webp'),
          ('bg/field-dusk.webp', 'spin/f002.webp', 'scene/dusk-run.webp'),
          ('bg/crop-rows.webp', 'spin/f000.webp', 'scene/field-work.webp'),
          ('bg/field-dusk.webp', 'spin/f009.webp', 'scene/harvesting.webp'),
          ('bg/field-sunset.webp', 'spin/f008.webp', 'scene/haulage.webp'),
          ('bg/crop-rows.webp', 'spin/f002.webp', 'scene/inter-cultivation.webp'),
          ('bg/soil-field.webp', 'spin/f005.webp', 'scene/sowing.webp'),
          ('bg/crop-rows.webp', 'spin/f004.webp', 'scene/walkaround.webp'))


def step_product_views():
    print('1/5  product views, from the 360 spin set')
    for view, frame in SPIN_VIEWS:
        Image.open(os.path.join(IMG, 'spin', frame + '.webp')).convert('RGBA') \
             .save(os.path.join(IMG, 'product', view + '.webp'), 'WEBP', quality=88, method=6)
        Image.open(os.path.join(IMG, 'spin', 'thumb-' + view + '.webp')).convert('RGBA') \
             .save(os.path.join(IMG, 'product', view + '-thumb.webp'), 'WEBP', quality=86, method=6)
    Image.open(os.path.join(IMG, 'spin', 'top.webp')).convert('RGBA') \
         .save(os.path.join(IMG, 'product', 'top.webp'), 'WEBP', quality=88, method=6)
    Image.open(os.path.join(IMG, 'spin', 'thumb-top.webp')).convert('RGBA') \
         .save(os.path.join(IMG, 'product', 'top-thumb.webp'), 'WEBP', quality=86, method=6)
    print('  %-40s %s' % ('product/<8 views> + thumbs', '(from spin/)'))

    f000 = Image.open(os.path.join(IMG, 'spin', 'f000.webp')).convert('RGBA')
    w, h = f000.size
    for box, rel, sc in (((.02, .18, .34, .74), 'product/grille.webp', 2),
                         ((.04, .28, .17, .46), 'part/part-headlamp.webp', 3),
                         ((.02, .55, .20, .95), 'part/part-tyre-front.webp', 2)):
        c = f000.crop((int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3])))
        c = c.resize((c.width * sc, c.height * sc), Image.LANCZOS)
        c.save(os.path.join(IMG, rel), 'WEBP', quality=88, method=6)
        _say(rel, c.size)
    g = Image.open(os.path.join(IMG, 'product', 'grille.webp'))
    g.thumbnail((360, 360), Image.LANCZOS)
    g.save(os.path.join(IMG, 'product', 'grille-thumb.webp'), 'WEBP', quality=86, method=6)
    ov = Image.open(os.path.join(IMG, 'product', 'overview.png')).convert('RGBA')
    ov.thumbnail((360, 360), Image.LANCZOS)
    ov.save(os.path.join(IMG, 'product', 'overview-thumb.webp'), 'WEBP', quality=86, method=6)


def step_menu_photography():
    print('2/5  menu photography (baked-in callouts painted out)')
    save_bgr(plate('Engine view'), 'product/engine.webp', thumb='product/engine-thumb.webp')
    save_bgr(plate('specifications'), 'product/showcase.webp', thumb='product/showcase-thumb.webp')
    save_bgr(clean('Operator station'), 'product/operator.webp', thumb='product/operator-thumb.webp')
    save_bgr(clean('hydraulics'), 'product/hydraulics.webp', thumb='product/hydraulics-thumb.webp')
    save_bgr(clean('Exploded View'), 'product/cutaway.webp', thumb='product/cutaway-thumb.webp')
    save_bgr(clean('Schematic Diagram'), 'product/schematic.webp')


def step_blueprints():
    print('3/5  blueprint views, from the Engineering Drawing sheet')
    dw = plate('Engineering Drawing')
    for box, rel in BLUEPRINTS:
        line_art(dw, box, rel)
    # the two tyre sections are cropped apart so the garbled sheet lettering
    # between them is left behind, then set side by side on one canvas
    fr = line_art(dw, (1054, 500, 1090, 620), None, 2.6, write=False)
    rr = line_art(dw, (1139, 492, 1198, 622), None, 2.6, write=False)
    gap = 26
    hh = max(fr.height, rr.height)
    tyres = Image.new('RGBA', (fr.width + gap + rr.width, hh), (0, 0, 0, 0))
    tyres.paste(fr, (0, hh - fr.height), fr)
    tyres.paste(rr, (fr.width + gap, hh - rr.height), rr)
    tyres.save(os.path.join(IMG, 'part', 'bp-tyres.webp'), 'WEBP', quality=92, method=6)
    _say('part/bp-tyres.webp', tyres.size)


def step_parts():
    print('4/5  component close-ups, from the exploded plate')
    src = Image.fromarray(cv2.cvtColor(clean('Exploded View'), cv2.COLOR_BGR2RGB))
    for box, rel in PARTS:
        part_cut(src, box, rel)


def step_scenes():
    print('5/5  field composites')
    for bg, pl, out in SCENES:
        scene(bg, pl, out)
    scene('bg/field-sunset.webp', 'spin/f001.webp', 'product/field.webp',
          base=.93, thumb='product/field-thumb.webp')


def main():
    if not os.path.isdir(SRC):
        sys.exit('no %r — the supplied menu plates are not in this checkout.'
                 % os.path.relpath(SRC, ROOT))
    step_product_views()
    step_menu_photography()
    step_blueprints()
    step_parts()
    step_scenes()
    print('done.')


if __name__ == '__main__':
    main()
