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
import io, json, os, sys, urllib.error, urllib.request

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


def best_poster(vid):
    """The largest poster YouTube actually has for this video."""
    from PIL import Image
    for name in SIZES:
        url = f"https://i.ytimg.com/vi/{vid}/{name}.jpg"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
        except urllib.error.HTTPError:
            continue
        im = Image.open(io.BytesIO(data))
        if im.width <= 120:          # YouTube's "no such size" grey placeholder
            continue
        return name, im
    return None, None


def main():
    os.makedirs(DIR, exist_ok=True)
    thumbs = {}
    for vid in video_ids():
        name, im = best_poster(vid)
        if im is None:
            print(f"  --  no poster for {vid}", file=sys.stderr)
            continue
        im = im.convert("RGB")
        target = WIDTH * 9 / 16
        if abs(im.width / im.height - 16 / 9) > 0.01:   # 4:3 poster -> crop the bars off
            h = round(im.width * 9 / 16)
            top = (im.height - h) // 2
            im = im.crop((0, top, im.width, top + h))
        im = im.resize((WIDTH, round(target)), Image.LANCZOS)
        dest = os.path.join(DIR, f"{vid}.webp")
        im.save(dest, "WEBP", quality=80, method=6)
        thumbs[vid] = os.path.relpath(dest, ROOT)
        print(f"  ok  {os.path.basename(dest)} ({name})", file=sys.stderr)
    json.dump({"count": len(thumbs), "thumbs": thumbs}, open(OUT, "w"), indent=2)
    print(f"wrote {len(thumbs)} posters -> {OUT}")


if __name__ == "__main__":
    main()
