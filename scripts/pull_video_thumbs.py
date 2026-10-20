#!/usr/bin/env python3
"""Download a poster frame for every embedded YouTube video.

Embedding a YouTube iframe costs the visitor a few hundred kilobytes of someone
else's JavaScript before they have asked to watch anything, and it is what drags
the desktop Lighthouse performance score down. The Web Theme's Video component has
a "placeholder" style for this: a poster image that ndt.js swaps for the real
player on click. This fetches those posters so they can be served from our own
domain as WebP, rather than hot-linking them.

YouTube offers several poster sizes and not every video has every one; a missing
size comes back as a 120x90 grey placeholder rather than a 404, so that is what we
check for. 4:3 posters are centre-cropped to 16:9 so the cards line up.

Deps: pillow. Usage: python3 scripts/pull_video_thumbs.py
"""
import io, json, os, sys, time, traceback, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "video_thumbs.json")
DIR = os.path.join(ROOT, "assets", "video")
WIDTH = 640
SIZES = ("maxresdefault", "hq720", "sddefault", "hqdefault")
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")}


def video_ids():
    """Every video id the site embeds, in page order, de-duplicated."""
    ids = []
    videos = os.path.join(ROOT, "data", "videos.json")
    if os.path.exists(videos):
        for v in json.load(open(videos)).get("videos", []):
            if v.get("id"):
                ids.append(v["id"])
    art = os.path.join(ROOT, "data", "art.json")
    if os.path.exists(art):
        for w in json.load(open(art)).get("works", []):
            if w.get("video"):
                ids.append(w["video"])
    seen, uniq = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq


def fetch(url, attempts=3):
    """One poster, with a retry. Returns the bytes, or None if it could not be had.

    Catches broadly on purpose. Only HTTPError was caught before, which left plain
    URLError, socket timeouts and RemoteDisconnected to propagate — so a single
    flaky request from a CDN we do not control aborted the whole weekly refresh,
    taking the publication crawl and the deploy down with it.
    """
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(2 * attempt)
                continue
            return None            # 404 and friends: this size simply is not there
        except Exception as exc:   # URLError, timeout, reset connection, anything
            if attempt < attempts:
                time.sleep(2 * attempt)
                continue
            print(f"  --  {url}: {exc}", file=sys.stderr)
            return None
    return None


def best_poster(vid):
    """The largest poster YouTube actually has for this video."""
    from PIL import Image
    for name in SIZES:
        data = fetch(f"https://i.ytimg.com/vi/{vid}/{name}.jpg")
        if not data:
            continue
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
        except Exception as exc:   # an HTML error page, a truncated body
            print(f"  --  {vid}/{name}: not an image ({exc})", file=sys.stderr)
            continue
        if im.width <= 120:          # YouTube's "no such size" grey placeholder
            continue
        return name, im
    return None, None


def main():
    os.makedirs(DIR, exist_ok=True)
    # Start from what we already have rather than from nothing. Rebuilding the index
    # from scratch meant one failed fetch silently dropped that video's entry, even
    # though its poster was still sitting on disk, and the page quietly went back to
    # hot-linking YouTube.
    thumbs = {}
    if os.path.exists(OUT):
        try:
            for vid, rel in (json.load(open(OUT)).get("thumbs") or {}).items():
                if os.path.exists(os.path.join(ROOT, rel)):
                    thumbs[vid] = rel
        except Exception as exc:
            print(f"  --  could not read {OUT}: {exc}", file=sys.stderr)

    wanted = video_ids()
    fetched = 0
    for vid in wanted:
        name, im = best_poster(vid)
        if im is None:
            if vid in thumbs:
                print(f"  ..  keeping the existing poster for {vid}", file=sys.stderr)
            else:
                print(f"  --  no poster for {vid}", file=sys.stderr)
            continue
        # Guarded like the fetch above it. Hardening only the download left this
        # half exposed, and a single image that will not convert, resize or encode
        # still took the whole weekly refresh down with it. The traceback is printed
        # in full because the last two failures here could not be diagnosed from the
        # job log.
        try:
            im = im.convert("RGB")
            target = WIDTH * 9 / 16
            if abs(im.width / im.height - 16 / 9) > 0.01:   # 4:3 -> crop the bars off
                h = round(im.width * 9 / 16)
                top = (im.height - h) // 2
                im = im.crop((0, top, im.width, top + h))
            im = im.resize((WIDTH, round(target)), Image.LANCZOS)
            dest = os.path.join(DIR, f"{vid}.webp")
            im.save(dest, "WEBP", quality=80, method=6)
        except Exception:
            print(f"  --  {vid}: could not process the {name} poster", file=sys.stderr)
            traceback.print_exc()
            continue
        thumbs[vid] = os.path.relpath(dest, ROOT)
        fetched += 1
        print(f"  ok  {os.path.basename(dest)} ({name})", file=sys.stderr)

    thumbs = {vid: thumbs[vid] for vid in wanted if vid in thumbs}   # page order
    try:
        json.dump({"count": len(thumbs), "thumbs": thumbs}, open(OUT, "w"), indent=2)
    except Exception:
        print(f"::warning::could not write {OUT}", file=sys.stderr)
        traceback.print_exc()
        return
    print(f"{fetched} fetched, {len(thumbs)} of {len(wanted)} posters -> {OUT}")
    if not thumbs and wanted:
        # Worth noticing, but not worth failing the job over: the pages fall back to
        # YouTube's own poster, and the publication refresh still deserves to land.
        print("::warning::no video posters could be fetched this run", file=sys.stderr)


if __name__ == "__main__":
    main()
