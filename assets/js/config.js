/* ============================================================================
   STANDARD · PRODUCT EXPERIENCE PLATFORM
   DEMO CONFIGURATION  —  safe to edit, no logic lives here.
   ----------------------------------------------------------------------------
   Everything that points at an asset, a model or a stream is declared once,
   here. When the Laravel build lands, this object is the shape the backend
   should render into the page (window.STD_CONFIG = @json($config)).
   ========================================================================== */

window.STD_CONFIG = {

  /* -- Which screen opens first -------------------------------------------- */
  startScreen: 'listing',

  /* -- 3D / 360° demo sources ---------------------------------------------- */
  viewer3d: {
    /* Local, brand-recoloured demo model. Swap this file to change the
       product shown in the 360° / 3D / AR viewers. */
    model: 'assets/models/tractor-di470.glb',

    /* Fallback models, tried in order if `model` above cannot be loaded.
       DELIBERATELY EMPTY. Only ever put a BRAND-CORRECT model here: a
       generic public sample would silently change the product's colour,
       which is worse than showing no 3D at all. When every entry fails the
       viewer shows the static product render already in the markup plus
       `strings.offline3d` below.

       The usual reason for a failure is opening index.html by double-
       clicking it: on file:// Chrome refuses to fetch the local .glb.
       Serve the folder (npx serve .) and the blue model loads. */
    modelFallbacks: [],

    /* Image-based lighting for the 3D stage (public HDRI from modelviewer.dev) */
    environment: 'https://modelviewer.dev/shared-assets/environments/aircraft_workshop_01_1k.hdr',

    /* <model-viewer> is Google's official web component. Loaded on demand,
       only when a 3D panel is first opened. */
    componentSrc: 'https://ajax.googleapis.com/ajax/libs/model-viewer/3.4.0/model-viewer.min.js',

    /* Camera presets driving the bottom angle strip (azimuth, elevation) */
    angles: {
      'front':       '0deg 80deg',    'front-left':  '45deg 78deg',
      'left':        '90deg 80deg',   'rear-left':   '135deg 78deg',
      'rear':        '180deg 80deg',  'rear-right':  '225deg 78deg',
      'right':       '270deg 80deg',  'front-right': '315deg 78deg',
      'top':         '0deg 6deg'
    }
  },

  /* -- 360° spin sequence (the product turntable) -------------------------- */
  spin360: {
    /* Views built from the supplied product photography, evenly spaced around
       the turn. NOT a rendered turntable: each plate is its own photograph, so
       this is a ring of real viewpoints and dragging steps between them with a
       short crossfade.

       `frames` and `start` are WRITTEN BY tools/build-spin.py to match whatever
       set was last built — change the plates, not these numbers. */
    frames: 10,
    src: 'assets/img/spin/f{n}.webp',

    /* Phones take the half-size set, which is roughly a quarter of the bytes
       and a fraction of the decoded bitmap. smallStep >1 additionally skips
       frames; at these counts every frame is wanted, so it stays 1. */
    srcSmall: 'assets/img/spin/half/f{n}.webp',
    smallBelow: 900,
    smallStep: 1,

    /* Frame order IS the turn order, starting at the front and going once
       around. The eight named views are spread evenly across it and are what
       the thumbnail strip targets — see data-frame in index.html, also written
       by the build. Top View is not on the ring; it is a separate still. */
    topSrc: 'assets/img/spin/top.webp',
    start: 1,

    /* Authored as eight keyframes in tools/hotspots-views.json and interpolated
       around the ring by tools/build-hotspots.py, so the frame count can change
       without re-authoring anything. */
    hotspots: 'assets/data/hotspots-360.json',

    dragSensitivity: 0.030,  /* views per pixel of horizontal drag              */
    crossfade: 160,          /* ms; a hard cut between views reads as a jump    */
    autoRotateFps: 3.2,      /* views per second while Auto Rotate is on        */
    preload: 16              /* frames fetched before the stage is revealed     */
  },

  /* -- 360° / immersive video --------------------------------------------- */
  video360: {
    /* Public equirectangular demo clip shipped with three.js examples. */
    src: 'https://threejs.org/examples/textures/MaryOculus.webm',
    poster: 'assets/img/bg/crop-rows.webp',
    /* three.js modules, loaded on demand for the equirectangular sphere. */
    threeSrc: 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js'
  },

  /* -- Standard video player ----------------------------------------------- */
  video: {
    src: 'https://threejs.org/examples/textures/MaryOculus.webm',
    poster: 'assets/img/bg/crop-rows.webp'
  },

  /* -- Feature switches ---------------------------------------------------- */
  flags: {
    /* "Add to Cart" is intentionally inert in this demo build. */
    commerceEnabled: false,
    autoRotate3d: false,
    railStartsOpen: false
  },

  /* -- Copy for inert demo controls ---------------------------------------- */
  strings: {
    inert: 'Demo build — this action is wired up in the Laravel release.',
    cart: 'Add to Cart is disabled in the static demo.',
    offline3d: 'The 3D viewer needs this folder served over HTTP. Run  npx serve .  here, then reload.',
    offline360: 'The 360° frames could not be loaded. Serve this folder over HTTP (npx serve .) and reload.',
    noAR: 'AR needs a recent phone or tablet — open this page on one to view the tractor in your space.'
  }
};
