#!/usr/bin/env python3
"""Build data/publications.json for correll.cs.colorado.edu → nd-pair.github.io/correll,
from OpenAlex (Nikolaus Correll's author ids, incl. split identities), grouped by year."""
import json, os, re, sys, time, urllib.parse, urllib.request, datetime

MAILTO = os.environ.get("OPENALEX_MAILTO", "nikolaus.correll@gmail.com")
API = "https://api.openalex.org"
IDS = ["A5047458039", "A5119753651", "A5120513272", "A5128775924", "A5130238936", "A5130284295"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": f"correll-site ({MAILTO})"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def pick_pdf(w):
    """Best open-access PDF url for a work, if any (used for automatic figure extraction)."""
    for key in ("best_oa_location", "primary_location"):
        loc = w.get(key) or {}
        if loc.get("pdf_url"):
            return loc["pdf_url"]
    for loc in (w.get("locations") or []):
        if loc.get("pdf_url"):
            return loc["pdf_url"]
    return (w.get("open_access") or {}).get("oa_url")


def works_for(aid):
    cursor = "*"
    while cursor:
        q = urllib.parse.urlencode({
            "filter": f"author.id:{aid}",
            "select": ("id,title,publication_year,publication_date,primary_location,"
                       "best_oa_location,locations,open_access,authorships,doi"),
            "per-page": 200, "cursor": cursor, "mailto": MAILTO})
        d = get(f"{API}/works?{q}")
        for w in d.get("results", []):
            yield w
        cursor = d.get("meta", {}).get("next_cursor")
        time.sleep(0.2)


def main():
    works = {}
    for aid in IDS:
        n = 0
        for w in works_for(aid):
            n += 1
            wid = w["id"]
            if wid in works:
                continue
            loc = (w.get("primary_location") or {})
            src = (loc.get("source") or {}) if loc else {}
            works[wid] = {
                "id": wid, "doi": w.get("doi"),
                "title": (w.get("title") or "(untitled)").strip(),
                "year": w.get("publication_year"), "date": w.get("publication_date"),
                "venue": src.get("display_name") if src else None,
                "pdf": pick_pdf(w),
                "authors": [ (a.get("author") or {}).get("display_name") for a in w.get("authorships", [])
                             if (a.get("author") or {}).get("display_name") ],
            }
        print(f"  {aid}: {n} works", file=sys.stderr)

    # de-dup preprint/published by title
    def norm(t): return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()
    def score(w): return (1 if w.get("venue") else 0, 1 if w.get("date") else 0)
    by_title = {}
    for w in works.values():
        k = norm(w["title"]) or w["id"]
        cur = by_title.get(k)
        if cur is None or score(w) > score(cur):
            if cur:  # keep the fuller author list
                if len(cur["authors"]) > len(w["authors"]): w["authors"] = cur["authors"]
            by_title[k] = w

    years = {}
    for w in by_title.values():
        years.setdefault(w["year"], []).append(w)
    year_list = []
    for y in sorted(years, key=lambda y: (y is None, -(y or 0))):
        items = sorted(years[y], key=lambda w: (w["date"] or "", w["title"]), reverse=True)
        year_list.append({"year": y, "count": len(items), "items": items})

    out = {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "source": "OpenAlex (https://openalex.org)", "total": len(by_title), "years": year_list}
    json.dump(out, open(os.path.join(ROOT, "data", "publications.json"), "w"), indent=2)
    print(f"wrote {len(by_title)} publications across {len(year_list)} years")


if __name__ == "__main__":
    main()
