#!/usr/bin/env python3
"""Automatically extract a representative figure for each publication from its open-access PDF.

For every paper that does NOT already have a hand-curated thumbnail (data/pub_images.json),
this downloads the OA PDF (arXiv links resolved to the direct PDF) and gathers the candidate
teaser figures from its first pages. If GitHub Models is available, a vision model chooses the
most representative one; otherwise a "top-right, earliest page" heuristic is used. The chosen
figure is resized to WebP in assets/pubs/auto/ and recorded in data/pub_figures.json (normalized-title
-> path). When a PDF yields no usable figure, its first page is rendered instead, so any paper whose
PDF downloads gets a thumbnail. The site prefers curated images and falls back to these. Paywalled
papers, and papers with no open-access PDF at all, are skipped.

Deps: pymupdf, pillow (+ optional Anthropic API key).
Usage: python3 scripts/pull_pub_figures.py [--limit N] [--upgrade] [--refresh]
  --upgrade  re-try only the papers currently showing a first-page render
  --refresh  re-process every paper from scratch
"""
import hashlib, io, json, os, re, sys, time
import urllib.error, urllib.parse, urllib.request

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
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
      "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9"}
RETRY_CODES = (429, 500, 502, 503, 504)

# Repositories and publishers advertise the real PDF behind a landing page with a
# citation_pdf_url meta tag (the Highwire convention EPFL Infoscience, DSpace, CU
# Scholar, IEEE, Springer and others all emit). Attribute order varies, so match both.
PDF_META = re.compile(rb"""<meta[^>]+?name=["']citation_pdf_url["'][^>]+?content=["']([^"']+)["']""", re.I)
PDF_META_REV = re.compile(rb"""<meta[^>]+?content=["']([^"']+)["'][^>]+?name=["']citation_pdf_url["']""", re.I)
PDF_HREF = re.compile(rb"""href=["']([^"']+?\.pdf(?:\?[^"']*)?)["']""", re.I)


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")[:60] or "paper"


EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def pdf_urls(w):
    """Every candidate PDF url for a work, best first (arXiv links resolved to the file)."""
    out = []
    for raw in (w.get("pdfs") or [w.get("pdf")]):
        if not raw:
            continue
        m = re.search(r"arxiv[.:/](\d{4}\.\d{4,5})(v\d+)?", raw, re.I) or \
            re.search(r"abs/(\d{4}\.\d{4,5})", raw, re.I)
        url = f"https://arxiv.org/pdf/{m.group(1)}" if m else raw
        if url not in out:
            out.append(url)
    return out


