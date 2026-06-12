/* lumi icon set — one line-icon family (lucide-style geometry), 24px grid,
   1.75 stroke, currentColor. Used at 14–18px throughout. */
/* global html */

const ICON_PATHS = {
  // superpowers
  award: [["c", 12, 8, 6], ["p", "M15.5 12.9 17 22l-5-3-5 3 1.5-9.1"]],
  sliders: [["l", 21, 4, 14, 4], ["l", 10, 4, 3, 4], ["l", 21, 12, 12, 12], ["l", 8, 12, 3, 12],
            ["l", 21, 20, 16, 20], ["l", 12, 20, 3, 20], ["l", 14, 2, 14, 6], ["l", 8, 10, 8, 14], ["l", 16, 18, 16, 22]],
  heart: [["p", "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.51 4.04 3 5.5l7 7Z"]],
  "trending-up": [["pl", "22 7 13.5 15.5 8.5 10.5 2 17"], ["pl", "16 7 22 7 22 13"]],
  zap: [["p", "M13 2 3 14h9l-1 8 10-12h-9l1-8z"]],
  users: [["p", "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"], ["c", 9, 7, 4],
          ["p", "M22 21v-2a4 4 0 0 0-3-3.87"], ["p", "M16 3.13a4 4 0 0 1 0 7.75"]],
  "user-plus": [["p", "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"], ["c", 9, 7, 4],
                ["l", 19, 8, 19, 14], ["l", 22, 11, 16, 11]],
  flag: [["p", "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"], ["l", 4, 22, 4, 15]],
  target: [["c", 12, 12, 10], ["c", 12, 12, 6], ["c", 12, 12, 2]],
  // signal lenses + category glyphs (2026-06-12 dashboard polish)
  coins: [["c", 8, 8, 6], ["p", "M18.09 10.37A6 6 0 1 1 10.34 18"], ["p", "M7 6h1v4"],
          ["p", "m16.71 13.88.7.71-2.82 2.82"]],
  magnet: [["p", "m6 15-4-4 6.75-6.77a7.79 7.79 0 0 1 11 11L13 22l-4-4 6.39-6.36a2.14 2.14 0 0 0-3-3L6 15"],
           ["p", "m5 8 4 4"], ["p", "m12 15 4 4"]],
  anchor: [["c", 12, 5, 3], ["l", 12, 22, 12, 8], ["p", "M5 12H2a10 10 0 0 0 20 0h-3"]],
  sun: [["c", 12, 12, 4], ["l", 12, 2, 12, 4], ["l", 12, 20, 12, 22], ["l", 4.9, 4.9, 6.3, 6.3],
        ["l", 17.7, 17.7, 19.1, 19.1], ["l", 2, 12, 4, 12], ["l", 20, 12, 22, 12],
        ["l", 6.3, 17.7, 4.9, 19.1], ["l", 19.1, 4.9, 17.7, 6.3]],
  refresh: [["p", "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"], ["p", "M21 3v5h-5"],
            ["p", "M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"], ["p", "M8 16H3v5"]],
  // shell / actions
  home: [["p", "m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"], ["p", "M9 22V12h6v10"]],
  star: [["p", "M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.77 5.82 21 7 14.14l-5-4.87 6.91-1.01L12 2z"]],
  "list-checks": [["p", "m3 17 2 2 4-4"], ["p", "m3 7 2 2 4-4"], ["l", 13, 6, 21, 6], ["l", 13, 12, 21, 12], ["l", 13, 18, 21, 18]],
  "file-text": [["p", "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"], ["p", "M14 2v4a2 2 0 0 0 2 2h4"],
                ["l", 8, 13, 16, 13], ["l", 8, 17, 16, 17]],
  table: [["p", "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"],
          ["l", 12, 3, 12, 21], ["l", 3, 9, 21, 9], ["l", 3, 15, 21, 15]],
  pencil: [["p", "M12 20h9"], ["p", "M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"]],
  link: [["p", "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"],
         ["p", "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"]],
  "sliders-v": [["l", 4, 21, 4, 14], ["l", 4, 10, 4, 3], ["l", 12, 21, 12, 12], ["l", 12, 8, 12, 3],
                ["l", 20, 21, 20, 16], ["l", 20, 12, 20, 3], ["l", 1, 14, 7, 14], ["l", 9, 8, 15, 8], ["l", 17, 16, 23, 16]],
  "book-open": [["p", "M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"], ["p", "M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"]],
  "log-out": [["p", "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"], ["pl", "16 17 21 12 16 7"], ["l", 21, 12, 9, 12]],
  sparkle: [["p", "M12 3l-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3Z"]],
  lock: [["p", "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z"], ["p", "M7 11V7a5 5 0 0 1 10 0v4"]],
  search: [["c", 11, 11, 8], ["p", "m21 21-4.3-4.3"]],
  shield: [["p", "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"]],
  pin: [["p", "M12 17v5"], ["p", "M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16h14v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1z"]],
  info: [["c", 12, 12, 10], ["l", 12, 16, 12, 12], ["l", 12, 8, 12.01, 8]],
  download: [["p", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"], ["pl", "7 10 12 15 17 10"], ["l", 12, 15, 12, 3]],
  copy: [["p", "M8 8h12v12a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2z"], ["p", "M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"]],
  "arrow-up-right": [["l", 7, 17, 17, 7], ["pl", "7 7 17 7 17 17"]],
  maximize: [["pl", "15 3 21 3 21 9"], ["pl", "9 21 3 21 3 15"], ["l", 21, 3, 14, 10], ["l", 3, 21, 10, 14]],
  close: [["l", 18, 6, 6, 18], ["l", 6, 6, 18, 18]],
};

window.Icon = function ({ name, size = 16, strokeWidth = 1.75, style }) {
  const parts = ICON_PATHS[name];
  if (!parts) return null;
  return html`
    <svg width=${size} height=${size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width=${strokeWidth} stroke-linecap="round" stroke-linejoin="round"
      style=${{ flexShrink: 0, ...(style || {}) }} aria-hidden="true">
      ${parts.map(([kind, ...a], i) => {
        if (kind === "p") return html`<path key=${i} d=${a[0]} />`;
        if (kind === "pl") return html`<polyline key=${i} points=${a[0]} />`;
        if (kind === "c") return html`<circle key=${i} cx=${a[0]} cy=${a[1]} r=${a[2]} />`;
        if (kind === "l") return html`<line key=${i} x1=${a[0]} y1=${a[1]} x2=${a[2]} y2=${a[3]} />`;
        return null;
      })}
    </svg>`;
};

/* one icon per superpower — same family, same weight */
window.SP_ICON = {
  Reward: "award", Processes: "sliders", Wellbeing: "heart", Growth: "trending-up",
  Capability: "zap", Inclusivity: "users", Attract: "user-plus", Leadership: "flag",
  Purpose: "target", Change: "refresh",
};

/* skeleton card matching the real card skeleton — no layout shift */
window.SkeletonCard = function () {
  return html`
    <div class="card skel-card" aria-hidden="true">
      <div class="skel" style=${{ height: "16px", width: "75%" }}></div>
      <div class="skel" style=${{ height: "16px", width: "45%" }}></div>
      <div class="skel" style=${{ height: "20px", width: "55%", marginTop: "4px" }}></div>
      <div class="skel" style=${{ height: "var(--chart-h)", marginTop: "8px" }}></div>
      <div class="skel" style=${{ height: "12px", width: "90%", marginTop: "auto" }}></div>
    </div>`;
};

window.SkeletonGrid = function ({ count = 6 }) {
  return html`<div class="bench-grid">${Array.from({ length: count }, (_, i) => html`<${SkeletonCard} key=${i} />`)}</div>`;
};
