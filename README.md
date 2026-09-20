# STANDARD · Product Experience Platform — static demo build

A single-page, fully static product experience for the STANDARD DI 470, built to a
fixed **16:9 stage (1600 × 900)** that scales to any screen without scrolling, and
reflows to a normal scrolling document on tablet and phone.

Serve the folder over HTTP and open `index.html`:

```
npx serve .        # or: python -m http.server 8080
```

A server is required: `index.html` is a shell that loads its screens from
`parts/` with `fetch()`, which browsers block on `file://`. To hand someone a
single double-clickable file instead, run `python tools/build-html.py` — it
writes `standalone.html` with the parts already inlined. (HTTP is what you want
anyway; the 3D model and the video stream need proper MIME types.)

---

## 1. What is where

```
index.html                     ← THE SHELL. <head> + the loader that pulls parts/ in.
standalone.html                ← BUILD OUTPUT (optional). Same page, parts inlined.
parts/                         ← EDIT HERE. The eight pieces the shell loads at runtime.
  02-icon-sprite.html            the <symbol id="i-*"> sprite
  03-app-chrome.html             stage, top bar, tab nav, rail
  04-listing-overview.html       01 Listing · 02 Overview
  05-view-360.html               03 360° View
  06-diagrams.html               04 Exploded · 05 Schematic · 06 Drawing
  07-detail-screens.html         07 Exterior · 08 Engine · 09 Operator · 10 Hydraulics · 11 Features
  08-content-screens.html        12 Specs · 13 Videos · 14 Gallery · 15 Brochure
  09-compare-enquire-footer.html 16 Compare · 17 Variants · 18 Enquire, footer bar
assets/
  css/
    tokens.css     ★ BRAND — the only file you touch to re-skin the platform
    base.css         reset, the 16:9 scaling root, type scale
    ui.css           shared components (buttons, panels, hotspots, tables…)
    rail.css         the master dashboard rail
    screens.css      Listing · Overview · 360° View
    diagrams.css     Exploded · Schematic · Engineering Drawing
    detail.css       Exterior · Engine · Operator · Hydraulics · Features
    content.css      Specs · Videos · Gallery · Brochure · Compare · Variants · Enquire
    responsive.css   tablet / phone / touch / print
  js/
    config.js      ★ DEMO CONFIG — model, video and feature-flag URLs
    core.min.js      the runtime the page loads (minified on purpose)
    _source/core.js  readable source for core.min.js — rebuild instructions below
  img/
    product/         16 product views + matching thumbnails (rendered from the 3D model)
    part/            component close-ups and blueprint line art
    scene/           tractor-in-field composites
    bg/              generated field / sky / soil backdrops
    brand/         ★ BRAND MARK SLOT — drop the logo PNG here and point
                     the two <img class="brand__logoImg"> tags at it
                     (top bar + footer). Empty slot = image placeholder.
  models/
    tractor-di470.glb  the 3D model used for AR ("View in your space")
  img/spin/            ★ the 360° spin set — built by tools/build-spin.py
  data/
    hotspots-360.json  per-frame marker coordinates, built from the keyframes
tools/
  build-html.py        index.html + parts/ -> standalone.html  (offline copy only)
  build-menu-art.py  ★ ONE COMMAND: menu plates in, every shipped still out
  build-spin.py      ★ ONE COMMAND: plates in, finished 360° set out
  key-frames.py        cuts supplied product plates off their black backdrop
  pack-frames.py       PNG → webp packer; crops, builds the half-size set
  hotspots-views.json  ★ eight authored marker keyframes, interpolated to N
  build-hotspots.py    compiles the above into the runtime marker table
  turntable.py         Blender renderer, for when a real 3D model exists
_reference/                    the supplied UI reference screens (not shipped)
_source-photography/           the supplied product plates (not shipped)
all the menu images/           the supplied per-menu photography (not shipped)
```

**Rule of thumb:** content lives in `parts/`, colour lives in `tokens.css`,
endpoints live in `config.js`. Everything else is engine.

### Editing the page

**Edit the file in `parts/` and reload the browser. There is no build step.**

`index.html` holds the `<head>` and a small loader. On load it fetches every
file in its `PARTS` array, joins them in that order and writes the result into
`<body>` in one go, then starts `core.min.js` — so the runtime always boots
against a complete DOM. Adding a screen means adding its file to that array;
that array is the only registry there is.

