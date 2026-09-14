#!/usr/bin/env python3
"""Render the data-driven parts of the site (publications, people, teaching, art,
videos) into static HTML fragments at build time.

Pre-rendering rather than fetching JSON in the browser keeps the pages fast, makes
the content available without JavaScript, and lets search engines and screen
readers see the real markup. All markup here uses Notre Dame Web Theme (NDT4)
components; see https://webtheme.nd.edu.
"""
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from PIL import Image
except Exception:  # Pillow is optional; without it we simply omit width/height
    Image = None

_SIZES = {}


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", str(t or "").lower()).strip()


def load(name, default=None):
    path = os.path.join(ROOT, "data", name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dims(rel):
    """Intrinsic size of a local image, so the browser can reserve space for it."""
    if rel in _SIZES:
        return _SIZES[rel]
    size = None
    path = os.path.join(ROOT, rel)
    if Image and os.path.exists(path):
        try:
            with Image.open(path) as im:
                size = im.size
        except Exception:
            size = None
    _SIZES[rel] = size
    return size


PLACEHOLDER = ('<figure class="card-image card-image--empty" aria-hidden="true">'
               '<span></span></figure>')


def img_tag(rel, alt="", cls=None, lazy=True, extra=""):
    size = dims(rel)
    wh = ' width="%d" height="%d"' % size if size else ""
    return '<img src="%s" alt="%s"%s%s%s%s>' % (
        esc(rel), esc(alt),
        ' class="%s"' % cls if cls else "",
        wh,
        ' loading="lazy" decoding="async"' if lazy else "",
        (" " + extra) if extra else "",
    )


# --------------------------------------------------------------------------- #
# publications
# --------------------------------------------------------------------------- #

def _pub_images():
    figs = (load("pub_figures.json") or {}).get("images", {})
    curated = (load("pub_images.json") or {}).get("images", {})
    merged = dict(figs)
    merged.update(curated)  # curated thumbnails win over auto-extracted figures
    return merged


def _authors(names, mark=re.compile(r"correll", re.I)):
    if not names:
        return ""
    shown = names[:8]
    out = [('<b>%s</b>' % esc(n)) if mark.search(n) else esc(n) for n in shown]
    txt = ", ".join(out)
    if len(names) > len(shown):
        txt += ' <span class="pub-more">and %d more</span>' % (len(names) - len(shown))
    return txt


def _pub_card(w, images, teasers, heading="h3"):
    link = w.get("doi") or w.get("id")
    key = norm(w.get("title"))
    img = images.get(key)
    teaser = teasers.get(key)
    figure = ('<figure class="card-image">%s</figure>'
              % img_tag(img, "")) if img else PLACEHOLDER
    meta = " &middot; ".join(x for x in [esc(w.get("venue")), esc(w.get("year"))] if x)
    title = esc(w.get("title"))
    title_html = ('<a class="card-link" href="%s">%s</a>' % (esc(link), title)) if link else title
    return (
        '<li class="card-container">\n'
        '  <article class="card card--horizontal card--image-sm card--pub">\n'
        '    %s\n'
        '    <div class="card-body">\n'
        '      <%s class="card-title">%s</%s>\n'
        '%s'
        '      <p class="card-meta">%s</p>\n'
        '      <p class="card-meta">%s</p>\n'
        '    </div>\n'
        '  </article>\n'
        '</li>' % (
            figure, heading, title_html, heading,
            ('      <p class="card-summary">%s</p>\n' % esc(teaser)) if teaser else "",
            _authors(w.get("authors")), meta)
    )


def recent_publications(count=4):
    pubs = load("publications.json") or {"years": []}
    images, teasers = _pub_images(), (load("pub_teasers.json") or {}).get("teasers", {})
    flat = [it for g in pubs.get("years", []) for it in g.get("items", [])][:count]
    cards = []
    for w in flat:
        link = w.get("doi") or w.get("id")
        key = norm(w.get("title"))
        img = images.get(key)
        figure = ('<figure class="card-image">%s</figure>' % img_tag(img, "")) if img else PLACEHOLDER
        title = esc(w.get("title"))
        title_html = ('<a class="card-link" href="%s">%s</a>' % (esc(link), title)) if link else title
        cards.append(
            '<li class="card-container">\n'
            '  <article class="card card--pub">\n'
            '    %s\n'
            '    <div class="card-body">\n'
            '      <p class="card-label">%s</p>\n'
            '      <h3 class="card-title">%s</h3>\n'
            '      <p class="card-meta">%s</p>\n'
            '    </div>\n'
            '  </article>\n'
            '</li>' % (figure, esc(w.get("year") or ""), title_html, esc(w.get("venue") or ""))
        )
    return "\n".join(cards)


def publications_summary():
    pubs = load("publications.json") or {}
    years = [g for g in pubs.get("years", []) if g.get("year")]
    return "%s publications across %s years, synchronised weekly from %s." % (
        pubs.get("total", 0), len(years), esc(pubs.get("source", "OpenAlex")))


def publications_anchors():
    pubs = load("publications.json") or {"years": []}
    items = ['<li><a href="#y%s">%s</a></li>' % (g["year"], g["year"])
             for g in pubs.get("years", []) if g.get("year")]
    return "\n      ".join(items)


def publications_list():
    pubs = load("publications.json") or {"years": []}
    images, teasers = _pub_images(), (load("pub_teasers.json") or {}).get("teasers", {})
    out = []
    for g in pubs.get("years", []):
        year = g.get("year") or "Other"
        cards = "\n".join(_pub_card(w, images, teasers) for w in g.get("items", []))
        out.append(
            '<section class="section pub-year" data-year="%s">\n'
            '  <h2 class="section-title section-title--sm" id="y%s">%s '
            '<span class="pub-count">%s</span></h2>\n'
            '  <ul class="list--unstyled pub-list">\n%s\n  </ul>\n'
            '</section>' % (esc(year), esc(year), esc(year), g.get("count", 0), cards))
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# people
# --------------------------------------------------------------------------- #

def _person_card(m, heading="h3"):
    img = m.get("img")
    figure = ('<figure class="avatar avatar--sm card-image">%s</figure>'
              % img_tag(img, "")) if img else ""
    role = ('<p class="person-title">%s</p>' % esc(m.get("role") or m.get("title"))) \
        if (m.get("role") or m.get("title")) else ""
    return (
        '<li class="card-container">\n'
        '  <div class="card card--person card--stacked">\n'
        '    %s\n'
        '    <div class="card-body">\n'
        '      <%s class="card-title">%s</%s>\n'
        '      %s\n'
        '    </div>\n'
        '  </div>\n'
        '</li>' % (figure, heading, esc(m.get("name")), heading, role))


def people_pi():
    data = load("people.json") or []
    groups = data.get("groups") if isinstance(data, dict) else data
    pi = next((g for g in groups if re.fullmatch(r"pi", g["group"], re.I)
               or re.search(r"principal", g["group"], re.I)), None)
    if not pi or not pi.get("members"):
        return ""
    p = pi["members"][0]
    figure = ('<figure class="avatar avatar--md card-image">%s</figure>'
              % img_tag(p["img"], "", lazy=False)) if p.get("img") else ""
    bits = []
    if p.get("title"):
        bits.append('<p class="person-title">%s</p>' % esc(p["title"]))
    if p.get("bio"):
        bits.append('<p class="card-summary">%s</p>' % esc(p["bio"]))
    if p.get("email"):
        bits.append('<p class="card-meta"><a href="mailto:%s">%s</a></p>'
                    % (esc(p["email"]), esc(p["email"])))
    return (
        '<div class="card-container">\n'
        '  <div class="card card--person card--horizontal">\n'
        '    %s\n'
        '    <div class="card-body">\n'
        '      <h2 class="card-title">%s</h2>\n'
        '      %s\n'
        '    </div>\n'
        '  </div>\n'
        '</div>' % (figure, esc(p["name"]), "\n      ".join(bits)))


def people_groups():
    data = load("people.json") or []
    groups = data.get("groups") if isinstance(data, dict) else data
    out = []
    for g in groups:
        name = g["group"]
        if re.fullmatch(r"pi", name, re.I) or re.search(r"principal", name, re.I):
            continue
        if re.search(r"alumni", name, re.I):
            continue
        cards = "\n".join(_person_card(m) for m in g["members"])
        out.append(
            '<section class="section">\n'
            '  <h2 class="section-title section-title--sm">%s</h2>\n'
            '  <ul class="grid grid-sm-2 grid-ml-4 list--unstyled">\n%s\n  </ul>\n'
            '</section>' % (esc(name), cards))
    return "\n".join(out)


def people_alumni():
    data = load("people.json") or []
    groups = data.get("groups") if isinstance(data, dict) else data
    out = []
    for g in groups:
        if not re.search(r"alumni", g["group"], re.I):
            continue
        rows = "\n".join(
            '      <li><b>%s</b>%s</li>' % (
                esc(m["name"]),
                (' <span class="alumni-role">%s</span>' % esc(m["role"])) if m.get("role") else "")
            for m in g["members"])
        out.append(
            '<details class="accordion">\n'
            '  <summary>%s (%d)</summary>\n'
            '  <div class="accordion-content">\n'
            '    <ul class="list--unstyled alumni-list">\n%s\n    </ul>\n'
            '  </div>\n'
            '</details>' % (esc(g["group"]), len(g["members"]), rows))
    if not out:
        return ""
    return '<div class="accordion-list">\n%s\n</div>' % "\n".join(out)


# --------------------------------------------------------------------------- #
# teaching, art, videos
# --------------------------------------------------------------------------- #

def teaching_cards():
    courses = load("teaching.json") or []
    out = []
    for c in courses:
        title = esc(c.get("title"))
        title_html = ('<a class="card-link" href="%s">%s</a>' % (esc(c["url"]), title)) \
            if c.get("url") else title
        out.append(
            '<li class="card-container">\n'
            '  <div class="card card--border">\n'
            '    <div class="card-body">\n'
            '      <p class="card-label">%s</p>\n'
            '      <h2 class="card-title">%s</h2>\n'
            '      <p class="card-summary">%s</p>\n'
            '    </div>\n'
            '  </div>\n'
            '</li>' % (esc(c.get("code") or ""), title_html, esc(c.get("desc") or "")))
    return "\n".join(out)


def _embed(video_id, title):
    return (
        '<div class="video--wrapper">\n'
        '  <iframe width="1280" height="720" style="aspect-ratio:16/9"\n'
        '    src="https://www.youtube-nocookie.com/embed/%s" title="%s"\n'
        '    loading="lazy" referrerpolicy="strict-origin-when-cross-origin"\n'
        '    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"\n'
        '    allowfullscreen></iframe>\n'
        '</div>' % (esc(video_id), esc(title)))


def videos():
    vids = (load("videos.json") or {}).get("videos", [])
    out = []
    for v in vids:
        out.append(
            '<li>\n'
            '  <article class="card card--video">\n'
            '    %s\n'
            '    <div class="card-body">\n'
            '      <h3 class="card-title">%s</h3>\n'
            '      <p class="card-meta">%s</p>\n'
            '    </div>\n'
            '  </article>\n'
            '</li>' % (_embed(v["id"], v["title"]), esc(v["title"]), esc(v.get("source") or "")))
    return "\n".join(out)


def art_intro():
    return esc((load("art.json") or {}).get("intro", ""))


def art_works():
    works = (load("art.json") or {}).get("works", [])
    out = []
    for w in works:
        body = "\n      ".join('<p>%s</p>' % esc(p) for p in w.get("body", []))
        figure = ('\n      <figure class="image image-default">%s</figure>'
                  % img_tag(w["image"], esc(w["title"]))) if w.get("image") else ""
        video = ("\n      " + _embed(w["video"], w["title"])) if w.get("video") else ""
        links = ""
        if w.get("links"):
            links = '\n      <p class="btn-list">%s</p>' % " ".join(
                '<a class="btn btn--secondary" href="%s">%s</a>' % (esc(l["url"]), esc(l["label"]))
                for l in w["links"])
        watch = ""
        if w.get("watch"):
            watch = '\n      <p class="art-refs">Referenced: %s</p>' % " &middot; ".join(
                '<a href="https://www.youtube.com/watch?v=%s">%s</a>' % (esc(v["id"]), esc(v["label"]))
                for v in w["watch"])
        refs = ""
        if w.get("refs"):
            refs = '\n      <p class="art-refs">%s</p>' % "<br>".join(esc(r) for r in w["refs"])
        out.append(
            '<section class="section art-work">\n'
            '  <h2 class="section-title section-title--sm">%s</h2>\n'
            '  <p class="card-label">%s</p>\n'
            '      %s%s%s%s%s%s\n'
            '</section>' % (esc(w["title"]), esc(w.get("year") or ""),
                            body, figure, video, links, watch, refs))
    return "\n".join(out)


TOKENS = {
    "RECENT_PUBLICATIONS": recent_publications,
    "PUBLICATIONS_SUMMARY": publications_summary,
    "PUBLICATIONS_ANCHORS": publications_anchors,
    "PUBLICATIONS_LIST": publications_list,
    "PEOPLE_PI": people_pi,
    "PEOPLE_GROUPS": people_groups,
    "PEOPLE_ALUMNI": people_alumni,
    "TEACHING_CARDS": teaching_cards,
    "VIDEOS": videos,
    "ART_INTRO": art_intro,
    "ART_WORKS": art_works,
}


def expand(text):
    for key, fn in TOKENS.items():
        token = "{{%s}}" % key
        if token in text:
            text = text.replace(token, fn())
    return text
