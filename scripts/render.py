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


def _first_pages():
    """Papers whose thumbnail is a render of page one rather than a figure.

    The two need different alt text: "a figure from" is a claim about the content of
    the image, and it would be wrong for a page render.
    """
    return set((load("pub_figures.json") or {}).get("first_page", []))


def _pub_alt(key, title, first_pages):
    """Describe what the thumbnail actually is, in terms of the paper beside it."""
    kind = "First page of" if key in first_pages else "Figure from"
    return "%s the paper \u201c%s\u201d" % (kind, title or "this publication")


def plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def _authors(names, mark=re.compile(r"correll", re.I)):
    if not names:
        return ""
    shown = names[:8]
    out = [('<b>%s</b>' % esc(n)) if mark.search(n) else esc(n) for n in shown]
    txt = ", ".join(out)
    if len(names) > len(shown):
        txt += ' <span class="pub-more">and %d more</span>' % (len(names) - len(shown))
    return txt


def _pub_card(w, images, teasers, first_pages, heading="h3"):
    link = w.get("doi") or w.get("id")
    key = norm(w.get("title"))
    img = images.get(key)
    teaser = teasers.get(key)
    figure = ('<figure class="card-image">%s</figure>'
              % img_tag(img, _pub_alt(key, w.get("title"), first_pages))) if img else PLACEHOLDER
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
    first_pages = _first_pages()
    flat = [it for g in pubs.get("years", []) for it in g.get("items", [])][:count]
    cards = []
    for w in flat:
        link = w.get("doi") or w.get("id")
        key = norm(w.get("title"))
        img = images.get(key)
        figure = ('<figure class="card-image">%s</figure>'
                  % img_tag(img, _pub_alt(key, w.get("title"), first_pages))) if img else PLACEHOLDER
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


# "OpenAlex (https://openalex.org)" in the data; a link on the name reads better
# than a URL printed in running text, and gives the link its own context.
_SOURCE = re.compile(r"^\s*(.+?)\s*\((https?://[^)]+)\)\s*$")


def publications_summary():
    pubs = load("publications.json") or {}
    years = [g for g in pubs.get("years", []) if g.get("year")]
    source = pubs.get("source") or "OpenAlex"
    m = _SOURCE.match(source)
    source_html = ('<a href="%s">%s</a>' % (esc(m.group(2)), esc(m.group(1)))) if m \
        else esc(source)
    return "%s across %s, synchronised weekly from %s." % (
        plural(pubs.get("total", 0), "publication"), plural(len(years), "year"), source_html)


def publications_anchors():
    pubs = load("publications.json") or {"years": []}
    items = ['<li><a href="#y%s">%s</a></li>' % (g["year"], g["year"])
             for g in pubs.get("years", []) if g.get("year")]
    return "\n      ".join(items)


def publications_list():
    pubs = load("publications.json") or {"years": []}
    images, teasers = _pub_images(), (load("pub_teasers.json") or {}).get("teasers", {})
    first_pages = _first_pages()
    out = []
    for g in pubs.get("years", []):
        year = g.get("year") or "Other"
        cards = "\n".join(_pub_card(w, images, teasers, first_pages)
                          for w in g.get("items", []))
        # A bare number after the year read as part of the heading. The unit makes it
        # a count; data-total lets app.js keep it honest while the list is filtered.
        out.append(
            '<section class="section pub-year" data-year="%s">\n'
            '  <h2 class="section-title section-title--sm" id="y%s">%s '
            '<span class="pub-count" data-total="%d">%s</span></h2>\n'
            '  <ul class="list--unstyled pub-list">\n%s\n  </ul>\n'
            '</section>' % (esc(year), esc(year), esc(year),
                            g.get("count", 0), plural(g.get("count", 0), "publication"),
                            cards))
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# people
# --------------------------------------------------------------------------- #

def _person_card(m, heading="h3"):
    img = m.get("img")
    figure = ('<figure class="avatar avatar--sm card-image">%s</figure>'
              % img_tag(img, "Portrait of %s" % (m.get("name") or ""))) if img else ""
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
              % img_tag(p["img"], "Portrait of %s" % p.get("name", ""), lazy=False)) \
        if p.get("img") else ""
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
        '  <div class="card card--person">\n'
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


def _video(video_id, title):
    """The theme's Video component in its dialog style.

    An embedded iframe pulls a few hundred kilobytes of YouTube's JavaScript before
    the visitor has asked to watch anything; on a desktop viewport, where several are
    above the fold, that alone cost 840ms of blocking time. The dialog style keeps a
    poster image in the page and the player in a <dialog> that ndt.js opens on click,
    so the video plays over the page instead of replacing what the visitor was
    reading, and the anchor is still a working link to YouTube without JavaScript.

    The poster image carries alt="" on purpose: the anchor's own text is the video's
    title, so describing the thumbnail as well would make the link announce itself
    twice.
    """
    poster = (load("video_thumbs.json") or {}).get("thumbs", {}).get(video_id)
    if poster:
        img = img_tag(poster, "", extra='width="640" height="360"') if not dims(poster) \
            else img_tag(poster, "")
    else:
        # Until pull_video_thumbs.py has run, fall back to YouTube's own poster.
        img = ('<img src="https://i.ytimg.com/vi/%s/hqdefault.jpg" alt="" width="480" '
               'height="360" loading="lazy" decoding="async">' % esc(video_id))
    return (
        '<div class="video--wrapper">\n'
        '    <div class="dialog-item">\n'
        '      <a class="video video--default dialog-link" href="https://www.youtube.com/watch?v=%s">\n'
        '        <figure>%s</figure>\n'
        '        %s\n'
        '      </a>\n'
        '      <dialog class="dialog dialog--video">\n'
        '        <form method="dialog" class="dialog-close">\n'
        '          <button type="submit" title="Close">&times;</button>\n'
        '        </form>\n'
        '        <div class="dialog-content">\n'
        '          <iframe width="1280" height="720" style="aspect-ratio: 16/9;" '
        'src="https://www.youtube.com/embed/%s?enablejsapi=1" title="%s" '
        'frameborder="0" loading="lazy" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; '
        'picture-in-picture" allowfullscreen="allowfullscreen"></iframe>\n'
        '        </div>\n'
        '      </dialog>\n'
        '    </div>\n'
        '  </div>' % (esc(video_id), img, esc(title), esc(video_id), esc(title)))


def videos():
    vids = (load("videos.json") or {}).get("videos", [])
    out = []
    for v in vids:
        # The theme has a Video component but no "video card", so this is the component
        # itself with an ordinary heading and caption under it, rather than a card
        # variant the design kit does not define.
        out.append(
            '<li>\n'
            '  %s\n'
            '  <p>%s</p>\n'
            '</li>' % (_video(v["id"], v["title"]), esc(v.get("source") or "")))
    return "\n".join(out)


def art_intro():
    return esc((load("art.json") or {}).get("intro", ""))


def art_works():
    works = (load("art.json") or {}).get("works", [])
    out = []
    for w in works:
        body = "\n      ".join('<p>%s</p>' % esc(p) for p in w.get("body", []))
        # img_tag escapes for us; passing esc() in as well double-escaped the title.
        figure = ('\n      <figure class="image image-default">%s</figure>'
                  % img_tag(w["image"], w.get("alt") or w["title"])) if w.get("image") else ""
        video = ("\n      " + _video(w["video"], w["title"])) if w.get("video") else ""
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