The parts are **fragments, not pages**: `parts/03` opens the `<div class="stage">`
that `parts/09` closes, and they only balance once joined. So never open a part
on its own, and never reorder the list. The page has to stay one document — it
is a single hash-routed app where every screen shares a DOM with the rail, the
top bar and the router in `core.min.js`.

Edit the `<head>` — meta tags, fonts, stylesheet links — in `index.html` itself.

The one thing `fetch()` cannot do is run off the filesystem, so for a
double-clickable copy — a zip, a USB stick, an e-mail attachment — inline the
parts into a self-contained file:

```
python tools/build-html.py            # index.html + parts/  ->  standalone.html
python tools/build-html.py --check    # exit 1 if standalone.html is stale (for CI)
```

That is a plain concatenation with no templating and no rewriting, and it reads
the part list out of `index.html` rather than keeping its own copy, so the two
can never drift. `standalone.html` is a derived artifact: never edit it, and
re-run the packer after changing a part or the shell.

---

## 2. Re-branding — 6 values, one file

Open `assets/css/tokens.css`. Inside `[data-brand="standard"]` there are six
seed values marked ★:

```css
--seed-primary:  #0068FE;   /* action blue   */
--seed-deep:     #0C2742;   /* deep navy     */
--seed-accent:   #FED047;   /* accent yellow */
--seed-ink:      #0E263C;   /* text ink      */
--seed-surface:  #FFFFFF;   /* card surface  */
--seed-canvas:   #F3F9FE;   /* page canvas   */
```

Change those and the whole platform follows — buttons, rails, bands, hotspots,
badges, tables, footers.

### Adding a second product line with its own colour

1. Copy the entire `[data-brand="standard"] { … }` block.
2. Rename the selector, e.g. `[data-brand="agrimax"]`.
3. Change the six seeds. Leave the rest alone.
4. Set it on the page: `<html lang="en" data-brand="agrimax">`.

A worked example (`[data-brand="agrimax"]`, green) already ships in the file as a
copy-paste template.

---

## 3. The master dashboard rail

`parts/03-app-chrome.html` → `<nav class="rail" id="rail">`.

* **Collapsed it shows icons only (6.4rem).** Hovering — or focusing with the
  keyboard, or tapping once on touch — expands it to the full labelled menu.
  It is an overlay, so expanding never reflows the 16:9 layout.
* Each entry is one line:

  ```html
  <a class="rail__item" href="#engine" data-goto="engine">
    <svg class="i"><use href="#i-engine"></use></svg><span>Engine</span>
  </a>
  ```

* `data-goto="<screen-id>"` is the entire navigation API. Put it on any element —
  link, button, card — and it routes to `<section id="s-<screen-id>">`.
* The rail changes skin per screen through `data-rail` on each `<section>`:
  `solid` (navy rail, content pushed clear of it), `overlay` (same navy rail, but
  the screen is full-bleed and reserves its own gutter) or `none` (corporate
  screens: listing, compare).

---

## 4. Hotspots

Modelled on the supplied hotspot reference: a pulsing blue marker, an attached
label, and a rich card with image + copy on click.

```html
<button class="hotspot" type="button" style="left:47%;top:52%"
        data-title="Engine"
        data-img="assets/img/part/part-gearbox.webp"
        data-text="3-cylinder, 4-stroke DI engine…">
  <span class="hotspot__dot"><svg class="i"><use href="#i-plus"></use></svg></span>
  <span class="hotspot__note"><b>Engine</b><span>High torque, fuel efficient</span></span>
</button>
```

* `style="left:%;top:%"` positions it over a flat image.
* `data-side="left"` flips the label to the other side of the marker.
* Swap `.hotspot__note` for `.hotspot__chip` to get the compact dark label used on
  the 360° screen.

**On the 360° screen the hotspots carry `data-hs="<key>"`** and are positioned
per view from `assets/data/hotspots-360.json`, so they follow the product as it
turns and hide on the views where that part is out of sight. Edit the positions
in `tools/hotspots-views.json`, then run `python tools/build-hotspots.py`.

`data-position="x y z"` on those same buttons is a **bounding-box fraction**
(x 0=left 1=right, y 0=front 1=rear, z 0=ground 1=roofline). It is unused by the
photography pipeline and is there for `tools/turntable.py`, which projects it
exactly when a real 3D model is rendered.

