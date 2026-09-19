/* ============================================================================
   STANDARD · PRODUCT EXPERIENCE PLATFORM — CORE RUNTIME (source)
   ----------------------------------------------------------------------------
   This file is the readable source for assets/js/core.min.js, which is the
   file the page actually loads. Rebuild after editing:

       npx terser assets/js/_source/core.js -c -m --toplevel \
            -o assets/js/core.min.js

   Nothing in here is content. Copy lives in index.html, settings in config.js.
   ========================================================================== */
(function (win, doc) {
  'use strict';

  var CFG = win.STD_CONFIG || {};
  var $  = function (s, r) { return (r || doc).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || doc).querySelectorAll(s)); };
  var on = function (el, ev, fn, o) { el && el.addEventListener(ev, fn, o || false); };

  var stage, screensEl, rail, toaster;
  var current = '';

  /* ------------------------------------------------------------------ utils */
  function toast(msg) {
    if (!toaster) return;
    var t = doc.createElement('div');
    t.className = 'toast'; t.textContent = msg;
    toaster.appendChild(t);
    win.setTimeout(function () {
      t.classList.add('is-out');
      win.setTimeout(function () { t.remove(); }, 260);
    }, 2200);
  }

  /* On tablet and phone the rail is a horizontally scrolling icon bar, so the
     entry for the screen you just opened is frequently off to the right.
     Bring it back into view; on the desktop rail this is a no-op. */
  function revealRailItem(id) {
    if (!rail) return;
    var nav = $('.rail__nav', rail);
    if (!nav || nav.scrollWidth <= nav.clientWidth + 2) return;
    var item = $('.rail__item[data-goto="' + id + '"]', nav);
    if (!item) return;
    var target = item.offsetLeft - (nav.clientWidth - item.offsetWidth) / 2;
    var max = nav.scrollWidth - nav.clientWidth;
    nav.scrollTo({
      left: Math.max(0, Math.min(max, target)),
      behavior: win.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
    });
  }

  /* ------------------------------------------------------ contextual slots
     Any element carrying data-on="a b c" is only shown while one of those
     screen ids is active. Keeps per-screen chrome declarative in the HTML. */
  function syncSlots(id) {
    $$('[data-on]').forEach(function (el) {
      var list = el.getAttribute('data-on').split(/\s+/);
      el.hidden = list.indexOf(id) < 0 && list.indexOf('*') < 0;
    });
    $$('[data-off]').forEach(function (el) {
      el.hidden = el.getAttribute('data-off').split(/\s+/).indexOf(id) > -1;
    });
  }

  /* ------------------------------------------------------------- navigation */
  function go(id, push) {
    var next = $('#s-' + id);
    if (!next) { id = CFG.startScreen || 'listing'; next = $('#s-' + id); }
    if (!next || id === current) { if (next) syncSlots(id); return; }

    var prev = $('.screen.is-active', screensEl);
    if (prev) prev.classList.remove('is-active');
    next.classList.add('is-active');
    current = id;

    stage.setAttribute('data-screen', id);
    stage.setAttribute('data-rail', next.getAttribute('data-rail') || 'solid');
    stage.setAttribute('data-chrome', next.getAttribute('data-chrome') || 'product');

    $$('[data-goto]').forEach(function (a) {
      a.classList.toggle('is-active', a.getAttribute('data-goto') === id);
    });
    syncSlots(id);
    if (push !== false && win.location.hash.slice(1) !== id) {
      win.history.pushState(null, '', '#' + id);
    }
    next.scrollTop = 0;
    revealRailItem(id);
    /* Off the 16:9 stage the document itself scrolls, so a screen change has
       to return to the top — otherwise the new screen opens part-way down. */
    if (doc.documentElement.scrollHeight > win.innerHeight + 4) {
      win.scrollTo(0, 0);
    }
    win.dispatchEvent(new CustomEvent('std:screen', { detail: { id: id, el: next } }));
  }

  /* ----------------------------------------------------------------- rail */
  function initRail() {
    rail = $('#rail');
    if (!rail) return;
    if (CFG.flags && CFG.flags.railStartsOpen) rail.classList.add('is-open');

    /* The two-tap affordance only makes sense for the COLLAPSED vertical rail,
       where the labels are hidden until it expands. Tablet and phone lay the
       rail out as a horizontal bar whose labels are always visible, so there
       swallowing the first tap just made every menu entry need two taps. */
    var isCollapsibleRail = function () {
      var nav = $('.rail__nav', rail);
      return !!nav && win.getComputedStyle(nav).flexDirection === 'column';
    };

    /* touch devices have no hover: first tap opens, second navigates */
    if (win.matchMedia('(hover: none)').matches) {
      on(rail, 'click', function (e) {
        if (!isCollapsibleRail()) return;
        if (!rail.classList.contains('is-open')) {
          e.preventDefault(); e.stopPropagation();
          rail.classList.add('is-open');
        }
      }, true);
      on(doc, 'click', function (e) {
        if (rail && !rail.contains(e.target)) rail.classList.remove('is-open');
      });
    }
    revealRailItem(current);
  }

  /* -------------------------------------------------------------- hotspots */
  function closeCards(root) {
    $$('.hotcard', root || doc).forEach(function (c) { c.remove(); });
    $$('.hotspot.is-open', root || doc).forEach(function (h) { h.classList.remove('is-open'); });
  }

  /* Cards are placed from the marker's REAL rendered rect, not from inline
     percentages. On the 360deg screen the markers live inside <model-viewer>
     and are positioned by the viewer itself, so they carry no style.left/top
     at all - reading those produced NaN and dumped the card in the corner. */
  var GAP = 12, EDGE = 10;

  function cardHost(hs) {
    return hs.closest('.hotlayer') ||          /* flat-image screens          */
           hs.closest('[data-fs]')  ||          /* 3D stage wrapper            */
           hs.offsetParent || hs.parentNode;
  }

  function placeCard(card, hs, host) {
    var hr = hs.getBoundingClientRect(), br = host.getBoundingClientRect();
    if (!hr.width || !br.width) { card.style.visibility = 'hidden'; return; }
    card.style.visibility = '';

    var cw = card.offsetWidth, ch = card.offsetHeight;
    var x = hr.right - br.left + GAP;                 /* prefer to the right   */
    if (x + cw > br.width - EDGE) x = hr.left - br.left - cw - GAP;  /* flip   */
    var y = hr.top - br.top + hr.height / 2 - ch / 2; /* vertically centred    */

    card.style.left = Math.max(EDGE, Math.min(x, br.width  - cw - EDGE)) + 'px';
    card.style.top  = Math.max(EDGE, Math.min(y, br.height - ch - EDGE)) + 'px';
  }

  function repositionCards() {
    $$('.hotcard').forEach(function (c) {
      if (c.__anchor && c.__host) placeCard(c, c.__anchor, c.__host);
    });
  }

  function openCard(hs) {
    var host = cardHost(hs);
    closeCards();
    hs.classList.add('is-open');

    var card = doc.createElement('div');
    card.className = 'hotcard';
    var img = hs.getAttribute('data-img');
    card.innerHTML =
      '<button class="hotcard__close" type="button" aria-label="Close">' +
        '<svg class="i i--xs"><use href="#i-x"></use></svg></button>' +
      (img ? '<div class="hotcard__media"><img src="' + img + '" alt=""></div>' : '') +
      '<div class="hotcard__body">' +
        '<div class="hotcard__title">' + (hs.getAttribute('data-title') || '') + '</div>' +
        '<p class="hotcard__text">' + (hs.getAttribute('data-text') || '') + '</p>' +
      '</div>';

    card.__anchor = hs; card.__host = host;
    card.style.visibility = 'hidden';
    host.appendChild(card);
    placeCard(card, hs, host);

    on($('.hotcard__close', card), 'click', function (e) { e.stopPropagation(); closeCards(); });
  }

  function initHotspots() {
    on(doc, 'click', function (e) {
      var hs = e.target.closest ? e.target.closest('.hotspot') : null;
      if (hs) { e.preventDefault(); openCard(hs); return; }
      if (!(e.target.closest && e.target.closest('.hotcard'))) closeCards();
    });
    on(doc, 'keydown', function (e) { if (e.key === 'Escape') closeCards(); });
    on(win, 'resize', repositionCards);
  }

  /* ------------------------------------------------------------ thumbstrip */
  function initThumbs() {
    on(doc, 'click', function (e) {
      var th = e.target.closest ? e.target.closest('.thumb') : null;
      if (!th) return;
      var strip = th.closest('.thumbstrip');
      $$('.thumb', strip).forEach(function (t) { t.classList.remove('is-active'); });
      th.classList.add('is-active');

      var view = th.getAttribute('data-view');
      var screen = th.closest('.screen');
      var target = screen && $('[data-view-target]', screen);
      if (target && view) {
        var src = th.getAttribute('data-full') ||
                  ('assets/img/product/' + view + '.webp');
        if (target.tagName === 'IMG') {
          target.style.opacity = '0';
          var pre = new Image();
          pre.onload = function () { target.src = src; target.style.opacity = '1'; };
          pre.src = src;
        }
      }
      /* 360° screen: the strip is a set of frame presets on the spin set.
         Falls through to the camera presets on any screen still on 3D. */
      var sp = spinIn(screen), fr = th.getAttribute('data-frame');
      if (sp && fr !== null) {
        if (fr === 'top') sp.showTop(); else sp.goTo(parseInt(fr, 10));
      } else {
        var mv = screen && $('model-viewer', screen);
        if (mv && view && CFG.viewer3d && CFG.viewer3d.angles[view]) {
          mv.setAttribute('camera-orbit', CFG.viewer3d.angles[view] + ' auto');
        }
      }
      closeCards();
    });
  }

  /* -------------------------------------------------------- 3D / AR viewer */
  var mvLoading = null;
  function loadModelViewer() {
    if (win.customElements && win.customElements.get('model-viewer')) return Promise.resolve();
    if (mvLoading) return mvLoading;
    mvLoading = new Promise(function (res) {
      var s = doc.createElement('script');
      s.type = 'module';
      s.src = (CFG.viewer3d && CFG.viewer3d.componentSrc) || '';
      s.onload = function () { res(); };
      s.onerror = function () { res(); };
      doc.head.appendChild(s);
    });
    return mvLoading;
  }

  function mountViewer(host) {
    if (!host || host.getAttribute('data-mounted')) return;
    host.setAttribute('data-mounted', '1');
    var v3 = CFG.viewer3d || {};
    loadModelViewer().then(function () {
      var mv = doc.createElement('model-viewer');
      mv.setAttribute('src', v3.model || '');
      mv.setAttribute('alt', host.getAttribute('data-alt') || 'Interactive 3D model');
      mv.setAttribute('camera-controls', '');
      mv.setAttribute('touch-action', 'pan-y');
      mv.setAttribute('shadow-intensity', '1.1');
      mv.setAttribute('shadow-softness', '.8');
      mv.setAttribute('exposure', '1.05');
      mv.setAttribute('interaction-prompt', 'none');
      mv.setAttribute('min-camera-orbit', 'auto auto 4%');
      mv.setAttribute('camera-orbit', host.getAttribute('data-orbit') || '-45deg 78deg auto');
      mv.setAttribute('field-of-view', host.getAttribute('data-fov') || '26deg');
      if (host.getAttribute('data-target')) mv.setAttribute('camera-target', host.getAttribute('data-target'));
      if (host.hasAttribute('data-ar')) {
        mv.setAttribute('ar', '');
        mv.setAttribute('ar-modes', 'webxr scene-viewer quick-look');
      }
      if (v3.environment) mv.setAttribute('environment-image', v3.environment);
      if (CFG.flags && CFG.flags.autoRotate3d) mv.setAttribute('auto-rotate', '');

      var tries = 0;
      mv.addEventListener('error', function () {
        var fb = (v3.modelFallbacks || [])[tries++];
        if (fb) { mv.setAttribute('src', fb); return; }
        /* Nothing brand-correct left to try. Keep the product's own colour
           on screen rather than substituting someone else's model. */
        host.classList.add('is-failed');
        if (!$('.viewer__offline', host)) {
          var n = doc.createElement('p');
          n.className = 'viewer__offline';
          n.textContent = (CFG.strings && CFG.strings.offline3d) || '';
          host.appendChild(n);
        }
      });
      mv.addEventListener('load', function () { host.classList.add('is-ready'); });

      /* the markers move with the geometry, so an open card must follow */
      var pending = 0;
      mv.addEventListener('camera-change', function () {
        if (pending) return;
        pending = win.requestAnimationFrame(function () { pending = 0; repositionCards(); });
      });

      host.appendChild(mv);
      /* declarative hotspots move into the viewer so they track the geometry */
      Array.prototype.slice.call(host.querySelectorAll('[slot^="hotspot"]'))
        .forEach(function (h) { mv.appendChild(h); });
    });
  }

  function initViewers() {
    var io = win.IntersectionObserver ? new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { mountViewer(e.target); io.unobserve(e.target); } });
    }, { rootMargin: '200px' }) : null;

    on(win, 'std:screen', function (e) {
      $$('[data-viewer3d]', e.detail.el).forEach(function (h) {
        if (io) io.observe(h); else mountViewer(h);
      });
    });
  }

  /* ------------------------------------------------------- 360° spin viewer
     A pre-rendered turntable: N frames, evenly spaced, each one a finished
     render. That is how every serious product configurator does it — the
     product cannot look "cartoon" because nothing is shaded at runtime.

     Horizontal drag maps onto the frame index. The markers ride along on a
     per-frame coordinate table baked by tools/turntable.py, so they track the
     geometry exactly as they did inside <model-viewer>.                     */

  function spinIn(screen) {
    var h = screen && $('[data-spin360]', screen);
    return (h && h.__spin) || null;
  }

  function mountSpin(host) {
    if (!host || host.__spin) return host && host.__spin;

    var cfg = CFG.spin360 || {};
    var N   = cfg.frames | 0;
    if (!cfg.src || N < 2) return null;

    var SENS  = cfg.dragSensitivity || 0.55;
    var START = Math.min(Math.max(cfg.start | 0, 0), N - 1);

    /* Small screens take the half-size set and every Nth frame — see the note
       in config.js. Decided once at mount: re-deciding on resize would throw
       away a warm cache to redundantly reload what is already on screen. */
    var small = win.innerWidth <= (cfg.smallBelow || 900);
    var SRC   = (small && cfg.srcSmall) ? cfg.srcSmall : cfg.src;
    var STEP  = small ? Math.max(1, cfg.smallStep | 0) : 1;

    /* The frame box shrink-wraps the render, so the baked marker percentages
       land on the product rather than on the stage's empty margins. */
    var box = doc.createElement('div');
    box.className = 'v360__box';

    /* Two stacked layers so a step can crossfade. With a 48-frame turntable a
       hard cut is invisible; across 45° steps it reads as a jump. The first
       layer stays in flow and gives the box its size, the second is laid over
       it — swapping which one is opaque is the whole effect. */
    var CROSS = Math.max(0, cfg.crossfade | 0);

    function layer(cls) {
      var el = doc.createElement('img');
      el.className = cls;
      el.draggable = false;
      el.decoding = 'async';
      if (CROSS) el.style.transition = 'opacity ' + CROSS + 'ms linear';
      box.appendChild(el);
      return el;
    }
    var img = layer('v360__frame');
    img.alt = host.getAttribute('data-alt') || '';
    var imgB = layer('v360__frame v360__frame--b');
    imgB.alt = '';
    imgB.style.opacity = '0';
    var layers = [img, imgB], showing = 0;

    /* Hidden until the table says where they go. A marker with no coordinates
       would otherwise pile up in the corner of the stage. */
    $$('.hotspot', host).forEach(function (h) { h.hidden = true; box.appendChild(h); });
    host.appendChild(box);

    var cache = new Array(N);   /* replaced wholesale if the small set falls back */
    var pos = START;      /* desired position, fractional while dragging */
    var painted = -1;     /* frame currently on screen                   */
    var table = null;     /* per-frame marker coordinates                */
    var isTop = false;

    function wrap(i) { return ((i % N) + N) % N; }
    /* Snap to a frame that actually exists in this device's set. */
    function snap(i) { return wrap(Math.round(i / STEP) * STEP); }
    function srcFor(i) { return SRC.replace('{n}', ('00' + i).slice(-3)); }

    function load(i, cb) {
      i = wrap(i);
      var im = cache[i];
      if (im) { if (cb) { im.complete ? cb(im.naturalWidth ? im : null, i) : im.addEventListener('load', function () { cb(im, i); }); } return im; }
      im = cache[i] = new Image();
      im.decoding = 'async';
      im.addEventListener('load', function () {
        /* A frame that lands while it is the one being asked for has to paint
           itself. Without this, dragging ahead of the preloader leaves the
           stage frozen on the last frame that happened to be ready. */
        if (!isTop && snap(pos) === i) render();
        if (cb) cb(im, i);
      });
      im.addEventListener('error', function () { if (cb) cb(null, i); });
      im.src = srcFor(i);
      return im;
    }

    function placeHotspots(i) {
      if (!table || !table.pos) return;
      $$('.hotspot', box).forEach(function (h) {
        var k   = h.getAttribute('data-hs');
        var row = k && table.pos[k] && table.pos[k][i];
        if (isTop || !row || !row[2]) { h.hidden = true; return; }
        h.hidden = false;
        h.style.left = (row[0] * 100).toFixed(3) + '%';
        h.style.top  = (row[1] * 100).toFixed(3) + '%';
      });
      repositionCards();
    }

    /* Paint the nearest loaded frame. If the target has not arrived yet we
       hold the last good one rather than flashing an empty stage. */
    function render() {
      var i = snap(pos);
      if (i === painted && !isTop) return;
      var im = cache[i];
      if (!im || !im.complete || !im.naturalWidth) { load(i); return; }
      isTop = false;
      painted = i;
      host.setAttribute('data-frame', i);
      show(im.src);
      placeHotspots(i);
    }

    /* Paint onto whichever layer is currently hidden, then swap. */
    function show(src) {
      if (!CROSS) { layers[showing].src = src; return; }
      /* First paint goes straight onto the visible layer. Crossfading from an
         empty <img> would fade in from a broken-image box, and would leave the
         in-flow layer with no src at all. */
      if (!layers[showing].getAttribute('src')) { layers[showing].src = src; return; }
      var next = layers[1 - showing];
      next.src = src;
      next.style.opacity = '1';
      layers[showing].style.opacity = '0';
      showing = 1 - showing;
    }

    function fail() {
      host.classList.add('is-failed');
      if (!$('.viewer__offline', host)) {
        var n = doc.createElement('p');
        n.className = 'viewer__offline';
        n.textContent = (CFG.strings && CFG.strings.offline360) ||
                        (CFG.strings && CFG.strings.offline3d) || '';
        host.appendChild(n);
      }
    }

    /* -------------------------------------------------------- auto rotate */
    var aRaf = 0, aLast = 0;
    function autoStep(t) {
      aRaf = win.requestAnimationFrame(autoStep);
      var fps = cfg.autoRotateFps || 18;
      if (t - aLast < 1000 / fps) return;
      aLast = t;
      pos = snap(pos) + STEP;
      render();
    }
    function setAuto(onOff) {
      if (aRaf) { win.cancelAnimationFrame(aRaf); aRaf = 0; }
      if (onOff && !win.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        aLast = 0;
        aRaf = win.requestAnimationFrame(autoStep);
      }
    }

    /* ------------------------------------------------------------- inertia */
    var gRaf = 0, vel = 0;
    function stopGlide() { if (gRaf) { win.cancelAnimationFrame(gRaf); gRaf = 0; } vel = 0; }
    function glide() {
      if (Math.abs(vel) < 0.12) { stopGlide(); return; }
      pos -= vel * SENS;
      vel *= 0.94;
      render();
      gRaf = win.requestAnimationFrame(glide);
    }

    /* ---------------------------------------------------------------- drag */
    var DEAD = 4;                      /* px before a press counts as a drag */
    var dragging = false, captured = false, lastX = 0, moved = 0, pid = null;

    on(box, 'pointerdown', function (e) {
      if (e.button) return;
      dragging = true; captured = false; lastX = e.clientX; moved = 0; pid = e.pointerId;
      stopGlide(); setAuto(false);
      $$('[data-vc="rotate"]', host.closest('.screen') || doc).forEach(function (b) { b.classList.remove('is-on'); });
      /* Deliberately NOT capturing the pointer yet. While a capture is active
         the browser retargets the following click to the capturing element, so
         capturing on press would swallow every hotspot click. Capture starts
         below, once the press has actually become a drag. */
    });

    on(box, 'pointermove', function (e) {
      if (!dragging) return;
      var dx = e.clientX - lastX;
      lastX = e.clientX;
      moved += Math.abs(dx);
      if (!captured && moved > DEAD) {
        captured = true;
        host.classList.add('is-drag');
        if (box.setPointerCapture) { try { box.setPointerCapture(pid); } catch (_) {} }
      }
      if (!captured) return;           /* still inside the dead zone */
      vel = dx;
      /* drag right → the tractor turns to present its left flank, matching
         the direction <model-viewer> orbited before */
      pos -= dx * SENS;
      render();
    });

    function endDrag() {
      if (!dragging) return;
      dragging = false;
      host.classList.remove('is-drag');
      if (captured && box.releasePointerCapture && pid !== null) {
        try { box.releasePointerCapture(pid); } catch (_) {}
      }
      captured = false; pid = null;
      if (Math.abs(vel) > 0.6) glide();
    }
    on(box, 'pointerup', endDrag);
    on(box, 'pointercancel', endDrag);

    /* A drag that happens to finish over a marker must not open its card. */
    on(box, 'click', function (e) {
      if (moved > DEAD) { e.stopPropagation(); e.preventDefault(); moved = 0; }
    }, true);

    /* ------------------------------------------------------------ keyboard */
    host.setAttribute('tabindex', '0');
    on(host, 'keydown', function (e) {
      if (e.key === 'ArrowRight')     { pos = snap(pos) + STEP; }
      else if (e.key === 'ArrowLeft') { pos = snap(pos) - STEP; }
      else if (e.key === 'Home')      { pos = START; }
      else return;
      e.preventDefault(); setAuto(false); render();
    });

    /* --------------------------------------------------------------- boot  */
    /* An absolutely-positioned box with height:X% and a width:auto replaced
       child is circular -- the box wants the image's width, the image wants
       the box's height. Browsers resolve it to the intrinsic width and the
       product ends up the wrong size. Every frame shares one size, so pin the
       ratio from the first one that loads and the box becomes deterministic. */
    function lockRatio(im) {
      if (im && im.naturalWidth && im.naturalHeight) {
        box.style.aspectRatio = im.naturalWidth + ' / ' + im.naturalHeight;
      }
    }

    load(START, function (im) {
      if (im) {
        lockRatio(im);
        pos = START; render();
        host.classList.add('is-ready');
        rest();
        return;
      }
      /* The small set is an optimisation, not a requirement. If it is missing
         fall back to the full one rather than taking every phone offline. */
      if (SRC !== cfg.src) {
        SRC = cfg.src; STEP = 1; cache = new Array(N);
        load(START, function (im2) {
          if (!im2) { fail(); return; }
          lockRatio(im2);
          pos = START; render();
          host.classList.add('is-ready');
          rest();
        });
        return;
      }
      fail();
    });
    for (var d = 1; d <= (cfg.preload || 8); d++) { load(START + d * STEP); load(START - d * STEP); }

    /* Everything else arrives while the browser is idle, so the stage is
       interactive long before the full set has landed. */
    function rest() {
      var i = 0;
      var idle = win.requestIdleCallback || function (f) {
        return win.setTimeout(function () { f({ timeRemaining: function () { return 8; } }); }, 60);
      };
      (function step() {
        idle(function (dl) {
          var n = 0;
          while (i < N && (n < 2 || (dl.timeRemaining && dl.timeRemaining() > 4))) { load(i); i += STEP; n++; }
          if (i < N) step(); else host.classList.add('is-loaded');
        });
      })();
    }

    if (cfg.hotspots) {
      win.fetch(cfg.hotspots)
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) { if (j) { table = j; if (painted >= 0) placeHotspots(painted); } })
        .catch(function () {});
    }

    var spin = {
      goTo: function (i) { setAuto(false); stopGlide(); pos = snap(i); render(); },
      showTop: function () {
        if (!cfg.topSrc) return;
        setAuto(false); stopGlide();
        isTop = true; painted = -1;
        host.setAttribute('data-frame', 'top');
        show(cfg.topSrc);
        $$('.hotspot', box).forEach(function (h) { h.hidden = true; });
        closeCards();
      },
      reset:   function () { setAuto(false); stopGlide(); pos = START; painted = -1; render(); },
      setAuto: setAuto,
      pause:   function () { setAuto(false); stopGlide(); endDrag(); }
    };
    host.__spin = spin;
    return spin;
  }

  function initSpin360() {
    on(win, 'std:screen', function (e) {
      $$('[data-spin360]').forEach(function (h) {
        if (e.detail.el.contains(h)) mountSpin(h);
        else if (h.__spin) h.__spin.pause();       /* never spin off-screen */
      });
    });
  }

  /* ------------------------------------------------------------- AR launcher
     The spin set replaced <model-viewer> on the 360 screen, and with it went
     the AR button the component used to draw itself. AR is still a real
     feature, so it gets its own entry point: the component and the .glb are
     fetched only when someone actually asks for AR, which is also why the
     heavy 3D payload no longer loads for everyone just to offer it. */
  var arMv = null;

  function launchAR(btn) {
    var v3 = CFG.viewer3d || {};
    if (!v3.model) { toast(CFG.strings.inert); return; }

    if (arMv && arMv.canActivateAR) { arMv.activateAR(); return; }

    btn.classList.add('is-busy');
    loadModelViewer().then(function () {
      if (!(win.customElements && win.customElements.get('model-viewer'))) {
        btn.classList.remove('is-busy');
        toast((CFG.strings && CFG.strings.noAR) || CFG.strings.inert);
        return;
      }
      var mv = arMv = doc.createElement('model-viewer');
      mv.className = 'ar-proxy';
      mv.setAttribute('src', v3.model);
      mv.setAttribute('alt', 'STANDARD DI 470');
      mv.setAttribute('ar', '');
      mv.setAttribute('ar-modes', 'webxr scene-viewer quick-look');
      if (v3.environment) mv.setAttribute('environment-image', v3.environment);

      mv.addEventListener('load', function () {
        btn.classList.remove('is-busy');
        if (mv.canActivateAR) mv.activateAR();
        else toast((CFG.strings && CFG.strings.noAR) || CFG.strings.inert);
      });
      mv.addEventListener('error', function () {
        btn.classList.remove('is-busy');
        arMv = null; mv.remove();
        toast(CFG.strings.offline3d);
      });
      doc.body.appendChild(mv);
    });
  }

  function initAR() {
    on(doc, 'click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-ar-launch]') : null;
      if (!b) return;
      e.preventDefault();
      launchAR(b);
    });
  }

  /* ---------------------------------------------------- viewer control bar */
  function initViewerControls() {
    on(doc, 'click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-vc]') : null;
      if (!b) return;
      var screen = b.closest('.screen');
      var host = screen && $('[data-viewer3d]', screen);
      var mv = host && $('model-viewer', host);
      var sp = spinIn(screen);
      var act = b.getAttribute('data-vc');

      if (act === 'rotate') {
        var on_ = b.classList.toggle('is-on');
        if (sp) sp.setAuto(on_);
        else if (mv) { on_ ? mv.setAttribute('auto-rotate', '') : mv.removeAttribute('auto-rotate'); }
        else toast(CFG.strings.inert);
      } else if (act === 'reset') {
        if (sp) {
          sp.reset();
          $$('[data-vc="rotate"]', screen).forEach(function (r) { r.classList.remove('is-on'); });
        } else if (mv) {
          mv.setAttribute('camera-orbit', host.getAttribute('data-orbit') || '-45deg 78deg auto');
          mv.setAttribute('field-of-view', host.getAttribute('data-fov') || '26deg');
          if (mv.resetTurntableRotation) mv.resetTurntableRotation();
        }
        $$('.thumb', screen).forEach(function (t, i) { t.classList.toggle('is-active', i === 1); });
      } else if (act === 'full') {
        var box = (host && host.closest('[data-fs]')) || (b.closest('[data-fs]')) || screen;
        if (doc.fullscreenElement) doc.exitFullscreen();
        else if (box && box.requestFullscreen) box.requestFullscreen().catch(function () { toast(CFG.strings.inert); });
      }
    });
  }

  /* ------------------------------------------------------- 360° video tile */
  function init360Video() {
    on(doc, 'click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-play360]') : null;
      if (!b) return;
      var wrap = b.closest('[data-360video]') || b.parentNode;
      if (wrap.getAttribute('data-live')) return;
      wrap.setAttribute('data-live', '1');
      wrap.classList.add('is-live');

      var cfg = CFG.video360 || {};
      var vid = doc.createElement('video');
      vid.src = cfg.src; vid.crossOrigin = 'anonymous';
      vid.loop = true; vid.muted = true; vid.playsInline = true;
      vid.setAttribute('playsinline', '');

      import(cfg.threeSrc).then(function (THREE) {
        var w = wrap.clientWidth, h = wrap.clientHeight;
        var cam = new THREE.PerspectiveCamera(72, w / h, 1, 1100);
        cam.layers.enable(1);
        var scene = new THREE.Scene();
        var geo = new THREE.SphereGeometry(500, 60, 40); geo.scale(-1, 1, 1);
        var tex = new THREE.VideoTexture(vid); tex.colorSpace = THREE.SRGBColorSpace;
        scene.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: tex })));
        var r = new THREE.WebGLRenderer({ antialias: true });
        r.setPixelRatio(win.devicePixelRatio); r.setSize(w, h);
        r.domElement.className = 'v360__canvas';
        wrap.appendChild(r.domElement);

        var lon = 0, lat = 0, down = false, px = 0, py = 0, pl = 0, pt = 0;
        on(r.domElement, 'pointerdown', function (ev) { down = true; px = ev.clientX; py = ev.clientY; pl = lon; pt = lat; });
        on(win, 'pointermove', function (ev) {
          if (!down) return;
          lon = (px - ev.clientX) * 0.16 + pl;
          lat = (ev.clientY - py) * 0.16 + pt;
        });
        on(win, 'pointerup', function () { down = false; });

        (function loop() {
          win.requestAnimationFrame(loop);
          lat = Math.max(-85, Math.min(85, lat));
          var phi = THREE.MathUtils.degToRad(90 - lat), th = THREE.MathUtils.degToRad(lon);
          cam.lookAt(500 * Math.sin(phi) * Math.cos(th), 500 * Math.cos(phi), 500 * Math.sin(phi) * Math.sin(th));
          r.render(scene, cam);
        })();
        vid.play().catch(function () { });
      }).catch(function () { wrap.classList.add('is-failed'); toast('360° stream unavailable offline.'); });
    });
  }

  /* ------------------------------------------------------- video player */
  function fmt(t) {
    if (!isFinite(t)) return '0:00';
    var m = Math.floor(t / 60), sec = Math.floor(t % 60);
    return m + ':' + (sec < 10 ? '0' : '') + sec;
  }

  function initPlayer() {
    $$('[data-player]').forEach(function (box) {
      var v = $('video', box);
      if (!v) return;
      var track = $('[data-track]', box), fill = $('[data-fill]', box),
          knob  = $('[data-knob]', box), time = $('[data-time]', box);

      function paint() {
        var p = v.duration ? (v.currentTime / v.duration) * 100 : 0;
        if (fill) fill.style.width = p + '%';
        if (knob) knob.style.left = p + '%';
        if (time) time.textContent = fmt(v.currentTime) + ' / ' + fmt(v.duration || 138);
      }

      $$('[data-pp]', box).forEach(function (b) {
        on(b, 'click', function () {
          if (v.paused) { v.play().catch(function () { toast('Video stream unavailable offline.'); }); }
          else v.pause();
        });
      });
      on($('[data-mute]', box), 'click', function () { v.muted = !v.muted; });
      on(track, 'click', function (e) {
        if (!v.duration) return;
        var r = track.getBoundingClientRect();
        v.currentTime = ((e.clientX - r.left) / r.width) * v.duration;
      });
      on(v, 'play',  function () { box.classList.add('is-playing'); });
      on(v, 'pause', function () { box.classList.remove('is-playing'); });
      on(v, 'timeupdate', paint);
      on(v, 'loadedmetadata', paint);
      paint();
    });
  }

  /* --------------------------------------------------------- filters / tabs */
  function initFilters() {
    on(doc, 'click', function (e) {
      var c = e.target.closest ? e.target.closest('[data-filter]') : null;
      if (!c) return;
      var group = c.closest('[data-filter-group]');
      $$('[data-filter]', group).forEach(function (x) { x.classList.remove('is-active'); });
      c.classList.add('is-active');
      var key = c.getAttribute('data-filter');
      var scope = doc.getElementById(group.getAttribute('data-filter-group'));
      if (!scope) return;
      $$('[data-cat]', scope).forEach(function (item) {
        item.hidden = key !== 'all' && item.getAttribute('data-cat').split(/\s+/).indexOf(key) < 0;
      });
    });
  }

  /* ---------------------------------------------------------- compare count */
  function initCompare() {
    function refresh() {
      var n = $$('[data-compare]:checked').length;
      $$('[data-compare-count]').forEach(function (el) {
        el.textContent = el.getAttribute('data-compare-count').replace('%d', n);
      });
    }
    on(doc, 'change', function (e) { if (e.target.matches('[data-compare]')) refresh(); });
    refresh();
  }

  /* -------------------------------------------------- inert / demo controls */
  function initInert() {
    on(doc, 'click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-inert]') : null;
      if (!b) return;
      e.preventDefault();
      toast(b.getAttribute('data-inert') || CFG.strings.inert);
    });
  }

  /* -------------------------------------------------------- routing / links */
  function initLinks() {
    on(doc, 'click', function (e) {
      var a = e.target.closest ? e.target.closest('[data-goto]') : null;
      if (!a) return;
      e.preventDefault();
      go(a.getAttribute('data-goto'));
      if (rail) rail.classList.remove('is-open');
    });
    on(win, 'popstate', function () { go(win.location.hash.slice(1) || CFG.startScreen, false); });
  }

  /* --------------------------------------------------------- image fallback */
  function initImageGuards() {
    on(doc, 'error', function (e) {
      var img = e.target;
      if (img.tagName !== 'IMG' || img.dataset.fallbackApplied) return;
      img.dataset.fallbackApplied = '1';
      img.src = 'assets/img/product/front-left.webp';
    }, true);
  }

  /* -------------------------------------------------------------- lifecycle */
  function boot() {
    stage     = $('#stage');
    screensEl = $('#screens');
    toaster   = $('#toaster');
    if (!stage) return;

    initRail(); initLinks(); initHotspots(); initThumbs();
    initViewers(); initSpin360(); initAR(); initViewerControls(); init360Video();
    initFilters(); initCompare(); initInert(); initImageGuards(); initPlayer();

    go(win.location.hash.slice(1) || CFG.startScreen || 'listing', false);
    doc.documentElement.classList.add('is-ready');
  }

  if (doc.readyState === 'loading') on(doc, 'DOMContentLoaded', boot);
  else boot();

  /* Minimal, frozen public surface. Nothing else is reachable. */
  win.STD = Object.freeze({ go: go, toast: toast, version: '1.0.0' });

})(window, document);
