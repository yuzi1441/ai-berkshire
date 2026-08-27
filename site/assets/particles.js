/* AI Berkshire 玻璃拟态粒子特效（仅展示层，不影响正式看板）
   在 theme-preview.html 中通过 <script type="module" src="./assets/particles.js"> 启用。
   - 默认仅在 18-glass 玻璃主题下运行；
   - 加 ?fx=1 可强制在任意主题下开启，仅作预览；
   - 采用预渲染离屏 sprite + requestAnimationFrame，随窗口缩放，尊重系统“减少动态效果”。
   - 鼠标移动产生轻微视差；面板的 backdrop-filter 会把粒子作为背景虚化，形成磨砂光斑。 */

const canvas = document.createElement("canvas");
canvas.id = "ab-fx-canvas";
canvas.setAttribute("aria-hidden", "true");
Object.assign(canvas.style, {
  position: "fixed",
  inset: "0",
  width: "100%",
  height: "100%",
  zIndex: "0",
  pointerEvents: "none",
});
document.body.appendChild(canvas);
document.head.insertAdjacentHTML(
  "beforeend",
  `<style>.app-shell{position:relative;z-index:2}</style>`,
);

const ctx = canvas.getContext("2d");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const forceFx = new URLSearchParams(location.search).get("fx") === "1";
const THEME_FX = { "18-glass": "bokeh", "01-bloomberg": "bokeh" };
const themeLink = document.getElementById("theme-css");
let active = false;
let running = false;
let W = 0, H = 0, dpr = 1;
const pointer = { x: 0, y: 0 };
const target = { x: 0, y: 0 };
let bokeh = [];
let dust = [];

const HUES = [
  [216, 168, 190], // 淡紫 #d8a8be
  [183, 129, 248], // 紫 #b781f8
  [247, 114, 182], // 粉 #f772b6
  [103, 232, 249], // 青 #67e8f9
  [129, 140, 248], // 蓝紫 #818cf8
  [232, 121, 249], // 品红 #e879f9
];

function makeSprite(rgb) {
  const s = 128;
  const c = document.createElement("canvas");
  c.width = c.height = s;
  const g = c.getContext("2d");
  const grd = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grd.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.9)`);
  grd.addColorStop(0.55, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.28)`);
  grd.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
  g.fillStyle = grd;
  g.fillRect(0, 0, s, s);
  return c;
}
const sprites = HUES.map(makeSprite);

function rand(a, b) { return a + Math.random() * (b - a); }

function spawnBokeh() {
  bokeh = [];
  const count = Math.max(16, Math.round(Math.min(34, W * 0.02)));
  for (let i = 0; i < count; i++) {
    bokeh.push({
      x: rand(0, W),
      y: rand(0, H),
      r: rand(28, 130),
      vy: rand(-0.26, -0.06),       // 缓慢上浮
      sway: rand(0.2, 0.9),
      phase: rand(0, Math.PI * 2),
      alpha: rand(0.12, 0.42),
      depth: rand(0.4, 1.4),        // 视差深度
      sprite: sprites[(Math.random() * sprites.length) | 0],
    });
  }
}

function spawnDust() {
  dust = [];
  const count = Math.round(Math.min(70, W * 0.045));
  for (let i = 0; i < count; i++) {
    dust.push({
      x: rand(0, W),
      y: rand(0, H),
      r: rand(0.6, 1.9),
      vx: rand(-0.12, 0.12),
      vy: rand(-0.16, 0.05),
      tw: rand(0.6, 2.2),           // 闪烁速度
      phase: rand(0, Math.PI * 2),
      alpha: rand(0.2, 0.7),
    });
  }
}

function resize() {
  dpr = Math.min(window.devicePixelRatio || 1, 2);
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width = Math.floor(W * dpr);
  canvas.height = Math.floor(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  spawnBokeh();
  spawnDust();
}

function step(t) {
  if (!active || !running) return;
  ctx.clearRect(0, 0, W, H);
  pointer.x += (target.x - pointer.x) * 0.05;
  pointer.y += (target.y - pointer.y) * 0.05;
  const px = (pointer.x - 0.5) * 34;
  const py = (pointer.y - 0.5) * 26;

  for (const d of dust) {
    d.x += d.vx; d.y += d.vy;
    if (d.x < -4) d.x = W + 4; if (d.x > W + 4) d.x = -4;
    if (d.y < -4) d.y = H + 4; if (d.y > H + 4) d.y = -4;
    const a = d.alpha * (0.6 + 0.4 * Math.sin(t * 0.001 * d.tw + d.phase));
    ctx.globalAlpha = Math.max(0, a);
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(d.x + px * 0.15, d.y + py * 0.15, d.r, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.globalCompositeOperation = "screen";
  for (const b of bokeh) {
    b.y += b.vy;
    const wob = Math.sin(t * 0.0006 * b.sway + b.phase) * 9;
    if (b.y < -b.r) { b.y = H + b.r; b.x = rand(0, W); }
    const bx = b.x + wob + px * b.depth;
    const by = b.y + py * b.depth;
    const a = b.alpha * (0.75 + 0.25 * Math.sin(t * 0.001 + b.phase));
    ctx.globalAlpha = a;
    const s = b.r * 2;
    ctx.drawImage(b.sprite, bx - b.r, by - b.r, s, s);
  }
  ctx.globalCompositeOperation = "source-over";
  ctx.globalAlpha = 1;
  requestAnimationFrame(step);
}

function start() {
  if (active || !canvas) return;
  active = true;
  running = !reduceMotion;
  if (reduceMotion) {
    const clear = () => ctx.clearRect(0, 0, W, H);
    clear();
    for (const b of bokeh) {
      ctx.globalAlpha = b.alpha;
      ctx.drawImage(b.sprite, b.x - b.r, b.y - b.r, b.r * 2, b.r * 2);
    }
  } else {
    requestAnimationFrame(step);
  }
}

function stop() {
  active = false;
  running = false;
  if (canvas) ctx.clearRect(0, 0, W, H);
}

function desiredFx() {
  if (!themeLink) return true; // 正式看板：粒子常驻
  const href = themeLink.getAttribute("href") || "";
  const id = href.split("/").pop().replace(".css", "");
  return Boolean(forceFx || THEME_FX[id]);
}
function syncTheme() {
  if (desiredFx()) start(); else stop();
}

if (themeLink) {
  new MutationObserver(syncTheme).observe(themeLink, { attributes: true, attributeFilter: ["href"] });
}

window.addEventListener("resize", resize);
window.addEventListener("mousemove", (e) => {
  target.x = e.clientX / W;
  target.y = e.clientY / H;
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) { running = false; return; }
  if (active && !reduceMotion && !running) { running = true; requestAnimationFrame(step); }
});

resize();
syncTheme();
