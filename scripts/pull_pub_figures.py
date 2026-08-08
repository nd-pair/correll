#!/usr/bin/env python3
"""Automatically extract a representative figure for each publication from its open-access PDF.

For every paper that does NOT already have a hand-curated thumbnail (data/pub_images.json),
this downloads the OA PDF (arXiv links resolved to the direct PDF), opens page 1, and picks the
"first image on the top right" — the largest embedded raster whose position is highest/rightmost,
which is almost always the teaser figure. The image is resized into assets/pubs/auto/ and recorded
in data/pub_figures.json (normalized-title -> path). The site prefers curated images and falls
back to these. Paywalled papers (no OA PDF) are simply skipped.

Deps: pymupdf, pillow.  Usage: python3 scripts/pull_pub_figures.py [--limit N]
"""
import io, json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBS = os.path.join(ROOT, "data", "publications.json")
CURATED = os.path.join(ROOT, "data", "pub_images.json")
OUT = os.path.join(ROOT, "data", "pub_figures.json")
FIG_DIR = os.path.join(ROOT, "assets", "pubs", "auto")
MAXPX = 480
MIN_SIDE = 150            # ignore small logos / icons / equations
MIN_AREA = 240 * 240
MAX_ASPECT = 6.0
UA = {"User-Agent": "Mozilla/5.0 (correll-site figure extraction)"}


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")[:60] or "paper"


def pdf_url(w):
    """Resolve a work's OA link to a directly-downloadable PDF url (arXiv handled explicitly)."""
    raw = w.get("pdf") or ""
    m = re.search(r"arxiv[.:/](\d{4}\.\d{4,5})(v\d+)?", raw, re.I) or \
        re.search(r"abs/(\d{4}\.\d{4,5})", raw, re.I)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}"
    if raw.lower().endswith(".pdf") or "/pdf/" in raw.lower():
        return raw
    return raw or None


def download(url, cap=35 * 1024 * 1024):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        ctype = (r.headers.get("Content-Type") or "").lower()
        data = r.read(cap + 1)
    if len(data) > cap:
        raise ValueError("pdf too large")
    if b"%PDF" not in data[:1024] and "pdf" not in ctype:
        raise ValueError(f"not a pdf ({ctype})")
    return data


def best_figure(pdf_bytes):
    """Return PNG bytes of the top-right teaser image on page 1, or None.

    Uses get_image_info(xrefs=True) so images placed inside XObject forms (the norm for
    arXiv teaser figures) are still found, with a page-coordinate bbox for positioning.
    """
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.page_count == 0:
            return None
        page = doc[0]
        pw = page.rect.width or 1
        cands = []
        for d in page.get_image_info(xrefs=True):
            w, h = d.get("width", 0), d.get("height", 0)
            if min(w, h) < MIN_SIDE or w * h < MIN_AREA:
                continue
            if max(w, h) / max(1, min(w, h)) > MAX_ASPECT:
                continue
            x0, y0, x1, y1 = d["bbox"]
            if (x1 - x0) < 40 or (y1 - y0) < 40:      # degenerate placement
                continue
            # "top right": smaller y is higher; larger x is more to the right.
            score = y0 - (x1 / pw) * 40
            cands.append((score, pymupdf.Rect(d["bbox"])))
        if not cands:
            return None
        cands.sort(key=lambda c: c[0])
        # Render the page region where the figure sits, so soft-masks/transparency are applied
        # exactly as displayed (on the page's white background) — not the raw, unmasked xref.
        clip = cands[0][1] & page.rect
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def save_resized(png_bytes, dest):
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))  # flatten transparency onto white
        im = Image.alpha_composite(bg, im)
    im = im.convert("RGB")
    im.thumbnail((MAXPX, MAXPX))
    im.save(dest, "PNG")


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    os.makedirs(FIG_DIR, exist_ok=True)
    pubs = json.load(open(PUBS))
    curated = set(json.load(open(CURATED)).get("images", {})) if os.path.exists(CURATED) else set()

    works = [it for g in pubs.get("years", []) for it in g.get("items", [])]
    todo = [w for w in works if norm(w["title"]) not in curated and w.get("pdf")]
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} papers to try (of {len(works)}; {len(curated)} already curated)", file=sys.stderr)

    figures = {}
    ok = fail = 0
    for w in todo:
        url = pdf_url(w)
        if not url:
            continue
        time.sleep(0.6)  # be polite to arXiv / OA hosts, avoid rate-limit misses
        try:
            png = best_figure(download(url))
            if not png:
                print(f"  --  no figure: {w['title'][:56]}", file=sys.stderr)
                fail += 1
                continue
            dest = os.path.join(FIG_DIR, slug(w["title"]) + ".png")
            save_resized(png, dest)
            figures[norm(w["title"])] = os.path.relpath(dest, ROOT)
            ok += 1
            print(f"  ok  {os.path.basename(dest)}  <-  {w['title'][:52]}", file=sys.stderr)
        except Exception as e:
            fail += 1
            print(f"  FAIL {w['title'][:52]}: {e}", file=sys.stderr)

    out = {"source": "open-access PDFs (page-1 teaser figure)", "count": len(figures), "images": figures}
    json.dump(out, open(OUT, "w"), indent=2)
    print(f"extracted {ok} figures, {fail} misses -> {OUT}")


if __name__ == "__main__":
    main()
