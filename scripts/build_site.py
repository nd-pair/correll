#!/usr/bin/env python3
"""Assemble the static pages from partials/ + pages/.

The Notre Dame Web Theme (NDT4) requires the site header, footer, global menu and
icon sprite to appear in the markup of every page. Rather than duplicate that
chrome by hand, each page in pages/ holds only its <main> content plus a small
JSON front-matter block; this script stitches the shared partials around it and
writes the finished page to the repository root (which is what GitHub Pages
publishes). Run it after editing anything in partials/ or pages/:

    python3 scripts/build_site.py
"""
import datetime, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
BASE = "https://nd-pair.github.io/correll/"

NAV = [
    ("index.html", "Home"),
    ("publications.html", "Publications"),
    ("people.html", "People"),
    ("teaching.html", "Teaching"),
    ("art.html", "Art"),
]


def read(*a):
    with open(P(*a), encoding="utf-8") as fh:
        return fh.read()


def nav_html(current, mobile=False):
    out = []
    for i, (href, label) in enumerate(NAV):
        active = href == current
        if mobile:
            cls = []
            if i == 0:
                cls.append("first")
            if i == len(NAV) - 1:
                cls.append("last")
            if active:
                cls.append("active")
            a = '<a href="%s"%s>%s</a>' % (
                href, ' aria-current="page" class="current"' if active else "", label)
            out.append('        <li%s>%s</li>' % (
                ' class="%s"' % " ".join(cls) if cls else "", a))
        else:
            a = '<a href="%s"%s>%s</a>' % (
                href, ' aria-current="page"' if active else "", label)
            out.append('              <li%s>%s</li>' % (
                ' class="active"' if active else "", a))
    return "\n".join(out)


def write_sitemap(urls):
    """A sitemap and robots.txt so crawlers (and the QA review) find every page."""
    today = datetime.date.today().isoformat()
    entries = "\n".join(
        "  <url><loc>%s</loc><lastmod>%s</lastmod></url>" % (u, today) for u in urls)
    with open(P("sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                 "%s\n</urlset>\n" % entries)
    with open(P("robots.txt"), "w", encoding="utf-8") as fh:
        fh.write("User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n" % BASE)


def main():
    head = read("partials", "head.html")
    sprite = read("partials", "sprite.svg").strip()
    skiplinks = read("partials", "skiplinks.html").strip()
    header = read("partials", "header.html")
    footer = read("partials", "footer.html")
    menu = read("partials", "globalmenu.html")
    tail = read("partials", "tail.html")
    year = str(datetime.date.today().year)

    pages, built = [], []
    for name in sorted(os.listdir(P("pages"))):
        if not name.endswith(".html"):
            continue
        raw = read("pages", name)
        try:
            fm_raw, body = raw.split("\n---\n", 1)
            fm = json.loads(fm_raw)
        except Exception as exc:  # pragma: no cover - build-time guard
            sys.exit("pages/%s: bad front matter (%s)" % (name, exc))

        canonical = BASE if name == "index.html" else BASE + name
        page = (
            head.replace("{{TITLE}}", fm["title"])
                .replace("{{DESCRIPTION}}", fm["description"])
                .replace("{{CANONICAL}}", canonical)
                .replace("{{BASE}}", BASE)
            + sprite + "\n"
            + skiplinks + "\n"
            + '<div class="%s" id="wrapper">\n' % fm.get(
                "wrapper", "wrapper page--full-width nav-top--false")
            + header.replace("{{NAV}}", nav_html(name)) + "\n"
            + render.expand(body.strip()) + "\n"
            + footer.replace("{{YEAR}}", year) + "\n"
            + "</div><!-- .wrapper -->\n"
            + menu.replace("{{MOBILENAV}}", nav_html(name, mobile=True)) + "\n"
            + tail.replace("{{PAGESCRIPT}}", fm.get("script", ""))
        )
        with open(P(name), "w", encoding="utf-8") as fh:
            fh.write(page)
        built.append(name)
        if name != "404.html":
            pages.append(canonical)

    write_sitemap(pages)
    print("built: " + ", ".join(built))


if __name__ == "__main__":
    main()