---

## 5. 3D, 360° and video — what is real and what is a placeholder

| Feature | Status in this build |
|---|---|
| **360° drag-to-rotate** | **Real, from photography.** Ten views of one tractor, plus Top View, from `assets/img/spin/`. Drag steps between them with a short crossfade, the 9 thumbnails target the eight named views, Auto Rotate / Reset View / Full Screen all work. Not WebGL and not a continuous turntable: each view is a finished photograph, which is what makes it look like the product instead of a shaded model. |
| **AR ("View in your space")** | **Real** on AR-capable phones — `<model-viewer>` ships WebXR / Scene Viewer / Quick Look. |
| **360° / immersive video** | Wired to a public equirectangular demo clip (three.js sample asset) rendered onto a video sphere. Needs a connection. |
| **Product video player** | Custom control bar (play, scrub, time, mute, fullscreen) over a real `<video>` pointed at a public demo clip. |
| **The tractor on the 360° screen** | The supplied STANDARD product photography, keyed and size-matched. **One tractor** (generation run 5) — see "One identity" below. |
| **The tractor everywhere else** | **Real.** The eight named product views are the spin plates themselves, so every card, thumbnail and gallery tile shows the same tractor the turntable does. Engine, Operator Station, Hydraulics, Features, Exploded and Schematic use the supplied per-menu photography; the component close-ups and blueprint views are cropped out of the exploded plate and the drawing sheet. All of it is rebuilt by `tools/build-menu-art.py`. |

### Rebuilding the spin set from supplied photography

```
python tools/build-spin.py
```

That is the whole job. Plates live in `_source-photography/`, are taken in
**filename order** (that order IS the turn order), and any frame count works —
the build writes the frame count into `config.js` and re-points the thumbnail
strip itself, so nothing is left stale. `_source-photography/SHOT-LIST.md` is
the brief for generating them.

* `key-frames.py` cuts the product off its black plate. It does **not**
  threshold: measured on these plates the backdrop and large parts of the
  tyres are both exactly luma 0, so it rebuilds the silhouette from where
  signal exists instead. It then scales every frame to ONE COMMON HEIGHT and
  parks it on one baseline and one axis — height, because a rigid body's
  height does not change as it turns. Fitting each frame to a box instead
  makes narrow views larger than wide ones and the product visibly pulses
  (it was doing exactly that, at ~10%; it is now 0.0%).
* Marker positions are authored **once, as eight keyframes** in
  `tools/hotspots-views.json` and interpolated around the ring, so changing the
  frame count costs nothing. They are stored against the product's own bounding
  box, not the frame, so re-packing cannot slide them off the part they name.

**One identity, or it looks wrong.** The 58 plates originally supplied were six
different tractors — decals, grille and tyres all changed between generation
runs — and that is what reads as broken when the viewer turns. The set shipped
here is run 5 alone. The other 48 plates are kept in
`_source-photography/rejected-other-tractors/`. Generate every new angle
image-conditioned on `_source-photography/REFERENCE-PLATE.png`, never from a
fresh prompt, or the problem comes straight back.

### Rebuilding the menu photography

```
python tools/build-menu-art.py
```

That is the whole job. The supplied plates live in `all the menu images/` and
the script writes every still the page uses: the five photographed screens,
the two diagram canvases, the four blueprint views and three detail views
cropped out of the Engineering Drawing sheet, the component close-ups cropped
out of the exploded plate, the eight named product views taken from the spin
set, and the tractor-in-field composites.

**Four of the supplied plates have callout cards baked into the pixels**, and
the lettering in them is generated rather than typeset — it does not spell the
parts it points at. The page draws its own hotspots over the same positions
with the real copy, so the baked ones are painted out first: `exemplar_fill()`
replaces each card with the best-matching block from the same horizontal band
of the photograph, or of its mirror, which is what makes a symmetric rear view
fill convincingly. Anything it leaves behind ends up underneath the live
marker that replaced it. The schematic is the exception — its callouts sit on
flat, pale background where a diffusion inpaint is cleaner, and the machine is
not symmetric, so mirroring would clone the grille.

The callout coordinates are measured on the 1248x832 plates as supplied and
listed in `CALLOUTS` / `SCHEMATIC_RECTS` at the top of the script. Regenerate
the plates and those need re-measuring.

