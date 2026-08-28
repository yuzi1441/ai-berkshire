/* 主题预览切换器：仅用于 theme-preview.html，不影响正式看板 index.html */

const THEMES = [
  { id: "01-bloomberg", name: "Bloomberg 终端琥珀" },
  { id: "02-linear", name: "Linear 现代灰阶" },
  { id: "03-cyberpunk", name: "赛博朋克霓虹" },
  { id: "04-aurora", name: "Aurora 极光" },
  { id: "05-quant", name: "Quant 量化绿幕" },
  { id: "06-hud", name: "军用 HUD 抬头显示" },
  { id: "07-vision", name: "Vision 空间景深" },
  { id: "08-dusk", name: "暮色琥珀交易室" },
  { id: "09-swiss", name: "瑞士国际主义" },
  { id: "10-ft", name: "FT 金融时报" },
  { id: "11-banking", name: "私人银行藏蓝金" },
  { id: "12-stripe", name: "Stripe 产品蓝紫" },
  { id: "13-nordic", name: "北欧极简冰蓝" },
  { id: "14-notion", name: "Notion 文档白" },
  { id: "15-economist", name: "Economist 数据杂志" },
  { id: "16-eink", name: "墨水屏护眼" },
  { id: "17-brutal", name: "新粗野主义" },
  { id: "18-glass", name: "玻璃拟态" },
  { id: "19-chinared", name: "中式雅金宣纸" },
  { id: "20-vapor", name: "Vaporwave 合成器浪潮" },
];

const KEY = "ab-preview-theme";
const params = new URLSearchParams(location.search);
const shotMode = params.get("shot") === "1";

function resolveIndex() {
  const want = (params.get("theme") || localStorage.getItem(KEY) || "").replace(".css", "");
  const i = THEMES.findIndex((t) => t.id === want);
  return i >= 0 ? i : 0;
}

let current = resolveIndex();

function apply(i) {
  current = (i + THEMES.length) % THEMES.length;
  const t = THEMES[current];
  document.getElementById("theme-css").href = `./assets/themes/${t.id}.css`;
  localStorage.setItem(KEY, t.id);
  const url = new URL(location);
  url.searchParams.set("theme", t.id);
  history.replaceState(null, "", url);
  const label = document.getElementById("ts-name");
  if (label) label.textContent = `${String(current + 1).padStart(2, "0")} / ${THEMES.length} · ${t.name}`;
}

if (!document.getElementById("theme-css")) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.id = "theme-css";
  document.head.appendChild(link);
}
apply(current);

if (!shotMode) {
  const bar = document.createElement("div");
  bar.id = "theme-switcher";
  bar.innerHTML = `
    <button type="button" data-ts="prev" title="上一个主题 (←)">‹</button>
    <span id="ts-name"></span>
    <button type="button" data-ts="next" title="下一个主题 (→)">›</button>
    <button type="button" data-ts="grid" title="全部主题">☰ 目录</button>
  `;
  const grid = document.createElement("div");
  grid.id = "ts-grid";
  grid.hidden = true;
  grid.innerHTML = THEMES.map(
    (t, i) =>
      `<button type="button" data-ts-i="${i}"><span class="ts-num">${String(i + 1).padStart(2, "0")}</span>${t.name}</button>`,
  ).join("");
  document.body.append(bar, grid);

  apply(current);
  bar.querySelector('[data-ts="prev"]').onclick = () => apply(current - 1);
  bar.querySelector('[data-ts="next"]').onclick = () => apply(current + 1);
  const gridBtn = bar.querySelector('[data-ts="grid"]');
  gridBtn.onclick = () => {
    grid.hidden = !grid.hidden;
  };
  grid.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-ts-i]");
    if (!btn) return;
    apply(Number(btn.dataset.tsI));
    grid.hidden = true;
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") grid.hidden = true;
    const tag = document.activeElement?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (e.key === "ArrowLeft") apply(current - 1);
    if (e.key === "ArrowRight") apply(current + 1);
  });
}

const style = document.createElement("style");
style.textContent = `
#theme-switcher {
  position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%);
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; border-radius: 999px;
  background: rgba(10, 14, 20, 0.92); color: #d4dfe9;
  border: 1px solid #335061; box-shadow: 0 10px 30px rgba(0,0,0,.5);
  z-index: 9999; backdrop-filter: blur(10px);
  font-family: ui-monospace, Menlo, monospace; font-size: 12px;
}
#theme-switcher button {
  cursor: pointer; border: 1px solid #335061; background: transparent;
  color: inherit; border-radius: 999px; padding: 4px 12px; font: inherit;
}
#theme-switcher button:hover { background: rgba(255,255,255,.1); }
#ts-grid {
  position: fixed; left: 50%; bottom: 72px; transform: translateX(-50%);
  display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 6px; padding: 12px; border-radius: 14px; max-height: 70vh; overflow: auto;
  background: rgba(10, 14, 20, 0.96); border: 1px solid #335061;
  z-index: 9999; box-shadow: 0 16px 44px rgba(0,0,0,.55);
}
#ts-grid[hidden] { display: none; }
#ts-grid button {
  display: flex; gap: 8px; align-items: center; text-align: left;
  cursor: pointer; border: 1px solid #263a4d; background: transparent;
  color: #d4dfe9; border-radius: 8px; padding: 7px 10px; font-size: 12.5px;
  font-family: inherit;
}
#ts-grid button:hover { border-color: #2ee6a8; color: #fff; }
#ts-grid .ts-num { opacity: .55; font-family: ui-monospace, monospace; font-size: 11px; }
`;
document.head.appendChild(style);