def europepmc_pdf(doi):
    """Europe PMC's copy of an open-access paper, if it holds one.

    Publisher sites are the most bot-hostile place to fetch from: Nature, Elsevier and
    IOP hand a scripted client an HTML interstitial or a 403 even for papers that are
    fully open access. Europe PMC mirrors those deposits and serves them to anyone, so
    it is worth asking once the publisher has refused.
    """
    if not doi:
        return None
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi).strip()
    q = urllib.parse.urlencode({"query": f'DOI:"{doi}"', "format": "json",
                                "pageSize": 1, "resultType": "lite"})
    try:
        req = urllib.request.Request(f"{EPMC}?{q}", headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
    except Exception:
        return None
    for rec in ((d.get("resultList") or {}).get("result") or []):
        if rec.get("pmcid") and rec.get("inEPMC") == "Y" and rec.get("hasPDF") == "Y":
            return f"https://europepmc.org/articles/{rec['pmcid']}?pdf=render"
    return None


def fetch_pdf(w):
    """Download a work's PDF from the first source that will give it up.

    Returns (bytes, url). Raises ValueError listing what each source said if none will.
    """
    tried = []
    for url in pdf_urls(w):
        time.sleep(0.6)  # be polite to arXiv / OA hosts, avoid rate-limit misses
        try:
            return download(url), url
        except Exception as e:
            tried.append(f"{urllib.parse.urlparse(url).netloc or url}: {e}")
    alt = europepmc_pdf(w.get("doi"))
    if alt:
        time.sleep(0.6)
        try:
            return download(alt), alt
        except Exception as e:
            tried.append(f"europepmc: {e}")
    raise ValueError("; ".join(tried) or "no open-access pdf")


def pdf_from_landing(html, base):
    """Find the PDF behind an HTML landing page, or None."""
    for pat in (PDF_META, PDF_META_REV):
        m = pat.search(html)
        if m:
            return urllib.parse.urljoin(base, m.group(1).decode("utf-8", "replace"))
    m = PDF_HREF.search(html)
    if m:
        return urllib.parse.urljoin(base, m.group(1).decode("utf-8", "replace"))
    return None


def download(url, cap=35 * 1024 * 1024, _followed=False):
    """Fetch a PDF.

    Many of the open-access links OpenAlex gives are landing pages rather than files,
    so an HTML response is followed once to the PDF it advertises. Transient server
    errors get one retry; a hard 403 is the publisher refusing us and is left alone.
    """
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                final = r.geturl()
                ctype = (r.headers.get("Content-Type") or "").lower()
                data = r.read(cap + 1)
            break
        except urllib.error.HTTPError as e:
            if e.code in RETRY_CODES and attempt == 1:
                time.sleep(3)
                continue
            raise
    if len(data) > cap:
        raise ValueError("pdf too large")
    if b"%PDF" in data[:1024] or "pdf" in ctype:
        return data
    if not _followed:
        target = pdf_from_landing(data, final)
        if target and target != url:
            time.sleep(0.6)
            return download(target, cap, _followed=True)
    raise ValueError(f"not a pdf ({ctype})")


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


def first_page_png(pdf_bytes):
    """Render page 1 of the PDF as a PNG, trimmed to its content.

    The fallback when no teaser figure can be found: a picture of the paper's own
    first page is a far more useful thumbnail than an empty tile, and it is always
    available once the PDF itself downloads. Margins are cropped away so the text
    block fills the thumbnail instead of floating in white space.
    """
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[0]
        content = None
        for rect in ([pymupdf.Rect(b[:4]) for b in page.get_text("blocks")]
                     + [pymupdf.Rect(d["bbox"]) for d in page.get_image_info()]):
            if rect.is_empty or rect.is_infinite:
                continue
            content = rect if content is None else (content | rect)
        if content is not None:
            content += (-8, -8, 8, 8)              # a little breathing room
            clip = content & page.rect
        else:
            clip = page.rect
        if clip.width < 40 or clip.height < 40:    # nothing sensible to crop to
            clip = page.rect
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


CAPTION = re.compile(r"^\s*(fig(?:ure)?\.?\s*(\d+)|table\s*\d+)", re.I)


def caption_figures(pdf_bytes, max_n=3, pages=4):
    """Find figures by their captions, and return them best-first as PNG bytes.

    The raster scan above only sees bitmap images. Older papers draw their figures as
    vectors — EPS line art, TikZ, plotting output — which carry no raster at all, so
    nothing is found and the paper falls through to a picture of its first page. A
    caption is the reliable anchor for those: the figure occupies the gap between a
    caption and the text above it, in the caption's own column. The crop is then
    tightened onto the drawings and images actually inside that gap, so a one-line
    caption does not yield a narrow slice of a wide figure, and a gap containing no
    ink at all is rejected rather than passed off as a figure.
    """
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        cands = []
        for pno in range(min(pages, doc.page_count)):
            page = doc[pno]
            blocks = [b for b in page.get_text("blocks") if (b[4] or "").strip()]
            blocks.sort(key=lambda b: b[1])
            ink = [pymupdf.Rect(d["rect"]) for d in page.get_drawings()]
            ink += [pymupdf.Rect(d["bbox"]) for d in page.get_image_info(xrefs=True)]
            ink = [r for r in ink if r.get_area() > 400]
            for i, b in enumerate(blocks):
                m = CAPTION.match(b[4])
                if not m or m.group(0).lower().startswith("table"):
                    continue
                x0, y0, x1, _ = b[:4]
                # The caption's column: every text block that shares its horizontal span.
                # This keeps a short one-line caption from cropping a wide figure to its
                # own width, without reaching across the gutter into the other column.
                cx0, cx1 = x0, x1
                for other in blocks:
                    if min(cx1, other[2]) - max(cx0, other[0]) > 0:
                        cx0, cx1 = min(cx0, other[0]), max(cx1, other[2])
                top = page.rect.y0
                for prev in blocks[:i]:
                    if prev[3] <= y0 and min(cx1, prev[2]) - max(cx0, prev[0]) > 0:
                        top = max(top, prev[3])
                band = pymupdf.Rect(cx0 - 6, top + 2, cx1 + 6, y0 - 2) & page.rect
                if band.height < 60 or band.width < 60:
                    continue
                inside = [r & band for r in ink if (r & band).get_area() > 0.4 * r.get_area()]
                if not inside:
                    continue
                rect = inside[0]
                for r in inside[1:]:
                    rect = rect | r
                rect = (rect + (-4, -4, 4, 4)) & band
                if rect.height < 50 or rect.width < 50:
                    continue
                num = int(m.group(2)) if m.group(2) else 99
                cands.append((pno * 1000 + num, pno, rect))
        cands.sort(key=lambda c: c[0])
        out = []
        for _, pno, rect in cands[:max_n]:
            pix = doc[pno].get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=rect, alpha=False)
            out.append(pix.tobytes("png"))
        return out
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
    im.save(dest, "WEBP", quality=78, method=6)


def adopt_orphans(figures, works, curated):
    """Take ownership of renders sitting in FIG_DIR that the index does not mention.

    Files and index can drift apart — a run killed before an image was recorded, a
    retry that failed after its predecessor had been forgotten. The filename is
    slug(title), so the mapping can always be rebuilt; without this the paper shows a
    neutral tile even though its picture is right there on disk, and the next run
    downloads the PDF all over again.
    """
    if not os.path.isdir(FIG_DIR):
        return 0
    referenced = {os.path.basename(rel) for rel in figures.values()}
    by_slug = {}
    for w in works:
        by_slug.setdefault(slug(w["title"]), []).append(w["title"])
    adopted = 0
    for fn in sorted(os.listdir(FIG_DIR)):
        if not fn.endswith(".webp") or fn in referenced:
            continue
        stem = re.sub(r"-[0-9a-f]{6}$", "", fn[:-5])   # strip a collision suffix
        for title in by_slug.get(stem, []):
            key = norm(title)
            if key in curated or key in figures:
                continue
            figures[key] = os.path.relpath(os.path.join(FIG_DIR, fn), ROOT)
            adopted += 1
    return adopted


