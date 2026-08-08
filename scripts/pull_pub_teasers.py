#!/usr/bin/env python3
"""Generate a one-line teaser for each publication from its abstract, via the Claude API.

Incremental and best-effort: only papers that have an abstract and no cached teaser are sent to
the model, so each run does a little more and repeated runs are cheap. If no ANTHROPIC_API_KEY is
configured the script exits cleanly and the site simply shows no teasers. Results are cached in
data/pub_teasers.json.

Usage: python3 scripts/pull_pub_teasers.py [--limit N]
"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBS = os.path.join(ROOT, "data", "publications.json")
ABSTRACTS = os.path.join(ROOT, "data", "abstracts.json")
OUT = os.path.join(ROOT, "data", "pub_teasers.json")
SLEEP = 0.4

SYS = ("You write one-line teasers for the publication list on a robotics lab website. "
       "Given a paper's title and abstract, write ONE plain, specific sentence (max 18 words) "
       "stating what the work does or shows. No hype, no 'this paper'/'we', no citations, "
       "no quotation marks, no internal or system XML tags. Output only the sentence.")


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def clean(s):
    return re.sub(r"\s+", " ", s.strip().strip('"').strip())


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    if not llm.available():
        print("No ANTHROPIC_API_KEY — skipping teasers.", file=sys.stderr)
        return
    pubs = json.load(open(PUBS))
    abstracts = json.load(open(ABSTRACTS)).get("abstracts", {})
    teasers = json.load(open(OUT)).get("teasers", {}) if os.path.exists(OUT) else {}

    titles = {norm(it["title"]): it["title"] for g in pubs.get("years", []) for it in g.get("items", [])}
    todo = [(k, titles[k]) for k in titles if k in abstracts and k not in teasers]
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} teasers to generate ({len(teasers)} cached, {len(abstracts)} abstracts) "
          f"using {llm.MODEL}", file=sys.stderr)

    made = 0
    try:
        for k, title in todo:
            try:
                t = clean(llm.text(SYS, f"Title: {title}\n\nAbstract: {abstracts[k]}", max_tokens=80))
            except llm.Unavailable as e:
                print(f"LLM unavailable: {e} — stopping.", file=sys.stderr)
                break
            if t:
                teasers[k] = t
                made += 1
                print(f"  ok  {title[:56]}\n      -> {t}", file=sys.stderr)
            time.sleep(SLEEP)
    except llm.RateLimited as e:
        print(f"Rate limited ({e}) — saving {made} new, will continue next run.", file=sys.stderr)

    json.dump({"count": len(teasers), "teasers": teasers}, open(OUT, "w"), indent=2)
    print(f"wrote {len(teasers)} teasers ({made} new) -> {OUT}")


if __name__ == "__main__":
    main()
