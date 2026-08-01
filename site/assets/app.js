const repositoryUrl = "https://github.com/yuzi1441/ai-berkshire/blob/main/";
const TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q=";
const LIVE_INTERVAL_MS = 45_000;
const SNAPSHOT_INTERVAL_MS = 180_000;

const state = {
  decisions: [],
  quotes: new Map(),
  selectedKey: null,
  view: "decision",
  market: "all",
  action: "all",
  trackingFilter: "all",
  sort: "buy_advice",
  detailTab: "valuation",
  quoteMode: "idle", // live | snapshot | idle | error
  quoteUpdatedAt: null,
  liveTimer: null,
  snapshotTimer: null,
  focusIndex: -1,
};

const els = {
  rows: document.querySelector("#decision-rows"),
  decisionTable: document.querySelector("#decision-table"),
  decisionHead: document.querySelector("#decision-head"),
  summary: document.querySelector("#summary"),
  status: document.querySelector("#data-status"),
  companyFilter: document.querySelector("#company-filter"),
  sortSelect: document.querySelector("#sort-select"),
  clearFilters: document.querySelector("#clear-filters"),
  marketChips: document.querySelector("#market-chips"),
  actionChips: document.querySelector("#action-chips"),
  viewTabs: document.querySelector("#view-tabs"),
  trackingFilterRow: document.querySelector("#tracking-filter-row"),
  trackingCount: document.querySelector("#tracking-count"),
  detailPanel: document.querySelector("#detail-panel"),
  detailTitle: document.querySelector("#detail-title"),
  detailSub: document.querySelector("#detail-sub"),
  detailKicker: document.querySelector("#detail-kicker"),
  detailBody: document.querySelector("#detail-body"),
  detailClose: document.querySelector("#detail-close"),
  detailReport: document.querySelector("#detail-report"),
  detailCopy: document.querySelector("#detail-copy-link"),
  workspace: document.querySelector("#workspace"),
  liveDot: document.querySelector("#live-dot"),
  liveText: document.querySelector("#live-text"),
  refreshQuotes: document.querySelector("#refresh-quotes"),
  toast: document.querySelector("#toast"),
  emptyState: document.querySelector("#empty-state"),
};

function trackingForItem(item) {
  const tracking = item?.post_buy_tracking;
  return tracking && tracking.status !== "not_tracked" ? tracking : null;
}

function trackingStatusLabel(status) {
  return { holding: "跟踪中", paused: "已暂停", closed: "已结束" }[status] || "未建立";
}

function thesisStatusLabel(status) {
  return {
    not_established: "未建立",
    healthy: "健康",
    borderline: "边际弱化",
    damaged: "受损",
    broken: "破裂",
  }[status] || "待复核";
}

function trackingStatusClass(status) {
  return {
    holding: "tracking-active",
    paused: "tracking-paused",
    closed: "tracking-closed",
    healthy: "tracking-healthy",
    borderline: "tracking-borderline",
    damaged: "tracking-damaged",
    broken: "tracking-broken",
  }[status] || "tracking-muted";
}

function trackingAlertLevel(tracking) {
  const alerts = tracking?.alerts || [];
  if (alerts.some((alert) => alert.severity === "critical")) return "critical";
  if (alerts.length) return "warning";
  return "none";
}

function trackingNeedsReview(tracking) {
  return Boolean((tracking?.alerts || []).some((alert) => ["review_due", "thesis_review"].includes(alert.kind)));
}

function trackingReviewLabel(tracking) {
  if (!tracking?.next_review_date) return "未设置";
  const due = (tracking.alerts || []).find((alert) => alert.kind === "review_due");
  if (due?.severity === "critical") return `${tracking.next_review_date} · 已到期`;
  if (due?.severity === "warning") return `${tracking.next_review_date} · 即将到期`;
  return tracking.next_review_date;
}

function appendTrackingBadge(parent, text, className) {
  const badge = document.createElement("span");
  badge.className = `tracking-badge ${className || ""}`;
  badge.textContent = text;
  parent.append(badge);
  return badge;
}

function marketBadgeClass(market) {
  return {
    "A股": "mkt-a",
    "港股": "mkt-hk",
    "美股": "mkt-us",
  }[market] || "mkt-unknown";
}

function decisionClass(action) {
  return {
    买入: "decision-buy",
    分批买入: "decision-installment",
    持有: "decision-hold",
    观察: "decision-watch",
    "减仓/卖出": "decision-sell",
  }[action] || "";
}


function stanceActionLabel(stance) {
  const blob = `${stance?.action || ""} ${stance?.price_range || ""} ${stance?.note || ""}`;
  if (/立即卖出|大幅减仓|建议卖出|建议减仓|清仓|锁定利润/.test(blob) && !/卖出信号|加仓信号/.test(blob)) {
    return "减仓/卖出";
  }
  if (/坚决回避|明确回避|不建议买入|不宜买入|暂不买入|远离|坚决不买|不要追|观望为主|继续观察|保持观望|建议观望|放入观察|等待更好|等待验证|观察池|回避/.test(blob)
      && !/买入|建仓|配置/.test(blob)) {
    return "观察";
  }
  if (/观望|等待|观察|不追/.test(blob) && !/买入|建仓|配置|试探|试错|小仓/.test(blob)) {
    return "观察";
  }
  if (/持有但不加|继续持有|持有观望|持有/.test(blob) && !/买入|建仓|配置|试探|试错|小仓/.test(blob)) {
    return "持有";
  }
  if (/强烈买入|积极买入|重点买入/.test(blob)) return "买入";
  if (/分批买入|分批建仓|可建仓|可配置|小仓|试探|试错|可参与|开始建仓|可分批|优先买入|重仓候选|可开始/.test(blob)) {
    return "分批买入";
  }
  if (/买入|建仓|配置/.test(blob)) return "分批买入";
  if (/持有/.test(blob)) return "持有";
  if (/观望|观察|等待|回避/.test(blob)) return "观察";
  return "";
}

function itemActionSet(item) {
  const set = new Set();
  if (item.action) set.add(item.action);
  for (const stance of item.investor_stances || []) {
    const label = stanceActionLabel(stance);
    if (label) set.add(label);
  }
  return set;
}

function renderStanceStack(item, { compact = true } = {}) {
  const stances = item.investor_stances || [];
  const wrap = document.createElement("div");
  wrap.className = compact ? "stance-stack" : "stance-stack stance-stack-detail";
  if (!stances.length) {
    const badge = document.createElement("span");
    badge.className = `decision ${decisionClass(item.action)}`;
    badge.textContent = item.action || "未分类";
    wrap.append(badge);
    return wrap;
  }
  for (const stance of stances) {
    const row = document.createElement("div");
    row.className = "stance-row";
    const coarse = stanceActionLabel(stance);
    const tag = document.createElement("span");
    tag.className = `stance-tag ${decisionClass(coarse)}`;
    tag.textContent = String(stance.stance || "").replace("型", "");
    const body = document.createElement("div");
    body.className = "stance-body";
    const action = document.createElement("div");
    action.className = "stance-action";
    action.textContent = stance.action || coarse || "见报告";
    body.append(action);
    if (stance.price_range) {
      const price = document.createElement("div");
      price.className = "stance-price";
      price.textContent = stance.price_range;
      body.append(price);
    }
    row.append(tag, body);
    wrap.append(row);
  }
  return wrap;
}

function itemKey(item) {
  return `${item.ticker || ""}::${item.company}`;
}

