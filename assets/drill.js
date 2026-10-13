(() => {
  const SCRIPT = document.currentScript;
  const SCRIPT_URL = new URL(SCRIPT?.src || "assets/drill.js", location.href);
  const INDEX_URL = new URL("drill-index.json", SCRIPT_URL).href;

  const STORAGE_KEY = "sphwords-drill-v2";
  const DEFAULT_LIST_ID = "default";

  /** @type {any[]} */
  let allCards = [];
  /** @type {Map<string, any>} */
  let cardById = new Map();
  /** @type {any[]} */
  let deck = [];
  let idx = 0;
  let revealed = false;
  let known = 0;
  let unknown = 0;
  /** @type {SpeechSynthesisVoice[]} */
  let voices = [];
  /** @type {{ email: string, id: number } | null} */
  let authUser = null;
  let syncTimer = 0;
  let syncNote = "本机浏览器";

  const $ = (sel) => document.querySelector(sel);

  function uid() {
    return `list-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  }

  function defaultLists() {
    return [{ id: DEFAULT_LIST_ID, name: "默认不熟", ids: [] }];
  }

  function normalizeState(raw) {
    const state = raw && typeof raw === "object" ? { ...raw } : {};
    if (!Array.isArray(state.lists) || !state.lists.length) state.lists = defaultLists();
    if (!state.activeListId) state.activeListId = state.lists[0].id;
    if (!state.viewListId) state.viewListId = state.activeListId;
    if (!state.sourceListId) state.sourceListId = state.activeListId;
    if (state.source !== "list") state.source = "chapter";
    state.lists = state.lists.map((l) => ({
      id: l.id || uid(),
      name: String(l.name || "未命名列表").slice(0, 40),
      ids: Array.isArray(l.ids) ? [...new Set(l.ids.map(String))] : [],
    }));
    return state;
  }

  function loadState() {
    try {
      return normalizeState(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
    } catch {
      return normalizeState({});
    }
  }

  function listWordCount(state) {
    return state.lists.reduce((n, l) => n + (l.ids?.length || 0), 0);
  }

  function scheduleServerSync(state) {
    if (!authUser) return;
    window.clearTimeout(syncTimer);
    syncTimer = window.setTimeout(async () => {
      try {
        const res = await fetch(apiUrl("/api/drill/lists"), {
          method: "PUT",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state),
        });
        if (!res.ok) throw new Error("sync failed");
        syncNote = `账号 ${authUser.email}`;
        renderAuthBar();
        renderListTable();
      } catch {
        syncNote = `账号 ${authUser.email}（同步失败，仍保存在本机）`;
        renderAuthBar();
        renderListTable();
      }
    }, 400);
  }

  function saveState(patch) {
    const next = normalizeState({ ...loadState(), ...patch });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    scheduleServerSync(next);
    return next;
  }

  function renderAuthBar() {
    const bar = $("#drill-auth-bar");
    if (!bar) return;
    if (authUser) {
      bar.innerHTML = `<span>已登录 <strong>${escapeHtml(authUser.email)}</strong> · 错词本跟账号走</span>
        <span><a href="account.html">我的账号</a> · <button type="button" class="drill-linkish" id="btn-logout">退出</button></span>`;
      $("#btn-logout")?.addEventListener("click", async () => {
        await fetch(apiUrl("/api/auth/logout"), { method: "POST", credentials: "same-origin" });
        authUser = null;
        syncNote = "本机浏览器";
        renderAuthBar();
        renderListTable();
      });
    } else {
      bar.innerHTML = `<span class="muted">未登录：错词本只在本机。登录后可跨手机/电脑同步。</span>
        <span><a href="login.html?next=drill.html">登录</a> · <a href="register.html">注册</a></span>`;
    }
  }

  function apiUrl(path) {
    return (window.sphUrl || ((p) => p))(path);
  }

  async function hydrateAuthAndLists() {
    try {
      const meRes = await fetch(apiUrl("/api/auth/me"), { credentials: "same-origin" });
      const me = await meRes.json();
      if (me.authenticated) {
        authUser = { email: me.email, id: me.id };
        const local = loadState();
        const remoteRes = await fetch(apiUrl("/api/drill/lists"), { credentials: "same-origin" });
        if (remoteRes.ok) {
          const remote = normalizeState(await remoteRes.json());
          const remoteEmpty = listWordCount(remote) === 0;
          const localHas = listWordCount(local) > 0;
          if (remoteEmpty && localHas) {
            const merged = saveState(local);
            syncNote = `账号 ${authUser.email}`;
            return merged;
          }
          localStorage.setItem(STORAGE_KEY, JSON.stringify(remote));
          syncNote = `账号 ${authUser.email}`;
          return remote;
        }
        syncNote = `账号 ${authUser.email}`;
      } else {
        authUser = null;
        syncNote = "本机浏览器";
      }
    } catch {
      // static file open / API down — keep local only
      authUser = null;
      syncNote = "本机浏览器";
    }
    return loadState();
  }

  function getList(state, id) {
    return state.lists.find((l) => l.id === id) || state.lists[0];
  }

  function speakable(word) {
    return String(word || "")
      .replace(/[/·]+/g, " ")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function pickVoice() {
    if (!voices.length && window.speechSynthesis) {
      voices = window.speechSynthesis.getVoices() || [];
    }
    const list = voices;
    return (
      list.find((v) => /en-GB/i.test(v.lang) && /female|susan|serena|martha|google/i.test(v.name)) ||
      list.find((v) => /en-GB/i.test(v.lang)) ||
      list.find((v) => /en-US/i.test(v.lang)) ||
      list.find((v) => /^en\b/i.test(v.lang)) ||
      null
    );
  }

  function speakWord(word) {
    if (!window.speechSynthesis) return;
    const text = speakable(word);
    if (!text) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const voice = pickVoice();
    if (voice) {
      u.voice = voice;
      u.lang = voice.lang;
    } else {
      u.lang = "en-GB";
    }
    u.rate = 0.92;
    u.pitch = 1;
    window.speechSynthesis.speak(u);
  }

  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function chapterOptions(cards) {
    return [...new Set(cards.map((c) => String(c.chapter)))].sort(
      (a, b) => Number(a) - Number(b)
    );
  }

  function fillListSelects(state) {
    for (const selId of ["drill-list-target", "drill-list-source", "drill-list-view"]) {
      const sel = $(`#${selId}`);
      const prev = sel.value;
      sel.innerHTML = "";
      for (const list of state.lists) {
        const opt = document.createElement("option");
        opt.value = list.id;
        opt.textContent = `${list.name}（${list.ids.length}）`;
        sel.appendChild(opt);
      }
      const preferred =
        selId === "drill-list-target"
          ? state.activeListId
          : selId === "drill-list-source"
            ? state.sourceListId
            : state.viewListId;
      sel.value = state.lists.some((l) => l.id === prev)
        ? prev
        : state.lists.some((l) => l.id === preferred)
          ? preferred
          : state.lists[0].id;
    }
  }

  function syncSourceFields() {
    const source = $("#drill-source").value;
    $("#source-chapter-fields").hidden = source !== "chapter";
    $("#source-list-fields").hidden = source !== "list";
  }

  function cardsFromList(listId) {
    const state = loadState();
    const list = getList(state, listId);
    return list.ids.map((id) => cardById.get(id)).filter(Boolean);
  }

  function filterDeck() {
    const source = $("#drill-source").value;
    if (source === "list") {
      return shuffle(cardsFromList($("#drill-list-source").value));
    }
    const ch = $("#drill-chapter").value;
    const onlyExtra = $("#drill-extra").checked;
    const includeRelated = $("#drill-related").checked;
    let list = allCards;
    if (ch !== "all") list = list.filter((c) => String(c.chapter) === ch);
    if (!includeRelated) list = list.filter((c) => c.kind !== "related");
    if (onlyExtra) list = list.filter((c) => c.extra || c.kind === "related");
    return shuffle(list);
  }

  function current() {
    return deck[idx] || null;
  }

  function addToActiveList(card) {
    if (!card) return;
    const state = loadState();
    const targetId = $("#drill-list-target").value || state.activeListId;
    const lists = state.lists.map((l) => {
      if (l.id !== targetId) return l;
      if (l.ids.includes(card.id)) return l;
      return { ...l, ids: [...l.ids, card.id] };
    });
    const next = saveState({ lists, activeListId: targetId });
    fillListSelects(next);
    renderListTable();
  }

  function removeFromList(listId, cardId) {
    const state = loadState();
    const lists = state.lists.map((l) =>
      l.id === listId ? { ...l, ids: l.ids.filter((id) => id !== cardId) } : l
    );
    const next = saveState({ lists });
    fillListSelects(next);
    renderListTable();
    return next;
  }

  function renderListTable() {
    const state = loadState();
    const viewId = $("#drill-list-view").value || state.viewListId;
    const list = getList(state, viewId);
    const body = $("#drill-table-body");
    const empty = $("#drill-table-empty");
    body.innerHTML = "";
    const cards = list.ids.map((id) => cardById.get(id)).filter(Boolean);
    $("#drill-list-count").textContent = `「${list.name}」共 ${cards.length} 词 · ${syncNote}`;
    empty.hidden = cards.length > 0;
    for (const card of cards) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${escapeHtml(card.word)}</strong></td>
        <td>${escapeHtml(card.sense)}</td>
        <td>${escapeHtml(String(card.chapter))}</td>
        <td><button type="button" class="drill-linkish" data-remove="${escapeAttr(card.id)}">移除</button></td>
      `;
      body.appendChild(tr);
    }
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

  function render() {
    const card = current();
    const face = $("#drill-face");
    const empty = $("#drill-empty");
    const actions = $("#drill-actions");
    const progress = $("#drill-progress");
    const meta = $("#drill-meta");

    if (!card) {
      face.hidden = true;
      actions.hidden = true;
      empty.hidden = false;
      progress.textContent = "0 / 0";
      meta.textContent = "";
      return;
    }

    empty.hidden = true;
    face.hidden = false;
    actions.hidden = false;
    progress.textContent = `${idx + 1} / ${deck.length}`;
    const state = loadState();
    const target = getList(state, $("#drill-list-target").value);
    meta.textContent = `认识 ${known} · 不熟 ${unknown} · 写入「${target.name}」`;

    const kind = $("#drill-kind");
    const isRelated = card.kind === "related";
    kind.hidden = !isRelated;
    kind.textContent = isRelated ? "拓展词" : "";

    $("#drill-word").textContent = card.word;
    $("#drill-ipa").textContent = revealed && card.ipa ? card.ipa : "";
    $("#drill-ipa").hidden = !(revealed && card.ipa);
    $("#drill-sense").textContent = revealed ? card.sense : "想一想这个词的意思";
    $("#drill-sense").classList.toggle("is-answer", revealed);
    $("#drill-sense").classList.toggle("is-prompt", !revealed);

    $("#btn-reveal").hidden = revealed;
    $("#btn-know").hidden = !revealed;
    $("#btn-unknown").hidden = !revealed;
  }

  function persistPrefs() {
    saveState({
      source: $("#drill-source").value,
      chapter: $("#drill-chapter").value,
      onlyExtra: $("#drill-extra").checked,
      includeRelated: $("#drill-related").checked,
      activeListId: $("#drill-list-target").value,
      sourceListId: $("#drill-list-source").value,
      viewListId: $("#drill-list-view").value,
    });
  }

  function startDeck(resetStats) {
    persistPrefs();
    syncSourceFields();
    deck = filterDeck();
    idx = 0;
    revealed = false;
    if (resetStats) {
      known = 0;
      unknown = 0;
    }
    render();
  }

  function nextCard() {
    revealed = false;
    idx += 1;
    if (idx >= deck.length) {
      deck = filterDeck();
      idx = 0;
    }
    render();
  }

  function revealCard(withSpeech) {
    if (revealed) return;
    revealed = true;
    render();
    if (withSpeech !== false) {
      const card = current();
      if (card) speakWord(card.word);
    }
  }

  function createList() {
    const name = (window.prompt("新不熟列表名称", "新的不熟列表") || "").trim().slice(0, 40);
    if (!name) return;
    const state = loadState();
    const list = { id: uid(), name, ids: [] };
    const next = saveState({
      lists: [...state.lists, list],
      activeListId: list.id,
      viewListId: list.id,
    });
    fillListSelects(next);
    $("#drill-list-target").value = list.id;
    $("#drill-list-view").value = list.id;
    persistPrefs();
    renderListTable();
    render();
  }

  function renameList() {
    const state = loadState();
    const list = getList(state, $("#drill-list-view").value);
    const name = (window.prompt("重命名列表", list.name) || "").trim().slice(0, 40);
    if (!name) return;
    const lists = state.lists.map((l) => (l.id === list.id ? { ...l, name } : l));
    const next = saveState({ lists });
    fillListSelects(next);
    renderListTable();
    render();
  }

  function deleteList() {
    const state = loadState();
    if (state.lists.length <= 1) {
      window.alert("至少保留一份不熟列表。");
      return;
    }
    const list = getList(state, $("#drill-list-view").value);
    if (!window.confirm(`删除列表「${list.name}」？其中的词不会删词库，只是不再记在这份表里。`)) {
      return;
    }
    const lists = state.lists.filter((l) => l.id !== list.id);
    const fallback = lists[0].id;
    const next = saveState({
      lists,
      activeListId: state.activeListId === list.id ? fallback : state.activeListId,
      viewListId: fallback,
      sourceListId: state.sourceListId === list.id ? fallback : state.sourceListId,
    });
    fillListSelects(next);
    renderListTable();
    if ($("#drill-source").value === "list") startDeck(true);
    else render();
  }

  async function init() {
    const state = await hydrateAuthAndLists();
    renderAuthBar();
    const res = await fetch(INDEX_URL);
    if (!res.ok) throw new Error("drill index fetch failed");
    allCards = await res.json();
    cardById = new Map(allCards.map((c) => [c.id, c]));

    const select = $("#drill-chapter");
    for (const ch of chapterOptions(allCards)) {
      const opt = document.createElement("option");
      opt.value = ch;
      opt.textContent = `第 ${ch} 章`;
      select.appendChild(opt);
    }
    if (state.chapter) select.value = state.chapter;
    $("#drill-extra").checked = Boolean(state.onlyExtra);
    $("#drill-related").checked = state.includeRelated !== false;
    $("#drill-source").value = state.source === "list" ? "list" : "chapter";

    fillListSelects(state);
    syncSourceFields();

    $("#drill-source").addEventListener("change", () => startDeck(true));
    select.addEventListener("change", () => startDeck(true));
    $("#drill-extra").addEventListener("change", () => startDeck(true));
    $("#drill-related").addEventListener("change", () => startDeck(true));
    $("#drill-list-source").addEventListener("change", () => {
      persistPrefs();
      if ($("#drill-source").value === "list") startDeck(true);
    });
    $("#drill-list-target").addEventListener("change", () => {
      persistPrefs();
      render();
    });
    $("#drill-list-view").addEventListener("change", () => {
      persistPrefs();
      renderListTable();
    });

    $("#btn-reshuffle").addEventListener("click", () => startDeck(true));
    $("#btn-new-list").addEventListener("click", createList);
    $("#btn-rename-list").addEventListener("click", renameList);
    $("#btn-delete-list").addEventListener("click", deleteList);
    $("#btn-start-view-list").addEventListener("click", () => {
      $("#drill-source").value = "list";
      $("#drill-list-source").value = $("#drill-list-view").value;
      startDeck(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    $("#drill-table-body").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-remove]");
      if (!btn) return;
      removeFromList($("#drill-list-view").value, btn.getAttribute("data-remove"));
      if ($("#drill-source").value === "list") {
        // refresh deck membership without resetting stats hard
        const cur = current();
        deck = filterDeck();
        idx = Math.min(idx, Math.max(0, deck.length - 1));
        if (cur) {
          const found = deck.findIndex((c) => c.id === cur.id);
          if (found >= 0) idx = found;
        }
        render();
      }
    });

    $("#btn-reveal").addEventListener("click", () => revealCard(true));
    $("#drill-face").addEventListener("click", (ev) => {
      if (ev.target.closest("a,button")) return;
      if (!revealed) revealCard(true);
    });
    $("#btn-speak").addEventListener("click", (ev) => {
      ev.stopPropagation();
      const card = current();
      if (card) speakWord(card.word);
    });

    $("#btn-know").addEventListener("click", () => {
      known += 1;
      const card = current();
      if (card && $("#drill-source").value === "list") {
        removeFromList($("#drill-list-source").value, card.id);
        deck = deck.filter((c) => c.id !== card.id);
        revealed = false;
        if (!deck.length) {
          deck = filterDeck();
          idx = 0;
        } else if (idx >= deck.length) {
          idx = 0;
        }
        render();
        return;
      }
      nextCard();
    });

    $("#btn-unknown").addEventListener("click", () => {
      unknown += 1;
      const card = current();
      addToActiveList(card);
      if (card && deck.length > 1) {
        const insertAt = Math.min(deck.length - 1, idx + 3 + Math.floor(Math.random() * 4));
        deck.splice(insertAt, 0, card);
      }
      nextCard();
    });

    if (window.speechSynthesis) {
      voices = window.speechSynthesis.getVoices() || [];
      window.speechSynthesis.addEventListener("voiceschanged", () => {
        voices = window.speechSynthesis.getVoices() || [];
      });
    }

    renderListTable();

    const hash = location.hash.replace(/^#/, "");
    const hashParams = new URLSearchParams(hash.includes("=") ? hash : "");
    const listFromHash = hashParams.get("list");
    if (listFromHash && state.lists.some((l) => l.id === listFromHash)) {
      $("#drill-source").value = "list";
      $("#drill-list-source").value = listFromHash;
      $("#drill-list-view").value = listFromHash;
      $("#drill-list-target").value = listFromHash;
      syncSourceFields();
      persistPrefs();
    }

    startDeck(true);

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register(new URL("sw.js", document.baseURI), { scope: "./" }).catch(() => {});
    }
  }

  init().catch(() => {
    $("#drill-empty").hidden = false;
    $("#drill-empty").textContent = "词库加载失败，请刷新重试。";
    $("#drill-face").hidden = true;
  });
})();
