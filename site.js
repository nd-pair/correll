// Shared nav + footer for the Correll site. Mirrors the PAIR site's chrome.
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
    nav.className = "nav";
    nav.innerHTML =
      `<div class="wrap">
        <a class="brand" href="index.html"><span class="dot"></span>Nikolaus Correll</a>
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
        <div style="max-width:42ch">
          <div class="brand" style="font-family:var(--serif);font-weight:600">Nikolaus Correll</div>
          <div style="margin-top:6px">Viola D. Hank Professor of Aerospace and Mechanical Engineering, University of Notre Dame. Robotic manipulation, robotic materials, and full-stack humanoids.</div>
        </div>
        <div style="display:grid;gap:5px">
          <div><a href="https://nd-pair.github.io/web/" target="_blank" rel="noopener">Physical AI &amp; Robotics Initiative</a></div>
          <div><a href="https://introduction-to-autonomous-robots.github.io/" target="_blank" rel="noopener">Introduction to Autonomous Robots (textbook)</a></div>
          <div><a href="https://openalex.org/A5047458039" target="_blank" rel="noopener">Publications on OpenAlex</a></div>
          <div><a href="mailto:nikolaus.correll@gmail.com">nikolaus.correll@gmail.com</a></div>
        </div>
      </div>
      <div class="wrap" style="margin-top:24px"><small>© Nikolaus Correll · University of Notre Dame</small></div>`;
  }
})();
