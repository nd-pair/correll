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
