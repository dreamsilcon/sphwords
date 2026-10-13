(() => {
  const m = location.pathname.match(/^(\/sphwords)(?=\/|$)/);
  const prefix = m ? m[1] : "";
  window.SPHWORDS_PREFIX = prefix;
  window.sphUrl = (path) => {
    const p = path.startsWith("/") ? path : `/${path}`;
    return prefix + p;
  };
})();
