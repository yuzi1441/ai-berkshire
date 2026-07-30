import {
  currentActionKind,
  fallbackActionKind,
  parseReportPriceBand,
} from "./action-classifier.mjs?v=20260730-a-share-audit2";

const repositoryUrl = "https://github.com/yuzi1441/ai-berkshire/blob/main/";
const TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q=";
const LIVE_INTERVAL_MS = 45_000;
const SNAPSHOT_INTERVAL_MS = 180_000;

const state = {
  decisions: [],
  quotes: new Map(),
  selectedKey: null,
  market: "all",
  action: "all",
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
  summary: document.querySelector("#summary"),
  status: document.querySelector("#data-status"),
  companyFilter: document.querySelector("#company-filter"),
  sortSelect: document.querySelector("#sort-select"),
  clearFilters: document.querySelector("#clear-filters"),
  marketChips: document.querySelector("#market-chips"),
  actionChips: document.querySelector("#action-chips"),
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
  if (/坚决回避|明确回避|不建议买入|不宜买入|暂不买入|远离|坚决不买|不要追|观望为主|继续观察|保持观望|建议观望|放入观察|等待更好|等待验证|观察池|无安全边际|回避/.test(blob)
      && !/买入|建仓|配置/.test(blob)) {
    return "观察";
  }
  if (/观望|等待|观察|不追/.test(blob) && !/买入|建仓|配置|试探|试错|小仓/.test(blob)) {
    return "观察";
  }
  if (/持有但不加|继续持有|持有观望|持有/.test(blob) && !/买入|建仓|配置|试探|试错|小仓/.test(blob)) {
    return "持有";
  }
  if (/强烈买入|积极买入|重点买入|重仓|重注/.test(blob)) return "买入";
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

function reportPriceRows(item) {
  const plans = Array.isArray(item?.price_plan) ? item.price_plan : [];
  const planRows = plans
    .filter((row) => row && row.price_range && (row.action || row.profile))
    .map((row, index) => ({
      profile: row.profile || "",
      price_range: row.price_range || "",
      action: row.action || row.profile || "见报告",
      note: row.rationale || "",
      source: "price_plan",
      index,
    }));
  if (planRows.length) return planRows;
  return (item?.investor_stances || [])
    .filter((row) => row && row.price_range)
    .map((row, index) => ({
      profile: row.stance || row.profile || "",
      price_range: row.price_range || "",
      action: row.action || "见报告",
      note: row.note || "",
      source: "stance_fallback",
      index,
    }));
}

function reportPriceRowText(row) {
  const action = String(row?.action || row?.profile || "见报告");
  const profile = String(row?.profile || "");
  if (profile && profile !== action && !/^(价格带|区间)$/.test(profile)) {
    return `${profile} · ${action}`;
  }
  return action;
}

function currentReportActionText(row) {
  let text = reportPriceRowText(row);
  text = text
    .replace(/[（(][^()（）]*(?:现价|当前价|目前价格|当前位置)[^()（）]*[）)]/g, "")
    .replace(/(^|[。；;]\s*)(?:当前|现价|目前)(?:价格|价)?\s*\d+(?:\.\d+)?\s*(?:元|港元|美元|HKD|USD)?[^。；;]*/gi, "$1")
    .replace(/当前所在区间|当前位置|当前区间/g, "该价格档")
    .replace(/当前价附近|现价附近/g, "该价格档附近")
    .replace(/^[\s。；;·，,]+|[\s。；;·，,]+$/g, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  return text || "按报告价格表执行";
}

function renderPriceActionTable(item, quote, { compact = true } = {}) {
  const rows = reportPriceRows(item);
  const wrap = document.createElement("div");
  wrap.className = compact ? "price-action-table" : "price-action-table price-action-table-detail";
  if (!rows.length) {
    const fallback = document.createElement("span");
    fallback.className = `decision ${decisionClass(item.action)}`;
    fallback.textContent = item.action || "未提取价格表";
    wrap.append(fallback);
    return wrap;
  }
  const matched = matchReportPriceRow(item, quote)?.row;
  const limit = compact ? 6 : rows.length;
  for (const rowData of rows.slice(0, limit)) {
    const row = document.createElement("div");
    row.className = "price-action-row";
    if (matched && matched.source === rowData.source && matched.index === rowData.index) {
      row.classList.add("current-price-row");
    }
    const price = document.createElement("div");
    price.className = "price-action-band";
    price.textContent = rowData.price_range;
    const action = document.createElement("div");
    action.className = "price-action-text";
    action.textContent = reportPriceRowText(rowData);
    row.append(price, action);
    wrap.append(row);
  }
  if (compact && rows.length > limit) {
    const more = document.createElement("div");
    more.className = "price-action-more";
    more.textContent = `另有 ${rows.length - limit} 档，点开查看`;
    wrap.append(more);
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


function isHolderOnlyPriceRow(row) {
  const profile = String(row?.profile || "");
  return /已持有|持仓者|持有者/.test(profile) && !/空仓|新资金|未持有/.test(profile);
}

function bandContainsExactPrice(price, band) {
  if (!Number.isFinite(price) || !band) return false;
  if (band.mode === "range") return price >= band.min - 1e-9 && price <= band.max + 1e-9;
  if (band.mode === "ceiling") return price <= band.max + 1e-9;
  if (band.mode === "floor") return price >= band.min - 1e-9;
  return false;
}

function inferredPointBand(points, index) {
  const current = points[index]?.band?.max;
  const previous = index > 0 ? points[index - 1]?.band?.max : null;
  if (!Number.isFinite(current)) return null;
  if (Number.isFinite(previous)) {
    return {
      min: previous,
      max: current,
      mode: "inferred_range",
      currency: points[index].band.currency,
    };
  }
  return {
    min: null,
    max: current,
    mode: "inferred_ceiling",
    currency: points[index].band.currency,
  };
}

function matchReportPriceRow(item, quote) {
  const price = Number(quote?.price);
  if (!Number.isFinite(price)) return null;
  const rows = reportPriceRows(item).map((row) => ({
    row,
    band: parseReportPriceBand(row, item?.market),
  })).filter((entry) => entry.band && entry.band.currency === quote.currency);
  if (!rows.length) return null;
  const nonHolderRows = rows.filter((entry) => !isHolderOnlyPriceRow(entry.row));
  const usable = nonHolderRows.length ? nonHolderRows : rows;
  const actionPriority = { buy: 0, trial: 1, hold: 2, watch: 3, no: 4, unknown: 5 };
  const exact = usable.filter((entry) => entry.band.mode !== "point" && bandContainsExactPrice(price, entry.band));
  if (exact.length) {
    exact.sort((a, b) => {
      const actionDiff = actionPriority[currentActionKind(a.row)] - actionPriority[currentActionKind(b.row)];
      if (actionDiff) return actionDiff;
      const widthA = a.band.mode === "range" ? a.band.max - a.band.min : Number.POSITIVE_INFINITY;
      const widthB = b.band.mode === "range" ? b.band.max - b.band.min : Number.POSITIVE_INFINITY;
      return widthA - widthB || a.row.index - b.row.index;
    });
    return { ...exact[0], effectiveBand: exact[0].band, confidence: "explicit" };
  }
  const points = usable.filter((entry) => entry.band.mode === "point").sort((a, b) => a.band.max - b.band.max);
  if (points.length >= 2) {
    const nextIndex = points.findIndex((entry) => price <= entry.band.max + 1e-9);
    if (nextIndex >= 0) {
      return {
        ...points[nextIndex],
        effectiveBand: inferredPointBand(points, nextIndex),
        confidence: "inferred_ladder",
      };
    }
    const highest = points[points.length - 1];
    if (["no", "watch", "hold"].includes(currentActionKind(highest.row))) {
      return {
        ...highest,
        effectiveBand: {
          min: highest.band.max,
          max: null,
          mode: "inferred_floor",
          currency: highest.band.currency,
        },
        confidence: "inferred_ladder",
      };
    }
  }
  if (points.length === 1) {
    const only = points[0];
    const tolerance = Math.max(0.02, only.band.max * 0.001);
    if (Math.abs(price - only.band.max) <= tolerance) {
      return { ...only, effectiveBand: only.band, confidence: "exact_point" };
    }
  }
  return null;
}

function formatBandNumber(value) {
  return Number(value).toFixed(2).replace(/\.?0+$/, "");
}

function priceBandUnit(currency) {
  return {
    CNY: "元",
    HKD: "港元",
    USD: "美元",
    KRW: "韩元",
  }[currency] || "";
}

function effectivePriceBandText(band) {
  if (!band) return "";
  const unit = priceBandUnit(band.currency);
  if (band.mode === "range" || band.mode === "inferred_range") {
    return `${formatBandNumber(band.min)}–${formatBandNumber(band.max)} ${unit}`.trim();
  }
  if (band.mode === "ceiling" || band.mode === "inferred_ceiling") {
    return `≤ ${formatBandNumber(band.max)} ${unit}`.trim();
  }
  if (band.mode === "floor" || band.mode === "inferred_floor") {
    return `≥ ${formatBandNumber(band.min)} ${unit}`.trim();
  }
  return `${formatBandNumber(band.max)} ${unit}附近`.trim();
}

function currentActionLabel(kind) {
  return {
    buy: "买入区",
    trial: "小仓试探区",
    hold: "持有区",
    watch: "观察区",
    no: "减仓/排除区",
    unknown: "无法归类",
  }[kind] || "待确认";
}

function actionMeta(kind) {
  return {
    buy: { key: "buy", rank: 5, className: "buy-zone" },
    trial: { key: "trial", rank: 4, className: "trial-zone" },
    hold: { key: "hold", rank: 3, className: "hold-zone" },
    watch: { key: "watch", rank: 2, className: "watch-zone" },
    no: { key: "no", rank: 1, className: "hot-zone" },
    unknown: { key: "unknown", rank: 0, className: "unknown-zone" },
  }[kind] || { key: "unknown", rank: 0, className: "unknown-zone" };
}

function reportFallbackKind(item) {
  return fallbackActionKind({
    action: item?.action,
    recommendation: item?.recommendation,
    conclusion_summary: item?.conclusion_summary,
    valuation_heading: item?.valuation_section?.heading,
  });
}

function recentUsableHistoryDecision(item) {
  const usable = (item?.report_history || []).filter((entry) => {
    const action = String(entry?.action || "").trim();
    return action && action !== "未提取";
  });
  return usable.find((entry) => /最终报告/.test(String(entry?.report_path || ""))) || usable[0] || null;
}

function compactReportConclusion(item) {
  const action = String(item?.action || "").trim();
  const recommendation = String(item?.recommendation || item?.conclusion_summary || "").trim();
  const heading = String(item?.valuation_section?.heading || "").trim();
  const recommendationIsUseful = recommendation
    && recommendation !== action
    && !/免责声明|不构成.{0,12}建议|投资研究最终报告|财务估值分析$|研究报告$/.test(recommendation);
  if (action && action !== "未提取" && !recommendationIsUseful) return action;
  const preferred = /免责声明|不构成.{0,12}建议|投资研究最终报告|财务估值分析$|研究报告$/.test(recommendation)
    ? heading
    : recommendationIsUseful
      ? recommendation
      : action;
  const conclusion = String(preferred || heading)
    .replace(/\s+/g, " ")
    .trim();
  if (!conclusion) return "";
  const firstSentence = conclusion.split(/[。；;\n]/, 1)[0].trim();
  return firstSentence.length > 42 ? `${firstSentence.slice(0, 41)}…` : firstSentence;
}

function reportFallbackResolution(item) {
  const currentKind = reportFallbackKind(item);
  if (currentKind !== "unknown") {
    return {
      kind: currentKind,
      conclusion: compactReportConclusion(item) || currentActionLabel(currentKind),
      cutoff: item?.data_cutoff || "未标注",
      basis: "latest_report",
    };
  }
  const historical = recentUsableHistoryDecision(item);
  if (historical) {
    const historicalKind = reportFallbackKind({
      action: historical.action,
      recommendation: historical.recommendation,
      conclusion_summary: historical.conclusion_summary,
    });
    if (historicalKind !== "unknown") {
      return {
        kind: historicalKind,
        conclusion: String(historical.action || "").trim() || currentActionLabel(historicalKind),
        cutoff: historical.data_cutoff || item?.data_cutoff || "未标注",
        basis: "recent_history",
      };
    }
  }
  return {
    kind: "unknown",
    conclusion: "",
    cutoff: item?.data_cutoff || "未标注",
    basis: "unknown",
  };
}

function reportFallbackAdvice(item, reason) {
  const resolution = reportFallbackResolution(item);
  const kind = resolution.kind;
  const meta = actionMeta(kind);
  const cutoff = resolution.cutoff;
  if (kind === "unknown") {
    return {
      key: meta.key,
      label: "无法归类",
      detail: `${reason}，且报告未提取明确操作结论 · 报告截止 ${cutoff}`,
      rank: meta.rank,
      className: meta.className,
      basis: "unknown",
    };
  }
  const basisText = resolution.basis === "recent_history"
    ? "按最近可用历史报告结论归类"
    : "按最新报告结论归类";
  return {
    key: meta.key,
    label: currentActionLabel(kind),
    detail: `${reason} · ${basisText} · 报告截止 ${cutoff}`,
    sourceAction: resolution.conclusion || currentActionLabel(kind),
    rank: meta.rank,
    className: meta.className,
    basis: resolution.basis,
  };
}

function unmatchedPricePlanAdvice(item, reason) {
  const meta = actionMeta("watch");
  return {
    key: meta.key,
    label: currentActionLabel("watch"),
    detail: `${reason} · 价格表存在但现价未命中，暂列观察 · 报告截止 ${item?.data_cutoff || "未标注"}`,
    sourceAction: compactReportConclusion(item) || "等待价格档重新覆盖",
    rank: meta.rank,
    className: meta.className,
    basis: "unmatched_price_plan",
  };
}

function reportBuyCeiling(item, quote) {
  if (!item?.buy_price || !quote?.currency) return null;
  const band = parseReportPriceBand(
    { price_range: item.buy_price },
    item?.market,
  );
  if (!band || band.currency !== quote.currency) return null;
  if (Number.isFinite(band.max)) return band.max;
  return null;
}

function staleBuyAnchorAdvice(item, price, ceiling) {
  const meta = actionMeta("watch");
  const unit = priceBandUnit(parseReportPriceBand(
    { price_range: item.buy_price },
    item?.market,
  )?.currency);
  return {
    key: meta.key,
    label: currentActionLabel("watch"),
    detail: `现价 ${formatBandNumber(price)} 高于报告买入锚 ${formatBandNumber(ceiling)} ${unit} · 暂列观察 · 报告截止 ${item?.data_cutoff || "未标注"}`,
    sourceAction: compactReportConclusion(item) || "等待价格回到报告买入锚",
    rank: meta.rank,
    className: meta.className,
    basis: "stale_buy_anchor",
  };
}

function buyAdviceForItem(item, quote) {
  const rows = reportPriceRows(item);
  if (!rows.length) {
    const fallback = reportFallbackAdvice(item, "无结构化价格档");
    const price = Number(quote?.price);
    const ceiling = reportBuyCeiling(item, quote);
    if (
      ["buy", "trial"].includes(fallback.key)
      && Number.isFinite(price)
      && Number.isFinite(ceiling)
      && price > ceiling * 1.03
    ) {
      return staleBuyAnchorAdvice(item, price, ceiling);
    }
    return fallback;
  }
  const price = Number(quote?.price);
  if (!Number.isFinite(price)) {
    return reportFallbackAdvice(item, "当前行情暂不可比");
  }
  const matched = matchReportPriceRow(item, quote);
  const priceText = Number(price).toFixed(2).replace(/\.00$/, "");
  if (!matched) {
    const hasComparable = rows.some((row) => parseReportPriceBand(row, item?.market)?.currency === quote.currency);
    const reason = hasComparable
      ? `现价 ${priceText} 未可靠命中报告价格档`
      : "报告价格单位与当前市场暂不可比";
    return hasComparable
      ? unmatchedPricePlanAdvice(item, reason)
      : reportFallbackAdvice(item, reason);
  }
  const kind = currentActionKind(matched.row);
  const meta = actionMeta(kind);
  const effectiveBand = matched.effectiveBand || matched.band;
  const effectiveBandText = effectivePriceBandText(effectiveBand);
  const cutoff = item?.data_cutoff || "未标注";
  return {
    key: meta.key,
    label: currentActionLabel(kind),
    detail: `现价 ${priceText} · 对应 ${effectiveBandText || matched.row.price_range} · 报告截止 ${cutoff}`,
    sourceAction: currentReportActionText(matched.row),
    rank: meta.rank,
    className: meta.className,
    matched: matched.row,
    price,
    band: effectiveBand,
    confidence: matched.confidence,
    basis: "live_price_band",
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
  wrap.append(badge);
  if (advice.sourceAction) {
    const source = document.createElement("div");
    source.className = "buy-advice-source";
    source.textContent = `报告动作：${advice.sourceAction}`;
    wrap.append(source);
  }
  wrap.append(sub);
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
    const adviceMatch = state.action === "all"
      || buyAdviceForItem(item, state.quotes.get(item.ticker)).key === state.action;
    const searchable = `${item.company} ${item.ticker || ""} ${item.title || ""}`.toLocaleLowerCase();
    return marketMatch && adviceMatch && (!phrase || searchable.includes(phrase));
  });

  list = [...list].sort((a, b) => {
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
  return /^-?\d+(\.\d+)?$/.test(text) || /^-?\d+(\.\d+)?[-—–~至到]\d+(\.\d+)?$/.test(text);
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
  const counts = visible.reduce((acc, item) => {
    const advice = buyAdviceForItem(item, state.quotes.get(item.ticker));
    acc[advice.key] = (acc[advice.key] || 0) + 1;
    return acc;
  }, {});
  const metrics = [
    ["当前个股", visible.length],
    ["A股", visible.filter((i) => i.market === "A股").length],
    ["港股", visible.filter((i) => i.market === "港股").length],
    ["买入/试探区", (counts.buy || 0) + (counts.trial || 0)],
    ["观察/减仓", (counts.watch || 0) + (counts.no || 0)],
  ];
  els.summary.replaceChildren();
  for (const [label, value] of metrics) {
    const card = document.createElement("div");
    card.className = "metric";
    card.innerHTML = `<span class="metric-label">${label}</span><strong class="metric-value">${value}</strong>`;
    els.summary.append(card);
  }
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

    const quote = state.quotes.get(item.ticker);
    const actionTd = document.createElement("td");
    actionTd.className = "conclusion-cell";
    actionTd.append(renderPriceActionTable(item, quote, { compact: true }));
    tr.append(actionTd);

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
  const priceRows = reportPriceRows(item);
  const tableBrief = priceRows.length ? `${priceRows.length} 档报告价格` : "未提取价格表";
  const adviceBrief = buyAdviceForItem(item, quote).label;
  els.detailSub.textContent = `${adviceBrief} · ${tableBrief} · 现价 ${formatPrice(quote)} (${change.text}) · 研报 ${item.data_cutoff || "待复核"}`;
  const sourcePath = item.valuation_section?.source_report_path || item.report_path;
  els.detailReport.href = `${repositoryUrl}${sourcePath || item.report_path}`;

  els.detailBody.replaceChildren();
  document.querySelectorAll(".detail-tabs .tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === state.detailTab);
  });

  if (state.detailTab === "overview") {
    const adviceCard = document.createElement("div");
    adviceCard.className = "card";
    const advice = buyAdviceForItem(item, quote);
    adviceCard.innerHTML = `<h3>综合操作归类</h3>`;
    const adviceBody = document.createElement("div");
    adviceBody.className = "buy-advice buy-advice-detail-card";
    const badge = document.createElement("span");
    badge.className = `zone-badge ${advice.className}`;
    badge.textContent = advice.label;
    if (advice.sourceAction) {
      const source = document.createElement("p");
      source.className = "buy-advice-source";
      source.textContent = `报告动作：${advice.sourceAction}`;
      adviceBody.append(badge, source);
    } else {
      adviceBody.append(badge);
    }
    const p = document.createElement("p");
    p.className = "source-note";
    p.textContent = advice.detail + "。规则：优先用实时价格匹配报告价格档；暂时无法比价时退回最新报告结论，并明确标注归类依据。报告结论只反映报告截止日的研究判断。仅供研究，不构成投资建议。";
    adviceBody.append(p);
    adviceCard.append(adviceBody);
    els.detailBody.append(adviceCard);

    const overview = document.createElement("div");
    overview.className = "card";
    overview.innerHTML = `<h3>报告价格行动表</h3>`;
    overview.append(renderPriceActionTable(item, quote, { compact: false }));
    if (!priceRows.length) {
      const fallback = document.createElement("p");
      fallback.className = "source-note";
      fallback.textContent = `未提取到价格行动表，回退粗粒度结论：${item.action || "未分类"}`;
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
    tip.innerHTML = `<h3>筛选依据</h3><p class="source-note">“综合操作筛选”优先采用实时价格所在的报告档位；无法可靠比价时采用最新报告结论。每只股票的归类依据会显示在操作标签下方，完整上下文请查看「估值原文」。</p>`;
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
    state.sort = "buy_advice";
    els.companyFilter.value = "";
    els.sortSelect.value = "buy_advice";
    els.marketChips.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.market === "all");
    });
    els.actionChips.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.action === "all");
    });
    renderRows();
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
