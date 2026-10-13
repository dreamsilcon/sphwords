(() => {
  const PAGE_SIZE = 8;
  const hub = document.querySelector(".compare-hub");
  if (!hub) return;

  const cards = [...hub.querySelectorAll("article.compare-card")];
  if (cards.length <= PAGE_SIZE) return;

  const sections = [...hub.querySelectorAll(".compare-section")];
  const totalPages = Math.ceil(cards.length / PAGE_SIZE);
  let page = 1;

  const topBar = document.createElement("nav");
  topBar.className = "compare-pager wrap";
  topBar.setAttribute("aria-label", "辨析分页");

  const bottomBar = topBar.cloneNode(false);
  bottomBar.className = "compare-pager wrap compare-pager-bottom";

  const heroNote = document.querySelector(".compare-hero .note");

  function pageOfCard(card) {
    const idx = cards.indexOf(card);
    return idx < 0 ? 1 : Math.floor(idx / PAGE_SIZE) + 1;
  }

  function renderPager(bar) {
    bar.innerHTML = "";
    const info = document.createElement("span");
    info.className = "compare-pager-info";
    const start = (page - 1) * PAGE_SIZE + 1;
    const end = Math.min(page * PAGE_SIZE, cards.length);
    info.textContent = `第 ${page} / ${totalPages} 页 · 显示 ${start}–${end} / 共 ${cards.length} 组`;

    const prev = document.createElement("button");
    prev.type = "button";
    prev.className = "compare-pager-btn";
    prev.textContent = "上一页";
    prev.disabled = page <= 1;
    prev.addEventListener("click", () => go(page - 1));

    const next = document.createElement("button");
    next.type = "button";
    next.className = "compare-pager-btn";
    next.textContent = "下一页";
    next.disabled = page >= totalPages;
    next.addEventListener("click", () => go(page + 1));

    const nums = document.createElement("div");
    nums.className = "compare-pager-nums";
    for (let i = 1; i <= totalPages; i++) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "compare-pager-num" + (i === page ? " is-active" : "");
      b.textContent = String(i);
      b.addEventListener("click", () => go(i));
      nums.appendChild(b);
    }

    bar.append(prev, info, nums, next);
  }

  function applyVisibility() {
    const start = (page - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    cards.forEach((card, i) => {
      card.hidden = i < start || i >= end;
    });
    for (const section of sections) {
      const visible = [...section.querySelectorAll("article.compare-card")].some((c) => !c.hidden);
      section.hidden = !visible;
      const localToc = section.querySelector(".compare-toc-local");
      if (localToc) {
        for (const li of localToc.querySelectorAll("li")) {
          const a = li.querySelector("a[href^='#']");
          if (!a) continue;
          const id = a.getAttribute("href").slice(1);
          const card = document.getElementById(id);
          li.hidden = !card || card.hidden;
        }
        localToc.hidden = ![...localToc.querySelectorAll("li")].some((li) => !li.hidden);
      }
    }
    renderPager(topBar);
    renderPager(bottomBar);
    if (heroNote) {
      heroNote.textContent = `共 ${cards.length} 组 · 每页 ${PAGE_SIZE} 组 · 第 ${page}/${totalPages} 页`;
    }
  }

  function go(nextPage, opts = {}) {
    page = Math.min(totalPages, Math.max(1, nextPage));
    applyVisibility();
    if (!opts.skipScroll) {
      const anchor = document.querySelector(".compare-hero") || topBar;
      anchor.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    const url = new URL(location.href);
    if (page === 1) url.searchParams.delete("page");
    else url.searchParams.set("page", String(page));
    history.replaceState(null, "", url);
  }

  function jumpToHash() {
    const id = location.hash.replace(/^#/, "");
    if (!id) return false;
    const card = document.getElementById(id);
    if (!card || !card.classList.contains("compare-card")) {
      // section anchors
      const section = document.getElementById(id);
      if (section && section.classList.contains("compare-section")) {
        const first = section.querySelector("article.compare-card");
        if (first) {
          go(pageOfCard(first), { skipScroll: true });
          section.scrollIntoView({ behavior: "smooth", block: "start" });
          return true;
        }
      }
      return false;
    }
    go(pageOfCard(card), { skipScroll: true });
    requestAnimationFrame(() => {
      card.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return true;
  }

  // Intercept in-page TOC links
  document.addEventListener("click", (ev) => {
    const a = ev.target.closest('a[href^="#"]');
    if (!a || a.origin !== location.origin) return;
    const id = a.hash.slice(1);
    const card = document.getElementById(id);
    if (card && card.classList.contains("compare-card")) {
      ev.preventDefault();
      history.pushState(null, "", a.hash);
      jumpToHash();
    }
  });

  window.addEventListener("hashchange", () => jumpToHash());

  const main = hub;
  main.parentNode.insertBefore(topBar, main);
  main.parentNode.insertBefore(bottomBar, main.nextSibling);

  const qPage = Number(new URLSearchParams(location.search).get("page") || 0);
  if (!jumpToHash()) {
    if (qPage >= 1 && qPage <= totalPages) go(qPage, { skipScroll: true });
    else go(1, { skipScroll: true });
  }
})();
