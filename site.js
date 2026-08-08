// Shared nav + footer for the Correll lab site.
(function(){
  const PAGES = [
    ["index.html","Home"],
    ["publications.html","Publications"],
    ["people.html","People"],
    ["teaching.html","Teaching"],
    ["art.html","Art"],
  ];
  const here = (location.pathname.split("/").pop() || "index.html");
  const nav = document.getElementById("site-nav");
  if(nav){
    nav.className = "site";
    nav.innerHTML =
      `<div class="wrap">
        <a class="brand" href="index.html">Nikolaus Correll</a>
        <button class="navtoggle" aria-label="Menu">☰</button>
        <nav>${PAGES.map(([h,l])=>`<a href="${h}" class="${h===here?"active":""}">${l}</a>`).join("")}</nav>
      </div>`;
    const t=nav.querySelector(".navtoggle"), m=nav.querySelector("nav");
    t.addEventListener("click",()=>m.classList.toggle("open"));
  }
  const foot = document.getElementById("site-footer");
  if(foot){
    foot.className = "site";
    foot.innerHTML =
      `<div class="wrap">
        <div style="max-width:40ch">
          <div style="font-family:var(--serif);color:var(--ink);font-size:16px;font-weight:600">Correll Lab</div>
          <div>Robotic manipulation, robotic materials, and full-stack humanoids at the University of Colorado Boulder.</div>
        </div>
        <div>
          <div><a href="https://www.colorado.edu/lab/correll" target="_blank" rel="noopener">colorado.edu/lab/correll</a></div>
          <div><a href="https://introduction-to-autonomous-robots.github.io/" target="_blank" rel="noopener">Introduction to Autonomous Robots (textbook)</a></div>
          <div><a href="mailto:ncorrell@colorado.edu">ncorrell@colorado.edu</a></div>
          <div><a href="https://openalex.org/A5047458039" target="_blank" rel="noopener">Publications on OpenAlex</a></div>
        </div>
      </div>`;
  }
})();