function showToast(message) {
  els.toast.hidden = false;
  els.toast.textContent = message;
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    els.toast.hidden = true;
  }, 2200);
}

function tencentSymbol(ticker, market) {
  if (!ticker) return null;
  const raw = String(ticker).trim().toUpperCase();
  if (raw.endsWith(".HK") || market === "港股") {
    const code = raw.replace(/\.HK$/, "");
    return /^\d+$/.test(code) ? `hk${code.padStart(5, "0")}` : null;
  }
  if (raw.endsWith(".SH")) return `sh${raw.slice(0, -3)}`;
  if (raw.endsWith(".SZ")) return `sz${raw.slice(0, -3)}`;
  if (raw.endsWith(".BJ")) return `bj${raw.slice(0, -3)}`;
  if (/^\d{6}$/.test(raw)) return raw.startsWith("6") || raw.startsWith("9") ? `sh${raw}` : `sz${raw}`;
  return null;
}


function parseStanceBand(stance) {
  const text = [stance && stance.price_range, stance && stance.action, stance && stance.note].filter(Boolean).join(" ");
  if (!text.trim()) return null;
  const cleaned = text.replace(/,/g, "");
  let currency = null;
  if (/(?:HK\$|HKD|港元)/i.test(cleaned)) currency = "HKD";
  else if (/(?:US\$|USD|美元)/i.test(cleaned)) currency = "USD";
  else if (/(?:₩|KRW|韩元)/i.test(cleaned)) currency = "KRW";
  else if (/(?:CNY|人民币|元)/i.test(cleaned)) currency = "CNY";
  // A bare number has no dependable comparison basis: it may be a multiple,
  // a target in another market, or a value quoted in a table header.
  if (!currency) return null;
  const range = cleaned.match(/(?:不高于|不低于|低于|高于|≤|≥|<|>|约)?\s*(?:HK\$|US\$|₩)?\s*(\d+(?:\.\d+)?)\s*[-—~至到]\s*(\d+(?:\.\d+)?)/);
  if (range) {
    const a = Number(range[1]);
    const b = Number(range[2]);
    if (Number.isFinite(a) && Number.isFinite(b)) return { min: Math.min(a, b), max: Math.max(a, b), mode: "range", currency: currency };
  }
  const ceiling = cleaned.match(/(?:不高于|不超过|低于|以下|≤|<=|<)\s*(?:HK\$|US\$|₩)?\s*(\d+(?:\.\d+)?)/) || cleaned.match(/(?:HK\$|US\$|₩)?\s*(\d+(?:\.\d+)?)\s*(?:元|港元|美元)?\s*(?:以下|以内)/);
  if (ceiling) {
    const max = Number(ceiling[1]);
    if (Number.isFinite(max)) return { min: null, max: max, mode: "ceiling", currency: currency };
  }
  const floor = cleaned.match(/(?:不低于|高于|≥|>=|>)\s*(?:HK\$|US\$|₩)?\s*(\d+(?:\.\d+)?)/);
  if (floor) {
    const min = Number(floor[1]);
    if (Number.isFinite(min)) return { min: min, max: null, mode: "floor", currency: currency };
  }
  const single = cleaned.match(/(?:HK\$|US\$|₩)?\s*(\d+(?:\.\d+)?)\s*(?:元|港元|美元)?/);
  if (single && /买入|建仓|分批|试探|试错|重仓|配置|以下|不高于|等待|观察|考虑/.test(cleaned)) {
    const max = Number(single[1]);
    if (Number.isFinite(max)) return { min: null, max: max, mode: "ceiling", currency: currency };
  }
  return null;
}

function priceFitsBand(price, band, quote) {
  if (!band || !Number.isFinite(price)) return false;
  if (band.currency !== quote?.currency) return false;
  if (band.mode === "range") return price <= band.max + 1e-9;
  if (band.mode === "ceiling") return price <= band.max + 1e-9;
  if (band.mode === "floor") return band.min == null || price >= band.min - 1e-9;
  return false;
}

function buyAdviceForItem(item, quote) {
  const price = quote && quote.price;
  const stances = (item && item.investor_stances) || [];
  if (!stances.length) {
    return { key: "unknown", label: "无分层价", detail: "报告未给出激进/稳健/保守价格带", rank: 0, className: "unknown-zone" };
  }
  if (!Number.isFinite(price)) {
    return { key: "unknown", label: "待比价", detail: "等待现价后对照分层价格带", rank: 0, className: "unknown-zone" };
  }
  const order = ["保守型", "稳健型", "激进型"];
  const byName = {};
  for (const s of stances) {
    byName[s.stance] = Object.assign({}, s, { band: parseStanceBand(s) });
  }
  const usable = order.map(function (name) { return byName[name]; }).filter(function (s) {
    return s && s.band && s.band.currency === quote.currency && Number.isFinite(s.band.max != null ? s.band.max : s.band.min);
  });
  if (!usable.length) {
    return { key: "unknown", label: "待比价", detail: "价格带缺少可核对的币种或单位", rank: 0, className: "unknown-zone" };
  }
  let matched = null;
  for (const name of order) {
    const s = byName[name];
    if (s && s.band && priceFitsBand(price, s.band, quote)) {
      matched = name;
      break;
    }
  }
  const fmt = function (n) {
    return Number.isFinite(n) ? Number(n).toFixed(2).replace(/\.00$/, "") : "-";
  };
  const priceText = fmt(price);
  if (!matched) {
    const tops = usable.map(function (s) { return s.band.max; }).filter(function (n) { return Number.isFinite(n); });
    const top = tops.length ? Math.max.apply(null, tops) : null;
    return {
      key: "no",
      label: "不适合买入",
      detail: top != null ? ("现价 " + priceText + " 高于激进上限约 " + fmt(top)) : ("现价 " + priceText + " 不在任一买入带"),
      rank: 1,
      className: "hot-zone",
      matched: null,
      price: price
    };
  }
  const labels = {
    "保守型": { label: "适合保守买入", className: "buy-zone", rank: 4 },
    "稳健型": { label: "适合稳健买入", className: "hold-zone", rank: 3 },
    "激进型": { label: "适合激进买入", className: "watch-zone", rank: 2 }
  };
  const meta = labels[matched];
  const band = byName[matched].band;
  let bandText = "";
  if (band.mode === "range") bandText = fmt(band.min) + "-" + fmt(band.max);
  else if (band.mode === "ceiling") bandText = "≤" + fmt(band.max);
  else if (band.mode === "floor") bandText = "≥" + fmt(band.min);
  let extra = "";
  if (matched === "保守型") extra = "（亦满足稳健/激进价格带）";
  else if (matched === "稳健型" && byName["激进型"] && byName["激进型"].band && priceFitsBand(price, byName["激进型"].band, quote)) {
    extra = "（亦满足激进价格带）";
  }
  return {
    key: matched === "保守型" ? "conservative" : matched === "稳健型" ? "balanced" : "aggressive",
    label: meta.label,
    detail: "现价 " + priceText + " · " + matched.replace("型", "") + "带 " + bandText + extra,
    rank: meta.rank,
    className: meta.className,
    matched: matched,
    price: price,
    band: band
  };
}

function renderBuyAdviceCell(item, quote) {
  const advice = buyAdviceForItem(item, quote);
  const wrap = document.createElement("div");
  wrap.className = "buy-advice";
  const badge = document.createElement("span");
  badge.className = "zone-badge " + advice.className;
  badge.textContent = advice.label;
  const sub = document.createElement("div");
  sub.className = "buy-advice-detail";
  sub.textContent = advice.detail;
  wrap.append(badge, sub);
  return wrap;
}

