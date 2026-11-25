#!/usr/bin/env python3
"""Build this site's pages. The work lives in the shared theme.

Kept as a shim so every existing command, workflow and note that says
`python3 scripts/build_site.py` still means what it meant before the chrome
moved to nd-pair/pair-theme. What belongs to this site -- pages/, data/,
render.py, styles.css and site.json -- stays here.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
THEME = os.environ.get("THEME_DIR") or os.path.join(ROOT, ".theme")

sys.path.insert(0, HERE)                       # this repo's render.py
sys.path.insert(0, os.path.join(THEME, "scripts"))
try:
    from pair_theme import build
except ImportError:
    sys.exit("No theme at %s -- run scripts/fetch_theme.sh (or set THEME_DIR)." % THEME)

if __name__ == "__main__":
    build.main(root=ROOT, theme=THEME)
