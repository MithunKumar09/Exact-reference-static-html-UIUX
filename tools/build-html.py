"""
STANDARD · page builder — assembles index.html from the parts/ folder
==============================================================================
index.html is a build output. The thing to edit is parts/*.html.

    python tools/build-html.py            # parts/  ->  index.html
    python tools/build-html.py --check    # exit 1 if index.html is stale
    python tools/build-html.py --force    # overwrite hand-edits to index.html

The page is one hash-routed document: every screen shares a DOM with the rail,
the topbar and the router in assets/js/core.min.js, so the parts cannot be
separate pages. They are concatenated verbatim — no templating, no markers, no
rewriting — which keeps index.html byte-for-byte what it has always been and
keeps it openable straight off the filesystem.

Order is the PARTS list below, not the directory listing. Adding a screen means
adding its file here.
"""

import hashlib, sys, difflib
from pathlib import Path

#  Part names and diff output carry em dashes and degree signs; a legacy
#  Windows console would otherwise abort the build on the print, not the build.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT  = Path(__file__).resolve().parent.parent
PARTS_DIR = ROOT / "parts"
OUT   = ROOT / "index.html"
STAMP = PARTS_DIR / ".last-build.sha256"

#  Concatenated in exactly this order.
PARTS = [
    "01-document-head.html",          # doctype, <head>, stylesheets, <body>
    "02-icon-sprite.html",            # <symbol id="i-*"> sprite
    "03-app-chrome.html",             # stage, topbar, tabnav, rail
    "04-listing-overview.html",       # 01 Listing · 02 Overview
    "05-view-360.html",               # 03 360 View
    "06-diagrams.html",               # 04 Exploded · 05 Schematic · 06 Drawing
    "07-detail-screens.html",         # 07 Exterior … 11 Features
    "08-content-screens.html",        # 12 Specs · 13 Videos · 14 Gallery · 15 Brochure
    "09-compare-enquire-footer.html", # 16 Compare · 17 Variants · 18 Enquire, footer
]


def read_parts():
    """Concatenate the parts in PARTS order, as bytes. Missing file = hard stop."""
    missing = [p for p in PARTS if not (PARTS_DIR / p).is_file()]
    if missing:
        sys.exit("build-html: missing part(s): " + ", ".join(missing))

    stray = sorted(
        f.name for f in PARTS_DIR.glob("*.html") if f.name not in PARTS
    )
    if stray:
        print("build-html: warning — not in PARTS, so not built in: "
              + ", ".join(stray), file=sys.stderr)

    return b"".join((PARTS_DIR / p).read_bytes() for p in PARTS)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv):
    check = "--check" in argv
    force = "--force" in argv

    built = read_parts()
    current = OUT.read_bytes() if OUT.exists() else None

    if check:
        if current == built:
            print(f"build-html: index.html is up to date ({len(built):,} bytes)")
            return 0
        print("build-html: index.html is STALE — run python tools/build-html.py",
              file=sys.stderr)
        return 1

    if current == built:
        print(f"build-html: index.html already current ({len(built):,} bytes, "
              f"{len(PARTS)} parts)")
        STAMP.write_text(sha(built) + "\n", encoding="utf-8")
        return 0

    #  index.html differs from the parts. That is normal after editing a part,
    #  but it also happens when someone edited index.html directly — in which
    #  case building would silently throw that edit away. Tell them apart with
    #  the hash written by the previous build.
    if current is not None and not force:
        last = STAMP.read_text(encoding="utf-8").strip() if STAMP.exists() else None
        if last is not None and sha(current) != last:
            print("build-html: REFUSING to overwrite — index.html has been edited "
                  "directly since the last build.\n"
                  "Those edits belong in parts/; move them there, or re-run with "
                  "--force to discard them.\n"
                  "What would be lost:\n", file=sys.stderr)
            diff = difflib.unified_diff(
                current.decode("utf-8").splitlines(),
                built.decode("utf-8").splitlines(),
                fromfile="index.html (on disk)", tofile="index.html (from parts)",
                lineterm="", n=1,
            )
            for i, line in enumerate(diff):
                if i >= 60:
                    print("  … diff truncated", file=sys.stderr)
                    break
                print("  " + line, file=sys.stderr)
            return 1

    OUT.write_bytes(built)
    STAMP.write_text(sha(built) + "\n", encoding="utf-8")
    print(f"build-html: wrote index.html — {len(PARTS)} parts, "
          f"{built.count(bytes([10])):,} lines, {len(built):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
