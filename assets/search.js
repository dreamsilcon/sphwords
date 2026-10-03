(() => {
  const SCRIPT = document.currentScript;
  const SCRIPT_URL = new URL(SCRIPT?.src || "assets/search.js", location.href);
  const ASSETS_DIR = SCRIPT_URL.pathname.replace(/[^/]+$/, "");
  const INDEX_URL = new URL("search-index.json", SCRIPT_URL).href;
  const ROOT_HREF = ASSETS_DIR.replace(/assets\/?$/, "") || "./";

  const MAX_RESULTS = 12;
  let indexPromise = null;
  let activeIndex = -1;

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(INDEX_URL)
        .then((r) => {
          if (!r.ok) throw new Error("index fetch failed");
          return r.json();
        })
        .catch((err) => {
          indexPromise = null;
          throw err;
        });
    }
    return indexPromise;
  }

  function resolveUrl(pathWithHash) {
    return new URL(pathWithHash, new URL(ROOT_HREF, location.href)).href;
  }

  function chapterLabel(chapter) {
    return `第${chapter}章`;
  }

  function scoreEntry(entry, q) {
    const word = entry.word.toLowerCase();
    const head = (entry.head || "").toLowerCase();
    const gloss = (entry.gloss || "").toLowerCase();
    if (word === q) return 0;
    if (word.startsWith(q)) return 1;
    if (word.includes(q)) return 2;
    if (head.includes(q) || gloss.includes(q)) return 3;
    return 99;
  }

  function search(entries, query) {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return entries
      .map((e) => ({ e, s: scoreEntry(e, q) }))
      .filter((x) => x.s < 99)
      .sort((a, b) => a.s - b.s || a.e.word.localeCompare(b.e.word) || Number(a.e.chapter) - Number(b.e.chapter))
      .slice(0, MAX_RESULTS)
      .map((x) => x.e);
  }

  function highlightEntryFromHash() {
    const id = decodeURIComponent(location.hash.replace(/^#/, ""));
    if (!id) return;
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add("entry-flash");
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => el.classList.remove("entry-flash"), 1600);
  }

  function renderResults(box, results, query) {
    if (!query.trim()) {
      box.hidden = true;
      box.innerHTML = "";
      activeIndex = -1;
      return;
    }
    if (!results.length) {
      box.hidden = false;
      box.innerHTML = `<div class="search-empty">没有找到「${escapeHtml(query.trim())}」</div>`;
      activeIndex = -1;
      return;
    }
    box.hidden = false;
    box.innerHTML = results
      .map((e, i) => {
        const gloss = e.gloss ? `<span class="search-gloss">${escapeHtml(e.gloss)}</span>` : "";
        return `<a class="search-item" role="option" data-idx="${i}" href="${escapeAttr(resolveUrl(e.url))}">
          <span class="search-word">${escapeHtml(e.word)}</span>
          ${gloss}
          <span class="search-chapter">${escapeHtml(chapterLabel(e.chapter))}</span>
        </a>`;
      })
      .join("");
    activeIndex = -1;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function setActive(box, next) {
    const items = [...box.querySelectorAll(".search-item")];
    if (!items.length) return;
    activeIndex = (next + items.length) % items.length;
    items.forEach((el, i) => el.classList.toggle("is-active", i === activeIndex));
    items[activeIndex].scrollIntoView({ block: "nearest" });
  }

  function mount() {
    const headerInner = document.querySelector(".site-header .inner");
    if (!headerInner || headerInner.querySelector(".site-search")) return;

    const wrap = document.createElement("div");
    wrap.className = "site-search";
    wrap.innerHTML = `
      <label class="search-label" for="site-search-input">搜索</label>
      <input id="site-search-input" class="search-input" type="search" placeholder="搜索单词…" autocomplete="off" spellcheck="false" />
      <div class="search-results" hidden role="listbox" aria-label="搜索结果"></div>
    `;

    const nav = headerInner.querySelector(".nav-meta");
    if (nav) headerInner.insertBefore(wrap, nav);
    else headerInner.appendChild(wrap);

    const input = wrap.querySelector(".search-input");
    const box = wrap.querySelector(".search-results");
    let timer = 0;

    async function runSearch() {
      const q = input.value;
      try {
        const entries = await loadIndex();
        renderResults(box, search(entries, q), q);
      } catch {
        box.hidden = false;
        box.innerHTML = `<div class="search-empty">搜索索引加载失败</div>`;
      }
    }

    input.addEventListener("input", () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(runSearch, 80);
    });

    input.addEventListener("keydown", (ev) => {
      if (box.hidden) return;
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        setActive(box, activeIndex + 1);
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        setActive(box, activeIndex - 1);
      } else if (ev.key === "Enter") {
        const items = [...box.querySelectorAll(".search-item")];
        const target = items[activeIndex] || items[0];
        if (target) {
          ev.preventDefault();
          location.href = target.href;
        }
      } else if (ev.key === "Escape") {
        box.hidden = true;
        input.blur();
      }
    });

    document.addEventListener("click", (ev) => {
      if (!wrap.contains(ev.target)) box.hidden = true;
    });

    input.addEventListener("focus", () => {
      if (input.value.trim()) runSearch();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      mount();
      highlightEntryFromHash();
    });
  } else {
    mount();
    highlightEntryFromHash();
  }

  window.addEventListener("hashchange", highlightEntryFromHash);
})();
