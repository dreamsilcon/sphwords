(() => {
  async function loadCaptcha(boxEl, state) {
    boxEl.innerHTML = "";
    const url = (window.sphUrl || ((p) => p))("/api/auth/captcha");
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) throw new Error("验证码加载失败");
    const data = await res.json();
    state.captchaId = data.captcha_id;
    boxEl.innerHTML = data.svg;
  }

  function bindCaptcha(boxEl, state) {
    boxEl.addEventListener("click", () => {
      loadCaptcha(boxEl, state).catch((err) => {
        boxEl.textContent = "刷新失败";
        console.error(err);
      });
    });
    return loadCaptcha(boxEl, state);
  }

  function setStatus(el, text, kind) {
    el.textContent = "";
    el.className = "auth-status" + (kind ? ` ${kind}` : "");
    if (!text) return;
    if (typeof text === "string") {
      el.textContent = text;
      return;
    }
    el.appendChild(text);
  }

  window.SphAuthForms = { bindCaptcha, setStatus, loadCaptcha };
})();