function parsePriceNumbers(text) {
  if (!text) return [];
  const cleaned = String(text).replace(/,/g, "");
  const matches = cleaned.match(/\d+(?:\.\d+)?/g) || [];
  return matches.map(Number).filter((n) => Number.isFinite(n) && n > 0 && n < 1_000_000);
}

function formatPrice(quote) {
  if (!quote || !Number.isFinite(quote.price)) return "—";
  const prefix = quote.currency === "HKD" ? "HK$" : quote.currency === "USD" ? "US$" : "";
  return `${prefix}${Number(quote.price).toFixed(2)}`;
}

function formatChange(quote) {
  if (!quote || !Number.isFinite(quote.change_pct)) return { text: "—", className: "flat" };
  const pct = quote.change_pct;
  const sign = pct > 0 ? "+" : "";
  return {
    text: `${sign}${pct.toFixed(2)}%`,
    className: pct > 0.005 ? "up" : pct < -0.005 ? "down" : "flat",
  };
}

function actionRank(action) {
  return { 买入: 5, 分批买入: 4, 持有: 3, 观察: 2, "减仓/卖出": 1 }[action] || 0;
}

function filteredDecisions() {
  const phrase = els.companyFilter.value.trim().toLocaleLowerCase();
  let list = state.decisions.filter((item) => {
    const marketMatch = state.market === "all" || item.market === state.market;
    const tracking = trackingForItem(item);
    const adviceMatch = state.action === "all"
      || buyAdviceForItem(item, state.quotes.get(item.ticker)).key === state.action;
    const trackingMatch = state.view !== "tracking"
      || (tracking && (
        state.trackingFilter === "all"
        || (state.trackingFilter === "alert" && trackingAlertLevel(tracking) !== "none")
        || (state.trackingFilter === "review" && trackingNeedsReview(tracking))
      ));
    const searchable = `${item.company} ${item.ticker || ""} ${item.title || ""}`.toLocaleLowerCase();
    return marketMatch
      && (state.view === "tracking" ? true : adviceMatch)
      && trackingMatch
      && (!phrase || searchable.includes(phrase));
  });

  list = [...list].sort((a, b) => {
    if (state.view === "tracking") {
      const aa = trackingForItem(a);
      const bb = trackingForItem(b);
      const alertRank = { critical: 3, warning: 2, none: 1 };
      const alertDelta = (alertRank[trackingAlertLevel(bb)] || 0) - (alertRank[trackingAlertLevel(aa)] || 0);
      if (alertDelta) return alertDelta;
      return String(aa?.next_review_date || "9999-12-31").localeCompare(String(bb?.next_review_date || "9999-12-31"));
    }
    if (state.sort === "action") {
      const d = actionRank(b.action) - actionRank(a.action);
      if (d) return d;
      return a.company.localeCompare(b.company, "zh");
    }
    if (state.sort === "buy_advice") {
      const aa = buyAdviceForItem(a, state.quotes.get(a.ticker));
      const bb = buyAdviceForItem(b, state.quotes.get(b.ticker));
      const d = (bb.rank || 0) - (aa.rank || 0);
      if (d) return d;
      return a.company.localeCompare(b.company, "zh");
    }
    if (state.sort === "change") {
      const ca = state.quotes.get(a.ticker)?.change_pct;
      const cb = state.quotes.get(b.ticker)?.change_pct;
      const na = Number.isFinite(ca) ? ca : -999;
      const nb = Number.isFinite(cb) ? cb : -999;
      if (nb !== na) return nb - na;
      return a.company.localeCompare(b.company, "zh");
    }
    if (state.sort === "cutoff") {
      return String(b.data_cutoff || "").localeCompare(String(a.data_cutoff || ""));
    }
    return a.company.localeCompare(b.company, "zh");
  });
  return list;
}

function selectedItem() {
  if (!state.selectedKey) return null;
  return state.decisions.find((item) => itemKey(item) === state.selectedKey) || null;
}

function setLiveStatus(mode, text) {
  state.quoteMode = mode;
  els.liveText.textContent = text;
  els.liveDot.classList.remove("on", "warn", "off");
  if (mode === "live") els.liveDot.classList.add("on");
  else if (mode === "snapshot") els.liveDot.classList.add("warn");
  else els.liveDot.classList.add("off");
}

function isLikelyMarketOpen() {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Shanghai",
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(new Date());
    const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
    const weekday = map.weekday;
    if (["Sat", "Sun"].includes(weekday)) return false;
    const minutes = Number(map.hour) * 60 + Number(map.minute);
    // A: 9:30-11:30, 13:00-15:00; H: 9:30-12:00, 13:00-16:00 -> union 9:30-16:00 with lunch gap ignored for simplicity of polling
    return (minutes >= 9 * 60 + 15 && minutes <= 11 * 60 + 45) || (minutes >= 12 * 60 + 50 && minutes <= 16 * 60 + 10);
  } catch {
    return false;
  }
}

function loadScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = true;
    script.onload = () => {
      script.remove();
      resolve();
    };
    script.onerror = () => {
      script.remove();
      reject(new Error(`quote script failed: ${url}`));
    };
    document.head.append(script);
  });
}

function parseTencentFieldString(raw, meta) {
  if (!raw) return null;
  const fields = String(raw).split("~");
  if (fields.length < 5) return null;
  const price = Number(fields[3]);
  const previous = Number(fields[4]);
  if (!Number.isFinite(price) || price <= 0) return null;
  let changePct = null;
  if (Number.isFinite(previous) && previous > 0) {
    changePct = ((price - previous) / previous) * 100;
  }
  // Prefer provider percent field when present.
  const maybePct = Number(fields[32]);
  if (Number.isFinite(maybePct) && Math.abs(maybePct) < 50) changePct = maybePct;
  return {
    ticker: meta.ticker,
    market: meta.market,
    symbol: meta.symbol,
    name: fields[1] || meta.company,
    price,
    previous_close: previous,
    change_pct: changePct,
    currency: meta.market === "港股" ? "HKD" : "CNY",
    provider_timestamp: fields[30] || null,
    source: "Tencent live",
  };
}

async function fetchLiveQuotes() {
  const watch = [];
  for (const item of state.decisions) {
    if (!item.ticker || !["A股", "港股"].includes(item.market)) continue;
    const symbol = tencentSymbol(item.ticker, item.market);
    if (!symbol) continue;
    watch.push({
      symbol,
      ticker: item.ticker,
      market: item.market,
      company: item.company,
    });
  }
  if (!watch.length) return 0;

  let loaded = 0;
  for (let i = 0; i < watch.length; i += 40) {
    const batch = watch.slice(i, i + 40);
    const url = `${TENCENT_QUOTE_URL}${batch.map((x) => x.symbol).join(",")}`;
    await loadScript(url);
    for (const meta of batch) {
      const raw = window[`v_${meta.symbol}`];
      const quote = parseTencentFieldString(raw, meta);
      if (quote) {
        state.quotes.set(quote.ticker, quote);
        loaded += 1;
      }
      try {
        delete window[`v_${meta.symbol}`];
      } catch {
        /* ignore */
      }
    }
  }
  return loaded;
}

