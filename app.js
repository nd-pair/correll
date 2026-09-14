/* Correll Laboratory — small progressive enhancements on top of the ND Web Theme.
   Everything the pages show is already in the HTML; this file only adds behaviour. */
(function () {
  "use strict";

  /* Global-menu search: scope the query to this site before handing it to Google.
     Without JavaScript the form still submits as an ordinary web search. */
  var search = document.getElementById("site-search");
  if (search) {
    search.addEventListener("submit", function () {
      var input = search.querySelector('input[name="q"]');
      if (input && input.value.indexOf("site:") === -1) {
        input.value = "site:nd-pair.github.io/correll " + input.value.trim();
      }
    });
  }

  /* Hero: cross-fade between lab photographs.
     The first image is the one in the markup, so the largest contentful paint is
     unaffected; the others are only fetched once the page has finished loading,
     and the whole thing is skipped for visitors who prefer reduced motion. */
  (function () {
    var figure = document.querySelector(".page-image[data-hero-rotate]");
    if (!figure || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var base = figure.querySelector("img");
    if (!base) return;

    var extra;
    try { extra = JSON.parse(figure.getAttribute("data-hero-rotate")); } catch (e) { return; }
    if (!Array.isArray(extra) || !extra.length) return;

    var shots = [{ src: base.getAttribute("src"), srcset: base.getAttribute("srcset") || "" }]
      .concat(extra);

    window.addEventListener("load", function () {
      var layer = new Image();
      layer.className = "hero-layer";
      layer.alt = "";
      layer.sizes = "100vw";
      layer.decoding = "async";
      figure.appendChild(layer);

      var i = 0;            // index currently on screen
      var onLayer = false;  // is the visible image the overlay, or the markup one?

      setInterval(function () {
        if (document.hidden) return;
        var next = shots[(i + 1) % shots.length];
        var target = onLayer ? base : layer;
        target.srcset = next.srcset || "";
        target.src = next.src;
        var show = function () {
          layer.classList.toggle("is-visible", !onLayer);
          onLayer = !onLayer;
          i = (i + 1) % shots.length;
        };
        if (target.complete) show();
        else target.addEventListener("load", show, { once: true });
      }, 7000);
    });
  })();

  /* Publications: filter the pre-rendered list as the visitor types. */
  var q = document.getElementById("pub-q");
  if (!q) return;
  var status = document.getElementById("pub-status");
  var years = Array.prototype.slice.call(document.querySelectorAll(".pub-year"));
  var items = Array.prototype.slice.call(document.querySelectorAll(".pub-list > li"));
  items.forEach(function (li) { li.dataset.s = li.textContent.toLowerCase().replace(/\s+/g, " "); });

  var timer;
  function apply() {
    var term = q.value.trim().toLowerCase();
    var shown = 0;
    items.forEach(function (li) {
      var hit = !term || li.dataset.s.indexOf(term) !== -1;
      li.hidden = !hit;
      if (hit) shown++;
    });
    years.forEach(function (sec) {
      sec.hidden = !sec.querySelector(".pub-list > li:not([hidden])");
    });
    if (status) {
      status.textContent = term
        ? shown + (shown === 1 ? " publication matches “" : " publications match “") + q.value.trim() + "”"
        : "";
    }
  }
  q.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(apply, 120);
  });
  q.form.addEventListener("submit", function (e) { e.preventDefault(); apply(); });
})();
