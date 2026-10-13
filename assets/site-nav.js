(() => {
  const el = document.querySelector("[data-site-nav]");
  if (!el) return;

  const base = el.getAttribute("data-base") || "";
  const active = el.getAttribute("data-active") || "";
  const items = [
    { id: "home", href: "index.html", label: "大厅" },
    { id: "notes", href: "notes.html", label: "笔记" },
    { id: "drill", href: "drill.html", label: "自测" },
    { id: "compare", href: "compare.html", label: "辨析" },
    { id: "account", href: "account.html", label: "账号" },
  ];

  el.innerHTML = items
    .map((item) => {
      const href = base + item.href;
      const cls = item.id === active ? "is-active" : "";
      return `<a class="${cls}" href="${href}">${item.label}</a>`;
    })
    .join("");
})();
