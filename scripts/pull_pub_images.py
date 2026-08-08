#!/usr/bin/env python3
"""Extract each publication's thumbnail (the little picture in front of each paper) from the
source lab site's AJAX-rendered "All papers" view, download the token-free original, resize it,
and write data/pub_images.json mapping normalized-title -> local image path.

The list is rendered client-side (Drupal Views AJAX), so a headless browser is required —
plain HTTP returns an empty shell. Run in CI via .github/workflows/refresh.yml.

Deps: playwright (+ chromium), pillow.  Usage: python3 scripts/pull_pub_images.py
"""
import difflib, json, os, re, sys, urllib.request

SRC = "https://www.colorado.edu/lab/correll/all-papers"
ORIGIN = "https://www.colorado.edu"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB_DIR = os.path.join(ROOT, "assets", "pubs")
PUBS = os.path.join(ROOT, "data", "publications.json")
OUT = os.path.join(ROOT, "data", "pub_images.json")
MAXPX = 480


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def load_openalex_titles():
    """Normalized titles from publications.json, so images key on the SAME title the site uses."""
    try:
        pubs = json.load(open(PUBS))
    except Exception:
        return []
    return [norm(it["title"]) for g in pubs.get("years", []) for it in g.get("items", [])]


def match_title(cu_title, oa_titles):
    """Map a source-site title to its OpenAlex equivalent (they occasionally differ in subtitle)."""
    n = norm(cu_title)
    if not oa_titles or n in oa_titles:
        return n
    hit = difflib.get_close_matches(n, oa_titles, n=1, cutoff=0.6)
    return hit[0] if hit else n


def to_original(path):
    """Strip the Drupal image-style prefix so we fetch the token-free original file.
    /lab/correll/sites/default/files/styles/<style>/public/<x> -> /lab/correll/sites/default/files/<x>"""
    return re.sub(r"(/sites/default/files)/styles/[^/]+/public/", r"\1/", path)


def extract_rows():
    from playwright.sync_api import sync_playwright
    js = """() => {
      const links=[...document.querySelectorAll('a[href*="/lab/correll/20"]')]
        .filter(a=>a.textContent.trim().length>15);
      function rowOf(a){let e=a;for(let i=0;i<6;i++){if(!e.parentElement)break;e=e.parentElement;
        if(e.querySelector('img'))return e;}return a.closest('div');}
      const seen=new Set(); const out=[];
      for(const a of links){const k=a.getAttribute('href'); if(seen.has(k))continue; seen.add(k);
        const row=rowOf(a); const img=row?row.querySelector('img'):null;
        let path=null; if(img){try{path=new URL(img.src,location.href).pathname}catch(e){}}
        out.push({title:a.textContent.trim(), path});}
      return out;
    }"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(SRC, wait_until="networkidle", timeout=60000)
        try:
            pg.wait_for_selector('a[href*="/lab/correll/20"]', timeout=30000)
        except Exception:
            pass
        pg.wait_for_timeout(2500)
        rows = pg.evaluate(js)
        b.close()
    return [r for r in rows if r.get("path") and "/files/" in r["path"]]


def save_image(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "correll-site image sync"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    try:
        from PIL import Image
        im = Image.open(dest)
        im.thumbnail((MAXPX, MAXPX))
        im.save(dest)
    except Exception as e:
        print(f"    (resize skipped: {e})", file=sys.stderr)


def main():
    os.makedirs(PUB_DIR, exist_ok=True)
    oa_titles = load_openalex_titles()
    rows = extract_rows()
    print(f"found {len(rows)} papers with thumbnails", file=sys.stderr)
    images = {}
    for r in rows:
        orig = to_original(r["path"])
        fn = os.path.basename(orig)
        dest = os.path.join(PUB_DIR, fn)
        url = ORIGIN + orig
        try:
            save_image(url, dest)
            images[match_title(r["title"], oa_titles)] = f"assets/pubs/{fn}"
            print(f"  ok  {fn}  <-  {r['title'][:60]}", file=sys.stderr)
        except Exception as e:
            print(f"  FAIL {fn}: {e}", file=sys.stderr)
    out = {"source": "colorado.edu/lab/correll/all-papers", "count": len(images), "images": images}
    json.dump(out, open(OUT, "w"), indent=2)
    print(f"wrote {len(images)} image mappings to {OUT}")


if __name__ == "__main__":
    main()
