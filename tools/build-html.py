"""
STANDARD · single-file packer — index.html + parts/  ->  standalone.html
==============================================================================
index.html is NOT generated: it is the shell you edit, and at runtime it fetches
parts/*.html and assembles them in the browser. Nothing here is needed to work
on the site — edit a part, reload the page.

This script exists for the one thing fetch() cannot do: open the demo straight
off the filesystem (double-click, USB stick, e-mail, the zip). It inlines the
parts into the shell and writes a self-contained standalone.html.

    python tools/build-html.py            # index.html + parts/  ->  standalone.html
    python tools/build-html.py --check    # exit 1 if standalone.html is stale

The part list is NOT duplicated here — it is read out of the PARTS array in
index.html, so the shell stays the single registry. The parts are concatenated
verbatim, in that order, with no templating and no rewriting: they are fragments
that only balance once joined (parts/03 opens .stage, parts/09 closes it).
"""

import re, sys
from pathlib import Path

#  Part names and diff output carry em dashes and degree signs; a legacy
#  Windows console would otherwise abort the build on the print, not the build.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT      = Path(__file__).resolve().parent.parent
PARTS_DIR = ROOT / "parts"
SHELL     = ROOT / "index.html"
OUT       = ROOT / "standalone.html"

BEGIN = "<!-- parts:begin"
END   = "<!-- parts:end -->"
CRLF  = "\r\n"


def read_shell():
    """index.html, plus the bounds of the loader block the parts replace."""
    text = SHELL.read_bytes().decode("utf-8")
    try:
        head = text.index(BEGIN)
        tail = text.index(END) + len(END)
    except ValueError:
        sys.exit(f"build-html: {SHELL.name} has no {BEGIN} … {END} block to replace.")
    return text, head, tail


def part_list(text):
    """The PARTS array in the shell's loader is the one registry of pieces."""
    m = re.search(r"var PARTS\s*=\s*\[(.*?)\]\s*;", text, re.S)
    if not m:
        sys.exit("build-html: could not find the PARTS array in index.html.")
    names = re.findall(r"'([^']+)'", m.group(1))
    if not names:
        sys.exit("build-html: the PARTS array in index.html is empty.")
    return names


def runtime_src(text):
    m = re.search(r"var RUNTIME\s*=\s*'([^']+)'", text)
    return m.group(1) if m else "assets/js/core.min.js"


def build():
    text, head, tail = read_shell()
    names = part_list(text)

    missing = [n for n in names if not (ROOT / n).is_file()]
    if missing:
        sys.exit("build-html: missing part(s): " + ", ".join(missing))

    listed = {n.split("/")[-1] for n in names}
    stray = sorted(f.name for f in PARTS_DIR.glob("*.html") if f.name not in listed)
    if stray:
        print("build-html: warning — not in the PARTS array, so not inlined: "
              + ", ".join(stray), file=sys.stderr)

    body = "".join((ROOT / n).read_bytes().decode("utf-8") for n in names)
    runtime = (CRLF + "<!-- Runtime. Source lives in assets/js/_source/core.js — "
               "rebuild with terser. -->" + CRLF
               + f'<script src="{runtime_src(text)}" defer></script>')

    return (text[:head] + body.rstrip("\r\n") + runtime + text[tail:]).encode("utf-8"), names


def main(argv):
    built, names = build()
    current = OUT.read_bytes() if OUT.exists() else None

    if "--check" in argv:
        if current == built:
            print(f"build-html: standalone.html is up to date ({len(built):,} bytes)")
            return 0
        print("build-html: standalone.html is STALE — run python tools/build-html.py",
              file=sys.stderr)
        return 1

    if current == built:
        print(f"build-html: standalone.html already current ({len(built):,} bytes, "
              f"{len(names)} parts)")
        return 0

    OUT.write_bytes(built)
    print(f"build-html: wrote standalone.html — {len(names)} parts, "
          f"{built.count(bytes([10])):,} lines, {len(built):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
