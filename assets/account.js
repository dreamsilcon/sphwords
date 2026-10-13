(() => {
  const $ = (sel) => document.querySelector(sel);
  const apiUrl = (path) => (window.sphUrl || ((p) => p))(path);

  /** @type {Map<string, any>} */
  let cardById = new Map();
  /** @type {any} */
  let drillState = null;

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function detailMessage(data) {
    if (!data) return "请求失败";
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((x) => x.msg || JSON.stringify(x)).join("；");
    }
    return data.message || "请求失败";
  }

  function fillListSelect() {
    const sel = $("#list-select");
    const prev = sel.value;
    sel.innerHTML = "";
    for (const list of drillState.lists || []) {
      const opt = document.createElement("option");
      opt.value = list.id;
      opt.textContent = `${list.name}（${(list.ids || []).length}）`;
      sel.appendChild(opt);
    }
    if (prev && [...sel.options].some((o) => o.value === prev)) {
      sel.value = prev;
    } else if (drillState.viewListId) {
      sel.value = drillState.viewListId;
    }
  }

  function currentList() {
    const id = $("#list-select").value;
    return (drillState.lists || []).find((l) => l.id === id) || drillState.lists?.[0];
  }

  function renderList() {
    const list = currentList();
    const body = $("#list-body");
    const empty = $("#list-empty");
    body.innerHTML = "";
    if (!list) {
      $("#list-meta").textContent = "暂无列表";
      empty.hidden = false;
      return;
    }
    const cards = (list.ids || []).map((id) => cardById.get(id)).filter(Boolean);
    const missing = (list.ids || []).length - cards.length;
    $("#list-meta").textContent =
      `「${list.name}」共 ${cards.length} 词` +
      (missing ? `（另有 ${missing} 条词库中已找不到）` : "");
    empty.hidden = cards.length > 0;
    for (const card of cards) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${escapeHtml(card.word)}</strong></td>
        <td>${escapeHtml(card.sense || "")}</td>
        <td>${escapeHtml(String(card.chapter ?? ""))}</td>
        <td><button type="button" class="drill-linkish" data-remove="${escapeHtml(card.id)}">移除</button></td>
      `;
      body.appendChild(tr);
    }
    const drillBtn = $("#btn-drill-list");
    drillBtn.href = `drill.html#list=${encodeURIComponent(list.id)}`;
  }

  async function removeFromList(cardId) {
    const list = currentList();
    if (!list) return;
    list.ids = (list.ids || []).filter((id) => id !== cardId);
    const res = await fetch(apiUrl("/api/drill/lists"), {
      method: "PUT",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(drillState),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      window.alert(detailMessage(data));
      return;
    }
    drillState = await res.json();
    fillListSelect();
    $("#list-select").value = list.id;
    renderList();
  }

  async function init() {
    const meRes = await fetch(apiUrl("/api/auth/me"), { credentials: "same-origin" });
    const me = await meRes.json();
    if (!me.authenticated) {
      location.href = `login.html?next=${encodeURIComponent("account.html")}`;
      return;
    }
    $("#account-email").textContent = me.email;

    const indexUrl = new URL("assets/drill-index.json", document.baseURI).href;
    const [indexRes, listsRes] = await Promise.all([
      fetch(indexUrl),
      fetch(apiUrl("/api/drill/lists"), { credentials: "same-origin" }),
    ]);
    if (!listsRes.ok) {
      $("#list-meta").textContent = "错题本加载失败，请重新登录后再试。";
      return;
    }
    const cards = await indexRes.json();
    cardById = new Map(cards.map((c) => [c.id, c]));
    drillState = await listsRes.json();
    fillListSelect();
    renderList();
  }

  $("#list-select").addEventListener("change", renderList);
  $("#list-body").addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-remove]");
    if (!btn) return;
    removeFromList(btn.getAttribute("data-remove"));
  });

  $("#btn-logout").addEventListener("click", async () => {
    await fetch(apiUrl("/api/auth/logout"), { method: "POST", credentials: "same-origin" });
    location.href = "login.html";
  });

  $("#pw-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const status = $("#pw-status");
    const btn = $("#pw-btn");
    const p1 = $("#newpw").value;
    const p2 = $("#newpw2").value;
    if (p1 !== p2) {
      SphAuthForms.setStatus(status, "两次输入的新密码不一致", "err");
      return;
    }
    btn.disabled = true;
    SphAuthForms.setStatus(status, "提交中…");
    try {
      const res = await fetch(apiUrl("/api/auth/change-password"), {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: $("#current").value,
          new_password: p1,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data));
      SphAuthForms.setStatus(status, data.message || "密码已更新", "ok");
      $("#pw-form").reset();
    } catch (err) {
      SphAuthForms.setStatus(status, err.message || String(err), "err");
    } finally {
      btn.disabled = false;
    }
  });

  init().catch(() => {
    $("#account-email").textContent = "加载失败";
  });
})();
