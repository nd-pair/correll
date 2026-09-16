# Notre Dame website requirements

Working notes for the three Physical AI and Robotics Initiative sites. Everything below is a
requirement the University enforces, not a preference. Read this before changing markup or styles.

Primary source: **[University website requirements](https://onmessage.nd.edu/university-branding/website-requirements/)**

---

## 1. The design system is not optional

All three sites are built on **NDT4**, the Notre Dame Web Theme. *"Starting in January 2020, all new
websites must use the theme as a starting point."*

- Documentation and every component's real markup: **<https://webtheme.nd.edu>**
- Figma design kit: [NDT v4.0 Digital Design Guide](https://www.figma.com/community/file/1608505202606664443/university-of-notre-dame-web-theme-4-0-digital-design-guide)
- Shared assets, which every page must load:

```html
<link rel="stylesheet" href="https://conductor.nd.edu/stylesheets/themes/ndt/4.0/ndt.css">
...
<script>window.NDTConductorHost='https://conductor.nd.edu';</script>
<script src="https://conductor.nd.edu/javascripts/themes/ndt/4.0/ndt.js"></script>
```

### Check the markup, do not guess it

The theme's documentation is served to AI assistants over MCP at **`https://webtheme.nd.edu/mcp`**:

```bash
claude mcp add --transport http ndt4 https://webtheme.nd.edu/mcp
```

`docs-list` enumerates every component; `docs-show <id>` returns its options and the rendered HTML
for each variant. **If an option is not documented, it does not exist.** Notre Dame Creative's
feedback on this project was explicit: headings, buttons, page headers, news and events cards, the
site title and the primary navigation must be *exactly* as the kit defines them — "not
close-but-not-quite".

### Rules that follow from that

- **Never restyle a kit component.** No overriding the type, colour, border, radius or spacing of
  `.card`, `.btn`, `.site-title`, `.nav-primary`, `.page-title`, `.section-title`, `.notice`, `.stat`
  or any other themed class. `styles.css` in each repo exists only for patterns the kit has no
  component for, and builds them from theme custom properties (`var(--brand-blue)`,
  `var(--gray)`, `var(--link-blue)`) so light/dark mode and the palette hold.
- **Do not invent component variants.** A `card--video` that the kit does not define is a finding.
  Use the component the kit actually has — for video, the Video component's placeholder style.
- **Never hand-pick brand colours.** `#c99700` is not Notre Dame gold. Take colours from the theme.
- **Do not recreate the marks.** The academic mark ships as SVG in the theme sprite. *"Do not display
  altered or misused Notre Dame official logos or marks."* Raster lock-ups of unknown provenance are
  not acceptable substitutes.
- To verify a component matches, render the kit's own Storybook story at the same viewport and
  compare computed styles. Differences of 1–2px are real findings.

---

## 2. Quality thresholds

Measured with [PageSpeed Insights](https://pagespeed.web.dev/) / Lighthouse. These are enforced:

| | Requirement |
| --- | --- |
| Performance — mobile | ≥ 80 |
| Performance — desktop | ≥ 90 |
| Accessibility | **100** |
| SEO | **100** |
| Best practices | ≥ 80 |
| Conformance | **WCAG 2.2, Level AA** |

Accessibility also means, in the University's words: screen reader compatibility, keyboard
navigation, alt text, simple navigation, and proper colour contrast.

### What has actually broken these thresholds here

- **Third-party embeds.** Three YouTube iframes above the fold cost 840 ms of blocking time and took
  desktop performance to 68. Poster images with click-to-play took it to 100.
- **Text over photographs.** 16px white nav over a hero photo measured 3.2–4.1:1 against the 4.5:1
  minimum. The fix was a documented `fadeDirection` on the page header, not custom CSS.
- **Gold text.** Brand gold reaches ~3:1 on white. It carries graphics, never body text.
- **`display` defeating `hidden`.** An element with `display:flex` and a `hidden` attribute stays in
  the accessibility tree.
- **Unsized images.** Every `<img>` needs `width` and `height`, or CLS suffers.

---

## 3. Hosting and domain

Approved: [Conductor](https://conductor.nd.edu/), [sites.nd.edu](http://sites.nd.edu), AWS under the
University account, [WP Engine](https://wpengine.com/), [Netlify](https://www.netlify.com/),
DreamHost, WordPress.com. Prohibited: *"Google Sites, Wix, Weebly, or Squarespace."*

> **Open question for these repos.** They are on GitHub Pages, which appears on neither list. Confirm
> with Notre Dame Creative before a QA review is scheduled. GitHub Pages also fixes
> `Cache-Control: max-age=600` with no way to change headers, which costs points on the "efficient
> cache lifetimes" audit; Netlify or AWS would not.

**nd.edu subdomains** are approved by the Office of Public Affairs & Communications —
[creative.nd.edu/subdomains](https://creative.nd.edu/subdomains/). Five business days; never
advertise one before approval; lab subdomains must carry a relevant keyword.

---

## 4. Review and content

*"All websites created outside the University using a 'nd.edu' subdomain must be submitted to Notre
Dame Creative for QA review prior to going live"* — five business days. QA covers the technical
build, the design components **and the content**, so have final content in place first: team bios
and photographs, results, reports.

- No advertising or endorsements.
- Ownership or permission is required for every photograph and graphic.
- Contact: **webgroup@nd.edu** · [creative.nd.edu/web](https://creative.nd.edu/web/)

### When the theme does not apply

[Minimum web standards](https://onmessage.nd.edu/university-branding/website-requirements/minimum-web-standards/)
cover special events, branded campaigns, products and journals, auxiliaries, and arts units not tied
to an academic programme. Separately, **internal applications, third-party applications and
collaborations have no prescriptive design requirement**, "though branding should be incorporated as
appropriate" — which is the basis on which `fcn` keeps its own application layout. Do not assume an
exception applies; the guidance says to consult Notre Dame Creative first.

---

## 5. How these repos are built

`correll` and `web` share one architecture. Content is **pre-rendered at build time** — nothing is
fetched from JSON in the browser, so it reaches crawlers, screen readers and visitors without
JavaScript.

```
partials/    shared chrome: head, skip links, header, footer, global menu, icon sprite
pages/       one file per page: JSON front matter + that page's <main>
scripts/
  build_site.py   partials + pages -> *.html at the repo root, plus sitemap.xml and robots.txt
  render.py       renders the data-driven sections
data/        JSON refreshed by the crawl/pull scripts
```

**After editing anything in `partials/`, `pages/` or `data/`, run `python3 scripts/build_site.py`.**
CI runs it too, so a hand-edited root `*.html` will be overwritten.

| Repo | Live | Notes |
| --- | --- | --- |
| `correll` | [nd-pair.github.io/correll](https://nd-pair.github.io/correll/) | Correll Laboratory. Publications and figures from OpenAlex. |
| `web` | [nd-pair.github.io/web](https://nd-pair.github.io/web/) | PAIR. Carries a members' gate — a soft gate over public data, not a security boundary. |
| `fcn` | [nd-pair.github.io/fcn](https://nd-pair.github.io/fcn/) | Faculty Collaboration Network. A single-page D3 application; branding applies, the page layout does not. |

Images are WebP and sized; the crawl scripts emit WebP directly, so do not reintroduce PNG or JPEG.

CI workflows rebase onto the branch before pushing, because the crawls take minutes and `main` can
move while they run. Only publishable files are deployed — `pages/`, `partials/`, `scripts/` and
`data/` stay out of `_site`.

---

## 6. Before you call it done

```bash
python3 scripts/build_site.py
# then, against the built pages:
#   - axe-core on every page, in light and dark, desktop and 390px wide,
#     with any accordion or dialog both open and closed
#   - https://pagespeed.web.dev/ against the live URL, mobile and desktop
```

Local Lighthouse runs need a gzip-serving server to be meaningful — GitHub Pages compresses, and an
uncompressed local server understates performance by 20 points. Local runs also cannot load
`static.nd.edu`, so the ND fonts are missing and spacing-sensitive audits (`target-size`) report
failures that do not occur in production. Verify those against the live site.