### Re-rendering the spin set from a 3D model instead

`tools/turntable.py` renders a full 48-frame turntable from a `.glb`/`.fbx`/
`.blend` in headless Blender, and projects the markers exactly (it owns the
camera, so no hand-authoring). Kept for when a real product model exists:

```
blender -b -P tools/turntable.py -- --model <your.glb> --out .work/render         --json .work/render/hotspots-360.json --res 1200 --samples 48         --yaw 180 --repaint --clean --exposure 1.5
python tools/pack-frames.py --src .work/render --json .work/render/hotspots-360.json
```

Check one frame with `--test` before committing to all 48; a render is roughly
a minute a frame on a mid-range GPU.

**Swapping in the real product:** drop your `.glb` anywhere, run the two commands
above, and the 360° screen follows. For AR, also replace
`assets/models/tractor-di470.glb` (or repoint `viewer3d.model` in `config.js`).

Public demo sources are declared once, in `assets/js/config.js`:

```js
viewer3d: { model, modelFallbacks, environment, componentSrc, angles }
video360: { src, poster, threeSrc }
video:    { src, poster }
```

---

## 6. "Add to Cart" is intentionally inactive

It appears in the top bar on every screen and again on the Enquiry form, rendered
in a disabled state (`disabled aria-disabled="true"`, greyed, `cursor: not-allowed`).
Commerce is off behind `flags.commerceEnabled` in `config.js`. Nothing is wired to
a basket — that is deliberate for this demo.

Other demo-only controls carry `data-inert="…message…"`; clicking one shows a toast
instead of failing silently. Search for `data-inert` to find every stub in one pass.

---

## 7. Rebuilding the runtime

The page loads `assets/js/core.min.js`. The readable source is
`assets/js/_source/core.js`. After editing the source:

```
npx terser assets/js/_source/core.js -c -m --toplevel -o assets/js/core.min.js
```

The shipped file is minified deliberately: the behaviour layer is not meant to be
edited in place. Content and copy stay in plain HTML so they *can* be.

---

## 8. Responsive behaviour

| Viewport | Behaviour |
|---|---|
| ≥ 1100px landscape | Locked 16:9 stage. `1rem = min(100vw/160, 100vh/90)`, so the whole UI scales as one crisp piece and always fits without scrolling. |
| ≤ 1100px or portrait | Leaves the stage: normal scrolling document, rail becomes a horizontal icon bar under a sticky header, grids collapse to 2 columns. |
| ≤ 680px | Single column, larger tap targets, decorative script and inline hotspot labels hidden. |
| Touch (`hover: none`) | First tap opens the rail, second navigates. Larger hotspot markers and buttons. |
| Print | Flattens to a plain document, one screen per page. |

---

## 9. Moving to Laravel

The structure is already shaped for it:

* Each `<section class="screen" id="s-NAME">` maps to a Blade partial —
  `resources/views/product/_NAME.blade.php`. The split in `parts/` is already
  most of that move.
* The `<head>` in `index.html`, `parts/02`–`03` and the footer in `parts/09`
  become `layouts/product.blade.php`: the icon sprite, top bar, rail and footer
  are the layout; the sections are `@include`s, and Blade replaces the loader.
* `assets/js/config.js` becomes
  `<script>window.STD_CONFIG = @json($config)</script>` — the object shape is
  already the contract.
* The rail is data-driven by nothing but markup, so it becomes a
  `@foreach ($sections as $s)` loop.
* Every table, spec row and card is real markup, never an image, so each one maps
  cleanly to a model attribute.

Nothing in the CSS or the runtime assumes a static host.

---

## 10. Asset credits

* 360° spin set: built from the STANDARD product photography supplied by the
  client, kept unshipped in `_source-photography/`. No third-party rights.
* AR / product stills: "Tractor" — Poly Pizza, **CC-BY**. Recoloured and
  re-packed for this demo. Attribute or replace before any public use.
* Blender (Cycles), used to render the spin set — GPL.
* `<model-viewer>` — Google, Apache-2.0, loaded from the Google Ajax CDN.
* three.js and its sample equirectangular clip — MIT, loaded from jsDelivr /
  threejs.org.
* Fonts: Inter and Caveat, Google Fonts (SIL Open Font License).
* All backdrops, scene composites, blueprint line art and product stills were
  generated for this build and carry no third-party rights.