async function loadSnapshotQuotes() {
  const response = await fetch(`./data/quotes/latest.json?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("snapshot missing");
  const payload = await response.json();
  let count = 0;
  for (const quote of payload.quotes || []) {
    if (!quote?.ticker || !Number.isFinite(Number(quote.price))) continue;
    const previous = Number(quote.previous_close);
    const price = Number(quote.price);
    const changePct =
      Number.isFinite(Number(quote.change_pct))
        ? Number(quote.change_pct)
        : Number.isFinite(previous) && previous > 0
          ? ((price - previous) / previous) * 100
          : null;
    state.quotes.set(quote.ticker, {
      ...quote,
      price,
      previous_close: previous,
      change_pct: changePct,
      source: quote.source || "snapshot",
    });
    count += 1;
  }
  state.quoteUpdatedAt = payload.generated_at || new Date().toISOString();
  return count;
}

async function refreshQuotes({ forceLive = false, silent = false } = {}) {
  try {
    // Always try the browser live endpoint first. Outside sessions Tencent still
    // returns the latest official close, which is better than a stale snapshot.
    try {
      const liveCount = await fetchLiveQuotes();
      if (liveCount > 0) {
        state.quoteUpdatedAt = new Date().toISOString();
        const label = isLikelyMarketOpen() || forceLive ? "实时行情" : "最新收盘";
        setLiveStatus("live", `${label} · ${liveCount} 只 · ${new Date().toLocaleTimeString()}`);
        renderAll();
        if (!silent) showToast(`已刷新${label} ${liveCount} 只`);
        return;
      }
    } catch (liveError) {
      console.warn("live quotes failed", liveError);
    }
    const snapCount = await loadSnapshotQuotes();
    setLiveStatus(
      "snapshot",
      `快照行情 · ${snapCount} 只 · ${state.quoteUpdatedAt ? new Date(state.quoteUpdatedAt).toLocaleString() : "未知"}`,
    );
    renderAll();
    if (!silent) showToast(`已加载行情快照 ${snapCount} 只`);
  } catch (error) {
    setLiveStatus("error", `行情不可用 · ${error.message}`);
    if (!silent) showToast("行情刷新失败");
  }
}

function startQuoteTimers() {
  clearInterval(state.liveTimer);
  clearInterval(state.snapshotTimer);
  state.liveTimer = setInterval(() => {
    // Trade session: denser live refresh. Off hours: still poll for latest close.
    const open = isLikelyMarketOpen();
    if (open || !state._offHoursTick) {
      refreshQuotes({ forceLive: open, silent: true });
    }
    state._offHoursTick = open ? 0 : ((state._offHoursTick || 0) + 1) % Math.max(1, Math.round(SNAPSHOT_INTERVAL_MS / LIVE_INTERVAL_MS));
  }, LIVE_INTERVAL_MS);
}

function isSeparatorRow(cells) {
  return cells.length > 0 && cells.every((cell) => cell === "" || /^:?-{3,}:?$/.test(cell));
}

function parseTableCells(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function looksNumeric(value) {
  const text = String(value || "")
    .replace(/[,，\s]/g, "")
    .replace(/^(HK\$|US\$|RMB|CNY|USD|HKD|约|低于|高于|≤|≥|<|>)/i, "")
    .replace(/(元|港元|美元|%|x|X|倍)$/g, "");
  return /^-?\d+(\.\d+)?$/.test(text) || /^-?\d+(\.\d+)?[-—~至到]\d+(\.\d+)?$/.test(text);
}

function rowToneClass(cells) {
  const blob = cells.join(" ");
  if (/乐观|激进/.test(blob)) return "tone-bull";
  if (/悲观|保守|谨慎|减仓|卖出|回避/.test(blob)) return "tone-bear";
  if (/中性|稳健|基准|持有|观察/.test(blob)) return "tone-base";
  return "";
}

function fillInlineMarkdown(el, text) {
  // Keep it simple and safe: bold / inline code only, no raw HTML injection.
  const parts = String(text || "").split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  for (const part of parts) {
    if (!part) continue;
    if (part.startsWith("**") && part.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = part.slice(2, -2);
      el.append(strong);
    } else if (part.startsWith("`") && part.endsWith("`")) {
      const code = document.createElement("code");
      code.textContent = part.slice(1, -1);
      el.append(code);
    } else {
      el.append(document.createTextNode(part));
    }
  }
}

function appendTable(target, tableLines) {
  const wrap = document.createElement("div");
  wrap.className = "valuation-table-wrap";
  const table = document.createElement("table");
  table.className = "valuation-table";
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  let headerDone = false;
  let colCount = 0;

  for (const line of tableLines) {
    if (!line.trim().startsWith("|")) continue;
    const cells = parseTableCells(line);
    if (!cells.length || isSeparatorRow(cells)) continue;
    const tr = document.createElement("tr");
    const tone = rowToneClass(cells);
    if (tone) tr.classList.add(tone);

    if (!headerDone) {
      colCount = cells.length;
      for (const cell of cells) {
        const th = document.createElement("th");
        fillInlineMarkdown(th, cell);
        tr.append(th);
      }
      thead.append(tr);
      headerDone = true;
      continue;
    }

    // Keep ragged rows readable.
    const normalized = cells.slice(0, Math.max(colCount, cells.length));
    while (normalized.length < colCount) normalized.push("");
    const headerTexts = [...(thead.rows[0]?.cells || [])].map((cell) => cell.textContent || "");
    normalized.forEach((cell, index) => {
      const td = document.createElement("td");
      const header = headerTexts[index] || "";
      const isFirst = index === 0;
      const isLast = index === normalized.length - 1;
      const numericHeader = /价|PE|EPS|涨跌|增速|回报|区间|目标|PB|ROE|市值|股息/i.test(header);
      if (!isFirst && (looksNumeric(cell) || numericHeader)) {
        td.classList.add("num");
      }
      // Narrative columns (含义/逻辑/说明) should wrap, not squeeze.
      if (isLast || /含义|逻辑|说明|假设|备注|理由|注释/.test(header)) {
        td.classList.add("text");
      }
      fillInlineMarkdown(td, cell);
      tr.append(td);
    });
    tbody.append(tr);
  }

  if (thead.childElementCount) table.append(thead);
  if (tbody.childElementCount) table.append(tbody);
  if (!table.childElementCount) return;
  wrap.append(table);
  target.append(wrap);
}

function renderMarkdownLite(target, markdown, { compact = false } = {}) {
  target.replaceChildren();
  target.classList.toggle("compact", Boolean(compact));
  if (!markdown) {
    const empty = document.createElement("div");
    empty.className = "valuation-empty";
    empty.textContent = "原文未提取到估值章节";
    target.append(empty);
    return;
  }

  // Normalize Windows newlines, then walk line-by-line so tables/lists/headings split cleanly.
  const lines = String(markdown).replace(/\r\n/g, "\n").split("\n");
  let index = 0;
  let firstHeadingSkipped = false;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    // Markdown tables
    if (trimmed.startsWith("|")) {
      const tableLines = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        tableLines.push(lines[index]);
        index += 1;
      }
      appendTable(target, tableLines);
      continue;
    }

    // Headings
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      const level = Math.min(headingMatch[1].length, 4);
      // Outer card already shows the section title; skip the first duplicate heading.
      if (!firstHeadingSkipped && level <= 3) {
        firstHeadingSkipped = true;
        index += 1;
        continue;
      }
      const heading = document.createElement(level <= 2 ? "h3" : "h4");
      heading.className = `valuation-h valuation-h${level}`;
      fillInlineMarkdown(heading, headingMatch[2].replace(/\*+/g, "").trim());
      target.append(heading);
      firstHeadingSkipped = true;
      index += 1;
      continue;
    }

    // Blockquotes
    if (trimmed.startsWith(">")) {
      const quote = document.createElement("blockquote");
      quote.className = "valuation-quote";
      const chunks = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        chunks.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      fillInlineMarkdown(quote, chunks.join(" "));
      target.append(quote);
      continue;
    }

    // Lists
    if (/^([-*+]|\d+\.)\s+/.test(trimmed)) {
      const ordered = /^\d+\.\s+/.test(trimmed);
      const list = document.createElement(ordered ? "ol" : "ul");
      list.className = "valuation-list";
      while (index < lines.length && /^([-*+]|\d+\.)\s+/.test(lines[index].trim())) {
        const item = document.createElement("li");
        fillInlineMarkdown(item, lines[index].trim().replace(/^([-*+]|\d+\.)\s+/, ""));
        list.append(item);
        index += 1;
      }
      target.append(list);
      continue;
    }

    // Paragraph (merge consecutive plain lines)
    const paraLines = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].trim().startsWith("|") &&
      !lines[index].trim().startsWith(">") &&
      !lines[index].trim().match(/^#{1,6}\s+/) &&
      !/^([-*+]|\d+\.)\s+/.test(lines[index].trim())
    ) {
      paraLines.push(lines[index].trim());
      index += 1;
    }
    const p = document.createElement("p");
    p.className = "valuation-p";
    fillInlineMarkdown(p, paraLines.join(" "));
    target.append(p);
  }
}


function cleanValuationLabel(heading) {
  if (!heading) return null;
  let text = String(heading)
    .replace(/^#+\s*/, "")
    .replace(/\*+/g, "")
    .trim();
  // Drop step / chapter prefixes that look abrupt in the list.
  text = text
    .replace(/^(第[一二三四五六七八九十百零〇两\d]+[步部分章节篇节]|[一二三四五六七八九十]+、|[（(]?[0-9]{1,2}[）).、:：]\s*)/u, "")
    .replace(/^(步骤|章节)\s*/u, "")
    .replace(/^[:：\s—–-]+/, "")
    .trim();
  // Prefer the core phrase when long embellishments follow.
  const core = text.match(/估值与安全边际|财务质量与估值|估值与价格纪律|最终投资建议|价格区间建议|行动价格带|三情景估值|财务估值|估值更新|估值分析/);
  if (core) {
    return core[0];
  }
  if (text.length > 18) {
    return `${text.slice(0, 16)}…`;
  }
  return text || "估值原表";
}

function valuationListLabel(item) {
  const heading = item?.valuation_section?.heading;
  const label = cleanValuationLabel(heading);
  if (!label) {
    return { label: "暂无原表", ready: false };
  }
  return { label, ready: true };
}

function renderSummary(visible) {
  if (state.view === "tracking") {
    const tracked = visible.map((item) => trackingForItem(item)).filter(Boolean);
    const reviewCount = tracked.filter(trackingNeedsReview).length;
    const moveCount = tracked.filter((tracking) => (tracking.alerts || []).some((alert) => alert.kind === "price_move")).length;
    const damagedCount = tracked.filter((tracking) => ["damaged", "broken"].includes(tracking.thesis_status)).length;
    const metrics = [
      ["跟踪中", tracked.filter((tracking) => tracking.status === "holding").length],
      ["论文待复核", reviewCount],
      ["股价异动", moveCount],
      ["论文受损", damagedCount],
      ["当前持仓", tracked.length],
    ];
    els.summary.replaceChildren();
    for (const [label, value] of metrics) {
      const card = document.createElement("div");
      card.className = "metric";
      card.innerHTML = `<span class="metric-label">${label}</span><strong class="metric-value">${value}</strong>`;
      els.summary.append(card);
    }
    return;
  }
  const counts = visible.reduce((acc, item) => {
    const advice = buyAdviceForItem(item, state.quotes.get(item.ticker));
    acc[advice.key] = (acc[advice.key] || 0) + 1;
    return acc;
  }, {});
  const metrics = [
    ["当前个股", visible.length],
    ["A股", visible.filter((i) => i.market === "A股").length],
    ["港股", visible.filter((i) => i.market === "港股").length],
    ["稳健/保守", (counts.balanced || 0) + (counts.conservative || 0)],
    ["暂不买入", counts.no || 0],
  ];
  els.summary.replaceChildren();
  for (const [label, value] of metrics) {
    const card = document.createElement("div");
    card.className = "metric";
    card.innerHTML = `<span class="metric-label">${label}</span><strong class="metric-value">${value}</strong>`;
    els.summary.append(card);
  }
}

function setTableHeader(labels) {
  els.decisionHead.innerHTML = `<tr>${labels.map((label) => `<th scope="col">${label}</th>`).join("")}</tr>`;
  els.decisionTable.classList.toggle("tracking-table", state.view === "tracking");
}

function renderTrackingRows(visible) {
  setTableHeader(["公司", "持仓状态", "论文状态", "下次复核", "最近异动"]);
  visible.forEach((item, index) => {
    const tracking = trackingForItem(item);
    if (!tracking) return;
    const tr = document.createElement("tr");
    const key = itemKey(item);
    if (key === state.selectedKey) tr.classList.add("active");
    tr.dataset.key = key;
    tr.dataset.index = String(index);
    tr.tabIndex = 0;

    const companyTd = document.createElement("td");
    companyTd.className = "company-cell";
    companyTd.innerHTML = `<div class="company-name">${item.company}</div><div class="company-meta">${item.market || "未识别"} · ${item.ticker || "无代码"}</div>`;
    tr.append(companyTd);

    const statusTd = document.createElement("td");
    statusTd.dataset.label = "持仓状态";
    appendTrackingBadge(statusTd, trackingStatusLabel(tracking.status), trackingStatusClass(tracking.status));
    if (tracking.buy_date) {
      const buyDate = document.createElement("div");
      buyDate.className = "tracking-meta";
      buyDate.textContent = `买入 ${tracking.buy_date}`;
      statusTd.append(buyDate);
    }
    tr.append(statusTd);

    const thesisTd = document.createElement("td");
    thesisTd.dataset.label = "论文状态";
    appendTrackingBadge(thesisTd, thesisStatusLabel(tracking.thesis_status), trackingStatusClass(tracking.thesis_status));
    const score = document.createElement("div");
    score.className = "tracking-meta";
    score.textContent = tracking.health_score ? `健康度 ${tracking.health_score}/10` : "尚未完成论文检查";
    thesisTd.append(score);
    tr.append(thesisTd);

    const reviewTd = document.createElement("td");
    reviewTd.dataset.label = "下次复核";
    const reviewLevel = trackingNeedsReview(tracking) ? (trackingAlertLevel(tracking) === "critical" ? "tracking-review-critical" : "tracking-review-warning") : "";
    appendTrackingBadge(reviewTd, trackingReviewLabel(tracking), reviewLevel);
    if (tracking.review_action) {
      const action = document.createElement("div");
      action.className = "tracking-meta";
      action.textContent = tracking.review_action;
      reviewTd.append(action);
    }
    tr.append(reviewTd);

    const eventTd = document.createElement("td");
    eventTd.dataset.label = "最近异动";
    const latest = tracking.latest_event;
    if (latest) {
      const eventTitle = document.createElement("div");
      eventTitle.className = "tracking-event-title";
      eventTitle.textContent = `${latest.date || ""} · ${latest.category || "不明"}${latest.change_pct == null ? "" : ` · ${Number(latest.change_pct).toFixed(2)}%`}`;
      eventTd.append(eventTitle);
      const eventSummary = document.createElement("div");
      eventSummary.className = "tracking-meta tracking-event-summary";
      eventSummary.textContent = latest.summary || "已记录异动，暂无摘要";
      eventTd.append(eventSummary);
    } else {
      eventTd.textContent = "暂无异动记录";
      eventTd.className = "tracking-empty";
    }
    const alerts = tracking.alerts || [];
    if (alerts.length) {
      appendTrackingBadge(eventTd, `${alerts.length} 条预警`, trackingAlertLevel(tracking) === "critical" ? "tracking-alert-critical" : "tracking-alert-warning");
    }
    tr.append(eventTd);

    tr.addEventListener("click", () => openDetail(item, { scrollRow: false }));
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter") openDetail(item, { scrollRow: false });
    });
    els.rows.append(tr);
  });
}

function appendStack(cell, lines) {
  const list = document.createElement("div");
  list.className = "stack-list";
  for (const line of lines.slice(0, 4)) {
    const row = document.createElement("div");
    row.className = "stack-item";
    row.textContent = line;
    list.append(row);
  }
  if (lines.length > 4) {
    const more = document.createElement("div");
    more.className = "stack-item muted";
    more.textContent = `另有 ${lines.length - 4} 条…`;
    list.append(more);
  }
  cell.append(list);
}

function renderRows() {
  const visible = filteredDecisions();
  renderSummary(visible);
  els.rows.replaceChildren();
  if (state.view === "tracking") {
    renderTrackingRows(visible);
    els.status.textContent = `显示 ${visible.length} / ${state.decisions.filter((item) => trackingForItem(item)).length} · 持仓跟踪`;
    if (els.emptyState) els.emptyState.hidden = visible.length > 0;
    if (state.focusIndex >= visible.length) state.focusIndex = visible.length - 1;
    return;
  }
  setTableHeader(["公司", "市场/代码", "分层结论", "现价", "买入建议", "估值原表", "研报日"]);

  visible.forEach((item, index) => {
    const tr = document.createElement("tr");
    const key = itemKey(item);
    if (key === state.selectedKey) tr.classList.add("active");
    tr.dataset.key = key;
    tr.dataset.index = String(index);
    tr.tabIndex = 0;

    const companyTd = document.createElement("td");
    companyTd.className = "company-cell";
    companyTd.innerHTML = `<div class="company-name">${item.company}</div><div class="company-meta">${item.valuation_section?.heading ? "含估值原表" : "待补原表"}</div>`;
    tr.append(companyTd);

    const marketTd = document.createElement("td");
    marketTd.innerHTML = `<span class="market-badge ${marketBadgeClass(item.market)}">${item.market || "未识别"}</span><div class="ticker-code">${item.ticker || "无代码"}</div>`;
    tr.append(marketTd);

    const actionTd = document.createElement("td");
    actionTd.className = "conclusion-cell";
    actionTd.append(renderStanceStack(item, { compact: true }));
    tr.append(actionTd);

    const quote = state.quotes.get(item.ticker);
    const change = formatChange(quote);
    const quoteTd = document.createElement("td");
    quoteTd.className = "quote-block";
    quoteTd.innerHTML = `
      <div class="quote-price">${formatPrice(quote)}</div>
      <div class="quote-change ${change.className}">${change.text}${quote?.source ? ` · ${quote.source === "Tencent live" ? "实时" : "快照"}` : ""}</div>
    `;
    tr.append(quoteTd);

    const adviceTd = document.createElement("td");
    adviceTd.className = "buy-advice-cell";
    adviceTd.append(renderBuyAdviceCell(item, quote));
    tr.append(adviceTd);

    const valTd = document.createElement("td");
    const valMeta = valuationListLabel(item);
    valTd.className = "valuation-col";
    valTd.innerHTML = `
      <span class="valuation-chip ${valMeta.ready ? "ready" : "empty"}">${valMeta.label}</span>
      <span class="valuation-hint">${valMeta.ready ? "查看原表" : "待补充"}</span>
    `;
    tr.append(valTd);

    const cutoffTd = document.createElement("td");
    cutoffTd.className = "cutoff-cell";
    cutoffTd.innerHTML = item.data_cutoff
      ? `<span class="cutoff-date">${item.data_cutoff}</span>`
      : `<span class="cutoff-pending">待复核</span>`;
    tr.append(cutoffTd);

    tr.addEventListener("click", () => openDetail(item, { scrollRow: false }));
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter") openDetail(item, { scrollRow: false });
    });
    els.rows.append(tr);
  });

  els.status.textContent = `显示 ${visible.length} / ${state.decisions.length} · 排序：${els.sortSelect.selectedOptions[0]?.text || state.sort}`;
  if (els.emptyState) {
    els.emptyState.hidden = visible.length > 0;
  }
  if (state.focusIndex >= visible.length) state.focusIndex = visible.length - 1;
}

function appendTrackingDetailCard(title, content) {
  const card = document.createElement("div");
  card.className = "card tracking-card";
  const heading = document.createElement("h3");
  heading.textContent = title;
  card.append(heading, content);
  els.detailBody.append(card);
}

function renderTrackingDetail(item, tracking) {
  if (!tracking) {
    const empty = document.createElement("div");
    empty.className = "card tracking-empty-card";
    empty.innerHTML = "<h3>尚未建立持仓跟踪</h3><p class=\"source-note\">基本面建议“买入”不等于已持仓。确认买入后，再使用持仓登记命令建立论文和预警。</p>";
    els.detailBody.append(empty);
    return;
  }

  const summary = document.createElement("dl");
  summary.className = "kv-grid";
  const fields = [
    ["持仓状态", trackingStatusLabel(tracking.status)],
    ["买入日期", tracking.buy_date || "未给出"],
    ["买入成本", tracking.cost_basis == null ? "未给出" : String(tracking.cost_basis)],
    ["仓位", tracking.position_weight == null ? "未给出" : `${tracking.position_weight}%`],
    ["论文状态", thesisStatusLabel(tracking.thesis_status)],
    ["论文健康度", tracking.health_score ? `${tracking.health_score}/10` : "尚未检查"],
    ["上次复核", tracking.last_review_date || "未给出"],
    ["下次复核", trackingReviewLabel(tracking)],
    ["复核动作", tracking.review_action || "未给出"],
  ];
  for (const [key, value] of fields) {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  appendTrackingDetailCard("持仓与论文", summary);

  const metrics = document.createElement("div");
  metrics.className = "tracking-metric-list";
  if (tracking.metrics?.length) {
    for (const metric of tracking.metrics) {
      const row = document.createElement("div");
      row.className = "tracking-metric-row";
      if (typeof metric === "string") {
        row.textContent = metric;
      } else {
        const name = metric?.name || "指标";
        const target = metric?.target ? ` · 目标 ${metric.target}` : "";
        const frequency = metric?.frequency ? ` · ${metric.frequency}` : "";
        const status = metric?.status ? ` · ${metric.status}` : "";
        row.textContent = `${name}${target}${frequency}${status}`;
      }
      metrics.append(row);
    }
  } else {
    const note = document.createElement("p");
    note.className = "source-note";
    note.textContent = "尚未登记 3 至 5 个论文跟踪指标。";
    metrics.append(note);
  }
  appendTrackingDetailCard("必须跟踪的指标", metrics);

  const activity = document.createElement("div");
  activity.className = "tracking-activity";
  const alerts = tracking.alerts || [];
  if (alerts.length) {
    for (const alert of alerts) {
      const row = document.createElement("div");
      row.className = `tracking-alert-row ${alert.severity === "critical" ? "critical" : "warning"}`;
      const title = document.createElement("strong");
      title.textContent = alert.title || "预警";
      const detail = document.createElement("span");
      detail.textContent = alert.detail || "请检查跟踪状态";
      row.append(title, detail);
      activity.append(row);
    }
  }
  const latest = tracking.latest_event;
  if (latest) {
    const event = document.createElement("div");
    event.className = "tracking-event-detail";
    event.textContent = `${latest.date || ""} · ${latest.category || "不明"}${latest.change_pct == null ? "" : ` · ${Number(latest.change_pct).toFixed(2)}%`} · ${latest.summary || "暂无摘要"}`;
    activity.append(event);
    if (latest.report_path) {
      const link = document.createElement("a");
      link.className = "btn ghost tracking-report-link";
      link.href = `${repositoryUrl}${latest.report_path}`;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = "打开异动报告";
      activity.append(link);
    }
  }
  if (!activity.childElementCount) {
    const note = document.createElement("p");
    note.className = "source-note";
    note.textContent = "暂无异动预警。行情达到预警线后，先标记待分析，再由你确认是否调用股价异动分析。";
    activity.append(note);
  }
  appendTrackingDetailCard("异动与预警", activity);

  if (tracking.thesis_report_path) {
    const link = document.createElement("a");
    link.className = "btn ghost tracking-report-link";
    link.href = `${repositoryUrl}${tracking.thesis_report_path}`;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "打开投资论文";
    els.detailBody.append(link);
  }
}

function renderDetail() {
  const item = selectedItem();
  if (!item) {
    els.detailPanel.hidden = true;
    els.workspace.classList.remove("detail-open");
    return;
  }
  els.detailPanel.hidden = false;
  els.workspace.classList.add("detail-open");
  els.detailTitle.textContent = item.company;
  const quote = state.quotes.get(item.ticker);
  const change = formatChange(quote);
  els.detailKicker.textContent = `${item.market || "未识别"} · ${item.ticker || "无代码"}`;
  const stanceBrief = (item.investor_stances || [])
    .map((s) => `${String(s.stance || "").replace("型", "")}${s.action ? "·" + String(s.action).slice(0, 8) : ""}`)
    .join(" / ") || item.action || "-";
  const adviceBrief = buyAdviceForItem(item, quote).label;
  els.detailSub.textContent = `${adviceBrief} · 分层 ${stanceBrief} · 现价 ${formatPrice(quote)} (${change.text}) · 研报 ${item.data_cutoff || "待复核"}`;
  const sourcePath = item.valuation_section?.source_report_path || item.report_path;
  els.detailReport.href = `${repositoryUrl}${sourcePath || item.report_path}`;

  els.detailBody.replaceChildren();
  const tracking = trackingForItem(item);
  const trackingTab = document.querySelector(".tracking-tab");
  if (trackingTab) {
    trackingTab.hidden = !tracking;
    if (!tracking && state.detailTab === "tracking") state.detailTab = "overview";
  }
  document.querySelectorAll(".detail-tabs .tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === state.detailTab);
  });

  if (state.detailTab === "tracking") {
    renderTrackingDetail(item, tracking);
    return;
  }

  if (state.detailTab === "overview") {
    const adviceCard = document.createElement("div");
    adviceCard.className = "card";
    const advice = buyAdviceForItem(item, quote);
    adviceCard.innerHTML = `<h3>买入建议（现价对照）</h3>`;
    const adviceBody = document.createElement("div");
    adviceBody.className = "buy-advice buy-advice-detail-card";
    const badge = document.createElement("span");
    badge.className = `zone-badge ${advice.className}`;
    badge.textContent = advice.label;
    const p = document.createElement("p");
    p.className = "source-note";
    p.textContent = advice.detail + "。规则：现价落入最保守仍满足的风格；高于全部买入上限则不适合买入。仅供研究，不构成投资建议。";
    adviceBody.append(badge, p);
    adviceCard.append(adviceBody);
    els.detailBody.append(adviceCard);

    const overview = document.createElement("div");
    overview.className = "card";
    overview.innerHTML = `<h3>分层结论（以第八步为准）</h3>`;
    overview.append(renderStanceStack(item, { compact: false }));
    if (!(item.investor_stances || []).length) {
      const fallback = document.createElement("p");
      fallback.className = "source-note";
      fallback.textContent = `未提取到激进/稳健/保守分层，回退粗粒度结论：${item.action || "未分类"}`;
      overview.append(fallback);
    }
    els.detailBody.append(overview);

    const meta = document.createElement("div");
    meta.className = "card";
    meta.innerHTML = `<h3>当前判断</h3>`;
    const dl = document.createElement("dl");
    dl.className = "kv-grid";
    const rows = [
      ["粗粒度标签", item.action || "-"],
      ["现价", `${formatPrice(quote)} ${change.text}`],
      ["数据截止", item.data_cutoff || "待复核"],
      ["推荐摘要", item.recommendation || item.title || "-"],
    ];
    for (const [k, v] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      dl.append(dt, dd);
    }
    meta.append(dl);
    els.detailBody.append(meta);

    const tip = document.createElement("div");
    tip.className = "card";
    tip.innerHTML = `<h3>价格信息</h3><p class="source-note">分层价格以报告第八步「最终决策与行动清单」为主；完整表格请查看「估值原文」。第七步三情景仅作辅助，不单独作为买卖结论。</p>`;
    els.detailBody.append(tip);
    return;
  }

  if (state.detailTab === "valuation") {
    const card = document.createElement("div");
    card.className = "card valuation-card";
    const head = document.createElement("div");
    head.className = "valuation-card-head";
    const title = document.createElement("h3");
    title.textContent = item.valuation_section?.heading || "估值原文";
    head.append(title);
    if (item.valuation_section?.source_note) {
      const note = document.createElement("p");
      note.className = "source-note";
      note.textContent = item.valuation_section.source_note;
      head.append(note);
    } else {
      const note = document.createElement("p");
      note.className = "source-note";
      note.textContent = "以下为报告章节原表渲染，未做价格二次摘要。";
      head.append(note);
    }
    const body = document.createElement("div");
    body.className = "valuation-markdown";
    renderMarkdownLite(body, item.valuation_section?.markdown || "");
    card.append(head, body);
    els.detailBody.append(card);
    return;
  }

  // history
  const history = item.report_history?.length ? item.report_history : [];
  if (!history.length) {
    const empty = document.createElement("div");
    empty.className = "card";
    empty.textContent = "暂无历史研报记录";
    els.detailBody.append(empty);
    return;
  }
  for (const snap of history) {
    const card = document.createElement("article");
    card.className = "history-card";
    const head = document.createElement("header");
    head.innerHTML = `<strong>${snap.data_cutoff || "待复核"}</strong><span class="decision ${decisionClass(snap.action)}">${snap.action || "-"}</span>`;
    card.append(head);
    if (snap.conclusion_summary || (snap.investor_stances || []).length) {
      const histLine = document.createElement("div");
      histLine.className = "history-stance";
      histLine.textContent = snap.conclusion_summary || (snap.investor_stances || [])
        .map((s) => `${String(s.stance || "").replace("型", "")}：${s.action || ""}${s.price_range ? "（" + s.price_range + "）" : ""}`)
        .join("；");
      card.append(histLine);
    }
    if (snap.valuation_section?.heading) {
      const headNote = document.createElement("div");
      headNote.className = "stack-item muted";
      headNote.textContent = snap.valuation_section.heading;
      card.append(headNote);
    }
    if (snap.valuation_section?.markdown) {
      const val = document.createElement("div");
      val.className = "valuation-markdown";
      renderMarkdownLite(val, snap.valuation_section.markdown, { compact: true });
      card.append(val);
    }
    const link = document.createElement("a");
    link.className = "btn ghost";
    link.href = `${repositoryUrl}${snap.report_path}`;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = snap.title || "打开该期报告";
    card.append(link);
    els.detailBody.append(card);
  }
}

function updateHash(item) {
  if (!item) {
    history.replaceState(null, "", location.pathname + location.search);
    return;
  }
  const token = item.ticker ? `ticker=${encodeURIComponent(item.ticker)}` : `company=${encodeURIComponent(item.company)}`;
  history.replaceState(null, "", `#${token}`);
}

function openDetail(item, { scrollRow = true, updateUrl = true } = {}) {
  if (!item) return;
  state.selectedKey = itemKey(item);
  const visible = filteredDecisions();
  state.focusIndex = visible.findIndex((x) => itemKey(x) === state.selectedKey);
  if (updateUrl) updateHash(item);
  renderRows();
  renderDetail();
  // Ensure full section is reachable from the top of the scrollable pane.
  if (els.detailBody) els.detailBody.scrollTop = 0;
  if (scrollRow) {
    const row = els.rows.querySelector(`tr[data-key="${CSS.escape(state.selectedKey)}"]`);
    row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

function closeDetail() {
  state.selectedKey = null;
  state.focusIndex = -1;
  updateHash(null);
  renderRows();
  renderDetail();
}

function renderAll() {
  renderRows();
  renderDetail();
}

function setView(view) {
  state.view = view === "tracking" ? "tracking" : "decision";
  state.focusIndex = -1;
  if (state.view === "tracking") {
    state.detailTab = "tracking";
  } else if (state.detailTab === "tracking") {
    state.detailTab = "valuation";
  }
  els.viewTabs?.querySelectorAll(".chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.view === state.view);
  });
  if (els.actionChips) els.actionChips.hidden = state.view === "tracking";
  if (els.trackingFilterRow) els.trackingFilterRow.hidden = state.view !== "tracking";
  renderAll();
}

function applyHashRoute() {
  const raw = location.hash.replace(/^#/, "");
  if (!raw) return;
  const params = new URLSearchParams(raw.includes("=") ? raw : `company=${raw}`);
  const ticker = params.get("ticker");
  const company = params.get("company");
  const item = state.decisions.find((d) => {
    if (ticker && d.ticker === ticker) return true;
    if (company && d.company === company) return true;
    return false;
  });
  if (item) openDetail(item, { scrollRow: true, updateUrl: false });
}

function bindEvents() {
  els.companyFilter.addEventListener("input", () => {
    renderRows();
  });
  els.companyFilter.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      const first = filteredDecisions()[0];
      if (first) openDetail(first);
    }
  });
  els.sortSelect.addEventListener("change", () => {
    state.sort = els.sortSelect.value;
    renderRows();
  });
  els.clearFilters.addEventListener("click", () => {
    state.market = "all";
    state.action = "all";
    state.trackingFilter = "all";
    state.sort = "buy_advice";
    els.companyFilter.value = "";
    els.sortSelect.value = "buy_advice";
    els.marketChips.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.market === "all");
    });
    els.actionChips.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.action === "all");
    });
    els.trackingFilterRow?.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.trackingFilter === "all");
    });
    setView("decision");
  });
  els.viewTabs?.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    setView(chip.dataset.view);
  });
  els.marketChips.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    state.market = chip.dataset.market;
    els.marketChips.querySelectorAll(".chip").forEach((node) => {
      node.classList.toggle("active", node === chip);
    });
    renderRows();
  });
  els.actionChips.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    state.action = chip.dataset.action;
    els.actionChips.querySelectorAll(".chip").forEach((node) => {
      node.classList.toggle("active", node === chip);
    });
    renderRows();
  });
  els.trackingFilterRow?.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    state.trackingFilter = chip.dataset.trackingFilter || "all";
    els.trackingFilterRow.querySelectorAll(".chip").forEach((node) => {
      node.classList.toggle("active", node === chip);
    });
    renderRows();
  });
  document.querySelector(".detail-tabs")?.addEventListener("click", (event) => {
    const tab = event.target.closest(".tab");
    if (!tab) return;
    state.detailTab = tab.dataset.tab;
    renderDetail();
  });
  els.detailClose.addEventListener("click", closeDetail);
  els.detailCopy.addEventListener("click", async () => {
    const item = selectedItem();
    if (!item) return;
    const url = `${location.origin}${location.pathname}#${item.ticker ? `ticker=${encodeURIComponent(item.ticker)}` : `company=${encodeURIComponent(item.company)}`}`;
    try {
      await navigator.clipboard.writeText(url);
      showToast("已复制分享链接");
    } catch {
      showToast(url);
    }
  });
  els.refreshQuotes.addEventListener("click", () => refreshQuotes({ forceLive: true }));
  window.addEventListener("hashchange", applyHashRoute);

  document.addEventListener("keydown", (event) => {
    const tag = document.activeElement?.tagName;
    const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    if (event.key === "/" && !typing) {
      event.preventDefault();
      els.companyFilter.focus();
      els.companyFilter.select();
      return;
    }
    if (event.key === "Escape") {
      if (document.activeElement === els.companyFilter) {
        els.companyFilter.blur();
        return;
      }
      closeDetail();
      return;
    }
    if (typing) return;
    const visible = filteredDecisions();
    if (!visible.length) return;
    if (event.key === "j" || event.key === "ArrowDown") {
      event.preventDefault();
      state.focusIndex = Math.min(visible.length - 1, Math.max(0, state.focusIndex) + 1);
      openDetail(visible[state.focusIndex]);
    } else if (event.key === "k" || event.key === "ArrowUp") {
      event.preventDefault();
      state.focusIndex = Math.max(0, (state.focusIndex < 0 ? 0 : state.focusIndex) - 1);
      openDetail(visible[state.focusIndex]);
    } else if (event.key === "Enter" && state.focusIndex >= 0) {
      openDetail(visible[state.focusIndex]);
      state.detailTab = "valuation";
      renderDetail();
    } else if (event.key === "o" && selectedItem()) {
      els.detailReport.click();
    }
  });
}

async function loadDashboard() {
  setLiveStatus("idle", "加载决策数据…");
  const response = await fetch(`./data/decision_board.json?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("无法加载 decision_board.json");
  const board = await response.json();
  state.decisions = board.decisions || [];
  const activeTracking = Number(board.post_buy_tracking?.active_count || 0);
  if (els.trackingCount) els.trackingCount.textContent = activeTracking ? String(activeTracking) : "0";
  renderAll();
  applyHashRoute();
  await refreshQuotes({ forceLive: isLikelyMarketOpen(), silent: true });
  startQuoteTimers();
}

bindEvents();
loadDashboard().catch((error) => {
  els.status.textContent = `加载失败：${error.message}`;
  setLiveStatus("error", "加载失败");
});
