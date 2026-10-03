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
  Use the component the kit actually has — for video, the Video component's dialog style.
- **Never hand-pick brand colours.** `#c99700` is not Notre Dame gold. Take colours from the theme.
- **Do not recreate the marks.** The academic mark ships as SVG in the theme sprite. *"Do not display
  altered or misused Notre Dame official logos or marks."* Raster lock-ups of unknown provenance are
  not acceptable substitutes.
- To verify a component matches, render the kit's own Storybook story at the same viewport and
  compare computed styles. Differences of 1–2px are real findings.
- **Where Storybook is silent, a live Conductor site is the reference.** Some of the theme ships in
  `ndt.css` and `ndt.js` without a story — the sticky navigation bar (`#nav-fixed.header-nav-fixed`)
  is the example that bit us. Read the markup off a real site
  ([huanggroup.nd.edu](https://huanggroup.nd.edu/), [www.nd.edu](https://www.nd.edu/)) rather than
  inventing it. "Not in Storybook" does not mean "does not exist"; it means check elsewhere before
  writing your own.
- **Use the component's own variants before reaching for a different component.** Video has
  `style: "dialog"`, which plays the video over the page; the placeholder style navigates the
  visitor away to YouTube. Both are one option apart.

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
- **Text over photographs.** 16px white nav over a hero photo measured 1.0–4.1:1 against the 4.5:1
  minimum. No gradient rescues it; the fix was the Page Header variant. See section 3.
- **Gold text.** Brand gold reaches ~3:1 on white. It carries graphics, never body text.
- **`display` defeating `hidden`.** An element with `display:flex` and a `hidden` attribute stays in
  the accessibility tree.
- **Unsized images.** Every `<img>` needs `width` and `height`, or CLS suffers.

---

## 3. What the Notre Dame Creative review added

None of the following is written down at the links above; all of it came back as findings on this
site, so treat it as part of the standard.

### Dark mode is a tested state, not a bonus

NDT4 sets `color-scheme: light dark` on `:root` and writes `light-dark()` for every colour that has
to follow the visitor's preference — look at `.caption`/`figcaption` and `.card-label` in `ndt.css`.
The palette variables are **not** scheme-aware: `--gray` is `#555` in both schemes, and `#555` on
the dark page background (`#091b34`) is **2.31:1**. Four of the review's design findings were this
one mistake. So:

```css
/* wrong: a light-mode-only colour */
color: var(--gray);
/* right: the theme's own pattern */
color: light-dark(var(--gray), var(--sky-blue-dark));   /* 7.46:1 light, 10.71:1 dark */
```

The same applies to fills. A `--gray-extra-extra-light` tile is a pale rectangle on a dark page; use
`light-dark(var(--gray-extra-extra-light), var(--brand-blue))`, or no fill at all. **Run every
accessibility pass twice, once per scheme.** Watch specificity when you do: `.card-image--empty`
loses to `.card--pub .card-image`.

### Alt text has to be functional, not merely present

"Every image has an alt attribute" is not the bar; the bar is that the attribute says what the image
contributes *where it sits*. Describe the photograph. For generated imagery, say which kind it is —
a figure lifted from a paper and a render of the paper's first page need different sentences.

`alt=""` stays correct for an image whose content is already carried by text in the same link: a
video poster inside an anchor whose text is the video's title should be `alt=""`, or the link
announces itself twice. Say so when you hand the site back, so it does not come back as a finding.

### Other findings worth remembering

| Finding | Rule |
| --- | --- |
| Hero had no gradient behind the text | Text over photography is measured, never assumed — see below |
| No sticky navigation | Every page carries `#nav-fixed`; ndt.js does the rest |
| Tinted sections looked cramped | A `.section` with a `bg--` class gets **side** padding only. Add `.p-4` (utilities layer, so it wins) or `.bg--full-bleed` |
| `card--horizontal` on the PI card | Causes desktop spacing problems on a People card; the default layout is what the kit shows for a profile |
| "2026 6" in a heading | A number in a heading needs its unit — "6 publications" |
| That number went stale while filtering | Any number a control can change must be recomputed by that control |
| The OpenAlex URL printed in body text | Link the name, do not print the URL |
| An AI-generated portrait | **Open question with Notre Dame Creative.** Ownership or permission is required for every image; whether generated imagery is permitted at all is not yet answered. Flag it rather than assume |

### Text over photographs: Container, not Screen

Page Header (**Screen**) runs the image full-bleed *behind* the site header, so white navigation
lands on whatever that photograph happens to show. On one of these heroes that is a white cabinet:
**all eight** documented `fadeDirection` values measured **1.00:1** there. No gradient fixes it,
because a linear fade can only darken one corner and the title is at the opposite one.

Page Header (**Container**) is what [www.nd.edu](https://www.nd.edu/) uses. The image sits below the
header, so the navigation keeps its own background and the gradient only has to carry the page
title. With `backgroundColor: "black"` and `fadeDirection: "to-top"` — the title sits at the bottom
of the image, which is where that gradient is densest — the title measures **3.55:1** against the
3:1 large-text minimum, on both photographs, at every width from 390 to 1920.

**Measure it, do not eyeball it.** axe cannot evaluate text over a gradient over a photograph, so it
reports nothing. The method that works: screenshot the page with the text's own colour and
decorations set to `transparent`, then sample the pixels inside the rectangles the glyphs occupy
(`Range.getClientRects()` on the text nodes, not the padded element box — a padded box samples
whitespace and the link's own underline and tells you nothing). Repeat for every hero photograph,
because the crop changes with the viewport.

---

## 4. Hosting and domain

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

## 5. Review and content

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

## 6. How these repos are built

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

## 7. Before you call it done

CI runs the whole list below on every push — `scripts/a11y_check.js`, same file in all
three repos. Run it yourself before you push and you will not be surprised:

```bash
python3 scripts/build_site.py
mkdir -p _site && cp *.html styles.css app.js robots.txt sitemap.xml _site/ && cp -r assets _site/
node scripts/a11y_check.js --root _site        # add --warn-only to report without failing

# Offline (no conductor.nd.edu), serve the theme from a storybook checkout instead:
A11Y_THEME_DIR=../ndt4-storybook node scripts/a11y_check.js --root _site
```

It blocks the deploy on a push, where you are there to fix what it finds, and only warns
on the scheduled refresh — filing one GitHub issue rather than letting the site go stale
because an author's name tripped a contrast rule. **`web` is advisory even on pushes**
until PAIR's own findings are cleared; the switch is commented in its workflows.

What it covers, and the manual steps it does not:

```bash
# covered by scripts/a11y_check.js:
#   - axe-core on every page, in light and dark, desktop and 390px wide,
#     with any accordion or dialog both open and closed
#   - pixel contrast behind any text that sits over a photograph, at every
#     breakpoint and for every photograph in the rotation (axe cannot see this)
#   - drive the interactive parts: open and close a video dialog, scroll until
#     the sticky bar appears and back, type in the publication filter
#   - no duplicate element ids (the sticky bar repeats the primary navigation)

# still manual:
#   - https://pagespeed.web.dev/ against the live URL, mobile and desktop
```

The container these sites are edited from cannot reach `conductor.nd.edu`, so local runs serve the
theme from [`ndwebgroup/ndt4-storybook`](https://github.com/ndwebgroup/ndt4-storybook)
(`css/ndt.snapshot.css` and `public/js/global.js`) through a Playwright route handler
(`A11Y_THEME_DIR`). That is faithful for layout and behaviour, but **the snapshot does not apply
every dark-mode rule the live theme does.** Two surfaces measured as failures offline and are fine
against `conductor.nd.edu`:

| Surface | Offline (snapshot) | Live theme |
| --- | --- | --- |
| `.section.bg--sky-blue-light` with stat tiles | stays light, text goes light, fails | flips to dark blue, white text |
| `.dialog` (the members' gate) | panel stays white, text goes light, 1.19:1 | panel `#0c2340`, body text 13.22:1 |

So treat an offline dark-mode failure on a **themed** surface as unproven until checked against the
live theme; a failure on something `styles.css` owns is real either way. CI always uses the live
theme, so CI is the authority.

### Two measurement traps worth knowing

- **The theme animates colour.** Nav links transition over 325ms. Neutralising the text and
  screenshotting straight away captures half-faded glyphs and reports them as contrast failures, so
  the check turns off `transition` and `animation` first and then asserts the text really went
  transparent before believing any number.
- **A modal hides everything.** A site with an entry gate opens a `<dialog>` over every page in a
  fresh browser profile, and anything measured "behind" the hero is then the modal's own panel. The
  check skips hero contrast while a `dialog[open]` is present, and `--session-storage` lets the run
  through the gate so the pages themselves get measured.

Local Lighthouse runs need a gzip-serving server to be meaningful — GitHub Pages compresses, and an
uncompressed local server understates performance by 20 points. Local runs also cannot load
`static.nd.edu`, so the ND fonts are missing and spacing-sensitive audits (`target-size`) report
failures that do not occur in production. Verify those against the live site.