def write_index(figures, page_renders, path=None):
    """Persist the title -> image index.

    Written after every paper, not once at the end: a run that is interrupted part
    way (or killed by a flaky download) would otherwise leave its images on disk with
    nothing pointing at them, and the next run would not know they exist.
    """
    out = {"source": "open-access PDFs (teaser figure, LLM- or heuristic-selected)",
           "count": len(figures), "images": figures,
           "first_page": sorted(page_renders & set(figures))}
    tmp = (path or OUT) + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(out, fh, indent=2)
    os.replace(tmp, path or OUT)   # atomic: never leave a half-written index behind


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    refresh = "--refresh" in sys.argv  # re-process every paper, ignoring the existing figure cache
    upgrade = "--upgrade" in sys.argv  # re-try only the papers that fell back to a first-page render
    os.makedirs(FIG_DIR, exist_ok=True)
    pubs = json.load(open(PUBS))
    curated = set(json.load(open(CURATED)).get("images", {})) if os.path.exists(CURATED) else set()
    # Incremental by default: keep figures already extracted (and their files), only work new
    # papers. With --refresh, start empty so every OA paper is re-extracted and re-picked.
    figures, page_renders = {}, set()
    if os.path.exists(OUT) and not refresh:
        cached = json.load(open(OUT))
        for k, rel in cached.get("images", {}).items():
            if os.path.exists(os.path.join(ROOT, rel)):
                figures[k] = rel
        page_renders = {k for k in cached.get("first_page", []) if k in figures}
    # Re-try only the papers currently showing a picture of their first page, to see
    # whether an improved scan can find them a real figure. Their existing entries stay
    # in place: a retry that fails must leave the paper with the picture it already had.
    retry = set(page_renders) if upgrade else set()

    works = [it for g in pubs.get("years", []) for it in g.get("items", [])]
    adopted = adopt_orphans(figures, works, curated)
    if adopted:
        print(f"adopted {adopted} render(s) already on disk but missing from the index",
              file=sys.stderr)
    todo = [w for w in works
            if norm(w["title"]) not in curated
            and (norm(w["title"]) not in figures or norm(w["title"]) in retry)
            and (w.get("pdfs") or w.get("pdf") or w.get("doi"))]
    if limit:
        todo = todo[:limit]
    import llm
    picker = "vision LLM" if llm.available() else "heuristic"
    print(f"{len(todo)} papers to try (of {len(works)}; {len(curated)} curated, "
          f"{len(figures)} already auto). Figure pick: {picker}.", file=sys.stderr)

    # Two papers can slug to the same filename (a preprint and its published version,
    # say). Remember who owns each destination so the second does not overwrite the first.
    owner = {os.path.join(ROOT, rel): key for key, rel in figures.items()}

    ok = pages = fail = 0
    for w in todo:
        try:
            pdf, used = fetch_pdf(w)
            if urllib.parse.urlparse(used).netloc.endswith("europepmc.org"):
                print(f"  via  europepmc  <-  {w['title'][:48]}", file=sys.stderr)
            pngs = candidate_figures(pdf) or caption_figures(pdf)
            key = norm(w["title"])
            dest = os.path.join(FIG_DIR, slug(w["title"]) + ".webp")
            if owner.get(dest, key) != key:
                dest = os.path.join(
                    FIG_DIR,
                    f"{slug(w['title'])}-{hashlib.sha1(key.encode()).hexdigest()[:6]}.webp")
            owner[dest] = key
            if pngs:
                idx = choose_with_llm(w["title"], pngs)
                save_resized(pngs[idx], dest)
                ok += 1
                tag = f"#{idx+1}/{len(pngs)}" if len(pngs) > 1 else "only"
                print(f"  ok   {os.path.basename(dest)} ({tag})  <-  {w['title'][:48]}",
                      file=sys.stderr)
                page_renders.discard(key)
            else:
                # No usable figure — fall back to a picture of the first page.
                save_resized(first_page_png(pdf), dest)
                page_renders.add(key)
                pages += 1
                print(f"  page {os.path.basename(dest)} (first page)  <-  {w['title'][:48]}",
                      file=sys.stderr)
            figures[key] = os.path.relpath(dest, ROOT)
            write_index(figures, page_renders)
        except Exception as e:
            fail += 1
            print(f"  FAIL {w['title'][:52]}: {e}", file=sys.stderr)

    write_index(figures, page_renders)
    print(f"extracted {ok} figures + {pages} first-page renders, {fail} misses -> {OUT}")


if __name__ == "__main__":
    main()
