#!/usr/bin/env python3
"""Automatically extract a representative figure for each publication from its open-access PDF.

For every paper that does NOT already have a hand-curated thumbnail (data/pub_images.json),
this downloads the OA PDF (arXiv links resolved to the direct PDF) and gathers the candidate
teaser figures from its first pages. If GitHub Models is available, a vision model chooses the
most representative one; otherwise a "top-right, earliest page" heuristic is used. The chosen
figure is resized into assets/pubs/auto/ and recorded in data/pub_figures.json (normalized-title
-> path). The site prefers curated images and falls back to these. Paywalled papers are skipped.

Deps: pymupdf, pillow (+ optional GitHub Models). Usage: python3 scripts/pull_pub_figures.py [--limit N]
"""
import io, json, os, re, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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


def candidate_figures(pdf_bytes, max_n=4):
    """Return a list of PNG bytes for the most likely teaser figures, best-first.

    Scans the first two pages, keeps sufficiently large rasters, and orders them by a
    "top-right, earlier page" heuristic. Each figure is RENDERED from its page region (so
    soft-masks/transparency show as displayed, on white) rather than extracting the raw xref
    (which loses the mask and comes out black). Uses get_image_info(xrefs=True) so images inside
    XObject forms — the norm for arXiv teaser figures — are still found with a page bbox.
    """
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        cands = []
        for pno in range(min(2, doc.page_count)):
            page = doc[pno]
            pw = page.rect.width or 1
            for d in page.get_image_info(xrefs=True):
                w, h = d.get("width", 0), d.get("height", 0)
                if min(w, h) < MIN_SIDE or w * h < MIN_AREA:
                    continue
                if max(w, h) / max(1, min(w, h)) > MAX_ASPECT:
                    continue
                x0, y0, x1, y1 = d["bbox"]
                if (x1 - x0) < 40 or (y1 - y0) < 40:
                    continue
                score = pno * 100000 + y0 - (x1 / pw) * 40   # earlier page, then top-right
                cands.append((score, pno, pymupdf.Rect(d["bbox"])))
        cands.sort(key=lambda c: c[0])
        pngs = []
        for _, pno, rect in cands[:max_n]:
            page = doc[pno]
            clip = rect & page.rect
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip, alpha=False)
            pngs.append(pix.tobytes("png"))
        return pngs
    finally:
        doc.close()


def choose_with_llm(title, pngs):
    """Ask a vision model which candidate best represents the paper; return an index or 0."""
    import llm
    if not llm.available() or len(pngs) < 2:
        return 0
    prompt = (f'Choose the single best "teaser" image to represent the paper "{title}" in a '
              f"publication list. Prefer a figure showing the robot, hardware, system overview, or "
              f"method pipeline; avoid plain line plots, bar charts, tables, or equations. "
              f"There are {len(pngs)} candidates, numbered in order. Reply with ONLY the number.")
    try:
        n = llm.choose_image(prompt, pngs)
        if n and 1 <= n <= len(pngs):
            return n - 1
    except (llm.Unavailable, llm.RateLimited) as e:
        print(f"    (llm pick skipped: {e})", file=sys.stderr)
    return 0


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
    refresh = "--refresh" in sys.argv  # re-process every paper, ignoring the existing figure cache
    os.makedirs(FIG_DIR, exist_ok=True)
    pubs = json.load(open(PUBS))
    curated = set(json.load(open(CURATED)).get("images", {})) if os.path.exists(CURATED) else set()
    # Incremental by default: keep figures already extracted (and their files), only work new
    # papers. With --refresh, start empty so every OA paper is re-extracted and re-picked.
    figures = {}
    if os.path.exists(OUT) and not refresh:
        for k, rel in json.load(open(OUT)).get("images", {}).items():
            if os.path.exists(os.path.join(ROOT, rel)):
                figures[k] = rel

    works = [it for g in pubs.get("years", []) for it in g.get("items", [])]
    todo = [w for w in works if norm(w["title"]) not in curated
            and norm(w["title"]) not in figures and w.get("pdf")]
    if limit:
        todo = todo[:limit]
    import llm
    picker = "vision LLM" if llm.available() else "heuristic"
    print(f"{len(todo)} papers to try (of {len(works)}; {len(curated)} curated, "
          f"{len(figures)} already auto). Figure pick: {picker}.", file=sys.stderr)

    ok = fail = 0
    for w in todo:
        url = pdf_url(w)
        if not url:
            continue
        time.sleep(0.6)  # be polite to arXiv / OA hosts, avoid rate-limit misses
        try:
            pngs = candidate_figures(download(url))
            if not pngs:
                print(f"  --  no figure: {w['title'][:56]}", file=sys.stderr)
                fail += 1
                continue
            idx = choose_with_llm(w["title"], pngs)
            dest = os.path.join(FIG_DIR, slug(w["title"]) + ".png")
            save_resized(pngs[idx], dest)
            figures[norm(w["title"])] = os.path.relpath(dest, ROOT)
            ok += 1
            tag = f"#{idx+1}/{len(pngs)}" if len(pngs) > 1 else "only"
            print(f"  ok  {os.path.basename(dest)} ({tag})  <-  {w['title'][:48]}", file=sys.stderr)
        except Exception as e:
            fail += 1
            print(f"  FAIL {w['title'][:52]}: {e}", file=sys.stderr)

    out = {"source": "open-access PDFs (teaser figure, LLM- or heuristic-selected)",
           "count": len(figures), "images": figures}
    json.dump(out, open(OUT, "w"), indent=2)
    print(f"extracted {ok} figures, {fail} misses -> {OUT}")


if __name__ == "__main__":
    main()
