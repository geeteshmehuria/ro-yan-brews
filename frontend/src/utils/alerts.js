export function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator(); const g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.frequency.value = 880; g.gain.value = 0.15;
    o.start(); setTimeout(() => { o.stop(); ctx.close(); }, 350);
  } catch { /* sound is best-effort */ }
}

const BASE_TITLE = document.title;

/** Show `text` as the tab title until the tab is looked at (or 15 s pass). */
export function flashTitle(text) {
  document.title = text;
  const restore = () => {
    if (document.hidden) return;
    document.title = BASE_TITLE;
    document.removeEventListener("visibilitychange", restore);
  };
  document.addEventListener("visibilitychange", restore);
  setTimeout(() => { document.title = BASE_TITLE; document.removeEventListener("visibilitychange", restore); }, 15000);
}
