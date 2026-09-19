Brand mark slot
---------------
Put the STANDARD logo PNG here (transparent background, square-ish, >= 144 px)
and point the slot at it:

  parts/03-app-chrome.html            <img class="brand__logoImg" src="assets/img/brand/logo-mark.png" ...>
  parts/09-compare-enquire-footer.html  (same line, footer lockup)

Then rebuild:  python tools/build-html.py

Leave src empty, or delete the file, and the header/footer show the image
placeholder instead.
