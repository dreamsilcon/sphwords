(() => {
  const SCRIPT = document.currentScript;
  const SCRIPT_URL = new URL(SCRIPT?.src || "assets/drill.js", location.href);
  const INDEX_URL = new URL("drill-index.json", SCRIPT_URL).href;

  const STORAGE_KEY = "sphwords-drill-v1";

  /** @type {any[]} */
  let allCards = [];
  /** @type {any[]} */
  let deck = [];
  let idx = 0;
  let revealed = false;
  let known = 0;
  let unknown = 0;
  /** @type {SpeechSynthesisVoice[]} */
  let voices = [];

  const $ = (sel) => document.querySelector(sel);

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

  function revealCard(withSpeech) {
    if (revealed) return;
    revealed = true;
    render();
    if (withSpeech !== false) {
      const card = current();
      if (card) speakWord(card.word);
    }
  }

  function loadState() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch {
      return {};
    }
  }

  function saveState(patch) {
    const next = { ...loadState(), ...patch };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
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
    const set = [...new Set(cards.map((c) => String(c.chapter)))].sort(
      (a, b) => Number(a) - Number(b)
    );
    return set;
  }

  function filterDeck() {
    const ch = $("#drill-chapter").value;
    const onlyExtra = $("#drill-extra").checked;
    let list = allCards;
    if (ch !== "all") list = list.filter((c) => String(c.chapter) === ch);
    if (onlyExtra) list = list.filter((c) => c.extra);
    return shuffle(list);
  }

  function current() {
    return deck[idx] || null;
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
    meta.textContent = `认识 ${known} · 不熟 ${unknown}`;

    $("#drill-word").textContent = card.word;
    $("#drill-ipa").textContent = revealed && card.ipa ? card.ipa : "";
    $("#drill-ipa").hidden = !(revealed && card.ipa);
    $("#drill-sense").textContent = revealed ? card.sense : "想一想这个词的意思";
    $("#drill-sense").classList.toggle("is-answer", revealed);
    $("#drill-sense").classList.toggle("is-prompt", !revealed);

    const extra = $("#drill-extra-hint");
    extra.hidden = !(revealed && card.extra);
    const note = $("#drill-note-link");
    note.href = card.url;
    note.hidden = !revealed;

    $("#btn-reveal").hidden = revealed;
    $("#btn-know").hidden = !revealed;
    $("#btn-unknown").hidden = !revealed;
  }

  function startDeck(resetStats) {
    deck = filterDeck();
    idx = 0;
    revealed = false;
    if (resetStats) {
      known = 0;
      unknown = 0;
    }
    saveState({
      chapter: $("#drill-chapter").value,
      onlyExtra: $("#drill-extra").checked,
    });
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

  async function init() {
    const state = loadState();
    const res = await fetch(INDEX_URL);
    if (!res.ok) throw new Error("drill index fetch failed");
    allCards = await res.json();

    const select = $("#drill-chapter");
    for (const ch of chapterOptions(allCards)) {
      const opt = document.createElement("option");
      opt.value = ch;
      opt.textContent = `第 ${ch} 章`;
      select.appendChild(opt);
    }
    if (state.chapter) select.value = state.chapter;
    $("#drill-extra").checked = Boolean(state.onlyExtra);

    select.addEventListener("change", () => startDeck(true));
    $("#drill-extra").addEventListener("change", () => startDeck(true));
    $("#btn-reshuffle").addEventListener("click", () => startDeck(true));

    $("#btn-reveal").addEventListener("click", () => revealCard(true));
    faceTap();

    $("#btn-speak").addEventListener("click", (ev) => {
      ev.stopPropagation();
      const card = current();
      if (card) speakWord(card.word);
    });

    $("#btn-know").addEventListener("click", () => {
      known += 1;
      nextCard();
    });
    $("#btn-unknown").addEventListener("click", () => {
      unknown += 1;
      // put back later in deck for another look
      const card = current();
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

    startDeck(true);

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register(new URL("sw.js", document.baseURI), { scope: "./" }).catch(() => {});
    }
  }

  function faceTap() {
    const face = $("#drill-face");
    face.addEventListener("click", (ev) => {
      if (ev.target.closest("a,button")) return;
      if (!revealed) revealCard(true);
    });
  }

  init().catch(() => {
    $("#drill-empty").hidden = false;
    $("#drill-empty").textContent = "词库加载失败，请刷新重试。";
    $("#drill-face").hidden = true;
  });
})();
