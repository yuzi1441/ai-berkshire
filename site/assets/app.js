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
  sentimentSnapshot: null,
  sentiments: new Map(),
  sentimentStatus: null,
  sentimentError: null,
  quotes: new Map(),
  selectedKey: null,
  view: "decision",
  market: "all",
  action: "all",
  trackingFilter: "all",
  sort: "buy_advice",
  detailTab: "technical",
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
  sentimentAlert: document.querySelector("#sentiment-alert"),
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
  tableWrap: document.querySelector(".table-wrap"),
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

function sentimentForItem(item) {
  return item?.ticker ? state.sentiments.get(item.ticker) || null : null;
}

function sentimentTone(score) {
  if (!Number.isFinite(Number(score))) return "sentiment-muted";
  const value = Number(score);
  if (value >= 70) return "sentiment-positive";
  if (value <= 45) return "sentiment-negative";
  return "sentiment-neutral";
}

function sentimentScoreText(score) {
  return Number.isFinite(Number(score)) ? Number(score).toFixed(1) : "—";
}

function sentimentStateText(sentiment) {
  return sentiment?.state || "无有效分数";
}

function sentimentRecencyText(news) {
  return news?.recency_state || news?.state || "暂无新闻时效信息";
}

function updateSentimentAlert() {
  if (!els.sentimentAlert) return;
  const status = state.sentimentStatus;
  if (status?.status !== "error") {
    els.sentimentAlert.hidden = true;
    els.sentimentAlert.textContent = "";
    return;
  }
  els.sentimentAlert.hidden = false;
  els.sentimentAlert.textContent = `情绪数据更新失败：${status.error || "模型未完成复核"}。当前显示上一份成功快照，不生成不完整结果。`;
}

function renderSentimentBadge(sentiment, label = "综合") {
  const badge = document.createElement("span");
  const score = sentiment?.score_0_100;
  badge.className = `sentiment-badge ${sentimentTone(score)}`;
  badge.textContent = `${label} ${sentimentScoreText(score)}`;
  return badge;
}

function renderSentimentCell(item) {
  const cell = document.createElement("td");
  cell.className = "sentiment-cell";
  cell.dataset.label = "情绪";
  const record = sentimentForItem(item);
  const combined = record?.combined_sentiment;
  cell.append(renderSentimentBadge(combined));
  const stateLine = document.createElement("div");
  stateLine.className = "sentiment-state";
  stateLine.textContent = sentimentStateText(combined);
  cell.append(stateLine);
  const freshness = document.createElement("div");
  freshness.className = "sentiment-freshness";
  freshness.textContent = state.sentimentStatus?.status === "error"
    ? `更新失败 · 上次快照 ${state.sentimentSnapshot?.data_cutoff || "未知"}`
    : record ? sentimentRecencyText(record.news_sentiment) : "情绪快照未加载";
  cell.append(freshness);
  return cell;
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

function checklistForItem(item) {
  const checklist = item?.checklist;
  return checklist && checklist.status !== "missing" ? checklist : null;
}

function checklistStatusClass(status) {
  return {
    "通过": "checklist-pass",
    "灰色地带": "checklist-gray",
    "未通过": "checklist-fail",
    "否决": "checklist-veto",
  }[status] || "checklist-pending";
}

function checklistBadgeText(checklist) {
  if (!checklist) return "未检查";
  const count = checklist.passed_count == null ? "待复核" : `${checklist.passed_count}/6`;
  return `${checklist.status || "待复核"} · ${count}`;
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

function historicalPriceReference(item) {
  const reference = item?.historical_price_reference;
  return reference && Array.isArray(reference.price_plan) && reference.price_plan.length
    ? reference
    : null;
}

function usablePriceRow(row, market) {
  return Boolean(
    row
      && row.price_range
      && row.price_range !== "未给出"
      && row.price_range !== "待复核"
      && parseReportPriceBand(row, market),
  );
}

function reportPriceRows(item, { historicalFallback = true } = {}) {
  const plans = Array.isArray(item?.price_plan) ? item.price_plan : [];
  const planRows = plans
    .filter((row) => usablePriceRow(row, item?.market) && (row.action || row.profile))
    .map((row, index) => ({
      profile: row.profile || "",
      price_range: row.price_range || "",
      action: row.action || row.profile || "见报告",
      note: row.rationale || "",
      source: "price_plan",
      index,
    }));
  if (planRows.length) return planRows;
  const stanceRows = (item?.investor_stances || [])
    .filter((row) => usablePriceRow(row, item?.market))
    .map((row, index) => ({
      profile: row.stance || row.profile || "",
      price_range: row.price_range || "",
      action: row.action || "见报告",
      note: row.note || "",
      source: "stance_fallback",
      index,
    }));
  if (stanceRows.length) return stanceRows;
  if (!historicalFallback) return [];
  const reference = historicalPriceReference(item);
  if (!reference) return [];
  return reference.price_plan
    .filter((row) => usablePriceRow(row, item?.market) && (row.action || row.profile))
    .map((row, index) => ({
      profile: row.profile || "",
      price_range: row.price_range || "",
      action: row.action || row.profile || "见报告",
      note: row.rationale || "",
      source: "historical_price_reference",
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
  const historicalReference = rows[0]?.source === "historical_price_reference"
    ? historicalPriceReference(item)
    : null;
  const wrap = document.createElement("div");
  wrap.className = compact ? "price-action-table" : "price-action-table price-action-table-detail";
  if (!rows.length) {
    const fallback = document.createElement("span");
    fallback.className = `decision ${decisionClass(item.action)}`;
    fallback.textContent = item.action || "未提取价格表";
    wrap.append(fallback);
    return wrap;
  }
  if (historicalReference) {
    const referenceNote = document.createElement("div");
    referenceNote.className = "historical-price-reference";
    const cutoff = historicalReference.source_data_cutoff || "日期未标注";
    referenceNote.textContent = `历史价格参照 · ${cutoff} · 不参与当前操作归类`;
    wrap.append(referenceNote);
    if (!compact && historicalReference.source_report_path) {
      const source = document.createElement("a");
      source.className = "historical-price-link";
      source.href = `${repositoryUrl}${historicalReference.source_report_path}`;
      source.target = "_blank";
      source.rel = "noreferrer";
      source.textContent = "查看来源报告";
      wrap.append(source);
    }
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
  const rows = reportPriceRows(item, { historicalFallback: false }).map((row) => ({
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
  const rows = reportPriceRows(item, { historicalFallback: false });
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


const TECHNICAL_DIMENSIONS = [
  ["短期（20日）", "短"],
  ["中期（60日）", "中"],
  ["长期（200日）", "长"],
  ["量能确认", "量"],
];

function technicalTone(technical) {
  if (technical?.status !== "ready") return technical?.status === "review" ? "review" : "missing";
  const state = String(technical.state || "");
  if (/防守|转弱|风险/.test(state)) return "defensive";
  if (/确认|分批|偏强/.test(state)) return "positive";
  return "neutral";
}

function technicalLight(technical, dimension) {
  return (technical?.lights || []).find((light) => light?.dimension === dimension) || null;
}

function renderTechnicalCell(item) {
  const technical = item?.technical_analysis || { status: "missing", lights: [] };
  const cell = document.createElement("td");
  cell.className = "technical-col";
  const state = document.createElement("span");
  state.className = `technical-state ${technicalTone(technical)}`;
  state.textContent = technical.status === "ready"
    ? technical.state || "待复核"
    : technical.status === "review" ? "待复核" : "未生成";
  cell.append(state);

  const lights = document.createElement("div");
  lights.className = "technical-lights";
  for (const [dimension, label] of TECHNICAL_DIMENSIONS) {
    const light = technicalLight(technical, dimension);
    const badge = document.createElement("span");
    badge.className = `technical-light ${light?.light === "绿" ? "green" : light?.light === "黄" ? "yellow" : light?.light === "红" ? "red" : "unknown"}`;
    badge.title = light ? `${dimension}：${light.light}。${light.meaning || ""}` : `${dimension}：待复核`;
    badge.textContent = `${label}${light?.light || "-"}`;
    lights.append(badge);
  }
  cell.append(lights);
  const freshness = document.createElement("span");
  freshness.className = "technical-freshness";
  freshness.textContent = technical.status === "ready"
    ? `技术日 ${technical.data_cutoff || "待复核"}`
    : technical.status === "review" ? "报告字段不完整" : "尚无技术报告";
  cell.append(freshness);
  return cell;
}

function compactTechnicalZone(value) {
  const parts = String(value || "")
    .split(/[；;]/)
    .map((part) => part.trim())
    .filter(Boolean);
  return [...new Set(parts)].join("；") || "待复核";
}

function renderTechnicalCrossCell(item) {
  const technical = item?.technical_analysis || { status: "missing" };
  const cell = document.createElement("td");
  cell.className = "technical-cross-col";

  const zone = document.createElement("div");
  zone.className = "technical-cross-zone";
  const zoneLabel = document.createElement("span");
  zoneLabel.className = "technical-cross-label";
  zoneLabel.textContent = "技术价";
  const zoneValue = document.createElement("strong");
  zoneValue.textContent = technical.status === "ready"
    ? compactTechnicalZone(technical.observation_zone)
    : technical.status === "review" ? "待复核" : "未生成";
  zone.append(zoneLabel, zoneValue);

  const overlap = document.createElement("div");
  const hasFundamentalPlan = !/未提取|无法核验/.test(String(technical.fundamental_entry_plan || ""));
  const combined = compactTechnicalZone(technical.combined_candidate_zone);
  const overlapKind = technical.status !== "ready"
    ? "pending"
    : !technical.combined_candidate_zone || !hasFundamentalPlan || technical.valid_buy_candidate === "暂不能判断"
      ? "pending"
      : /无交集/.test(combined) ? "none" : "overlap";
  overlap.className = `technical-cross-overlap ${overlapKind}`;
  const overlapLabel = document.createElement("span");
  overlapLabel.className = "technical-cross-label";
  overlapLabel.textContent = "基本面交叉";
  const overlapValue = document.createElement("strong");
  overlapValue.textContent = technical.status !== "ready"
    ? "待复核"
    : overlapKind === "pending" ? "待复核"
      : overlapKind === "none" ? "无交集"
        : combined;
  overlap.append(overlapLabel, overlapValue);

  cell.append(zone, overlap);
  return cell;
}

function renderTechnicalDetail(item) {
  const technical = item?.technical_analysis || { status: "missing", lights: [] };
  const card = document.createElement("section");
  card.className = "card technical-detail";
  const title = document.createElement("h3");
  title.textContent = "技术面辅助观察";
  card.append(title);

  const disclaimer = document.createElement("p");
  disclaimer.className = "technical-disclaimer";
  disclaimer.textContent = "技术面仅辅助观察，不参与综合操作归类、筛选或买入建议。";
  card.append(disclaimer);

  if (technical.status === "missing") {
    const empty = document.createElement("p");
    empty.className = "technical-empty";
    empty.textContent = "未生成技术面报告。生成后会按技术指标的实际数据截止日自动显示。";
    card.append(empty);
    els.detailBody.append(card);
    return;
  }
  if (technical.status === "review") {
    const empty = document.createElement("p");
    empty.className = "technical-empty";
    empty.textContent = "技术面报告待复核，暂不显示推断后的指标或状态。";
    card.append(empty);
    if (technical.report_path) {
      const link = document.createElement("a");
      link.className = "btn ghost";
      link.href = `${repositoryUrl}${technical.report_path}`;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = "打开技术面报告";
      card.append(link);
    }
    els.detailBody.append(card);
    return;
  }

  const summary = document.createElement("dl");
  summary.className = "technical-summary";
  const rows = [
    ["技术状态", technical.state || "待复核"],
    ["技术日", technical.data_cutoff || "待复核"],
    ["技术收盘价", technical.latest_price != null ? `${technical.latest_price} ${technical.currency || ""}`.trim() : "待复核"],
    ["技术观察区", technical.observation_zone || "待复核"],
    ["数据质量", technical.confidence || "待复核"],
  ];
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  card.append(summary);

  const grid = document.createElement("div");
  grid.className = "technical-light-grid";
  for (const [dimension, label] of TECHNICAL_DIMENSIONS) {
    const light = technicalLight(technical, dimension);
    const itemNode = document.createElement("div");
    itemNode.className = "technical-light-card";
    itemNode.innerHTML = `<span>${label}期</span><strong class="${light?.light === "绿" ? "green" : light?.light === "黄" ? "yellow" : "red"}">${light?.light || "待复核"}</strong>`;
    const meaning = document.createElement("p");
    meaning.textContent = light?.meaning || "未提供说明";
    itemNode.append(meaning);
    grid.append(itemNode);
  }
  card.append(grid);
  if (technical.report_path) {
    const link = document.createElement("a");
    link.className = "btn ghost";
    link.href = `${repositoryUrl}${technical.report_path}`;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "打开技术面报告";
    card.append(link);
  }
  els.detailBody.append(card);
}

function renderNewsList(title, news, {emptyText = "暂无抓取新闻"} = {}) {
  const card = document.createElement("section");
  card.className = "card sentiment-news-card";
  const heading = document.createElement("h3");
  heading.textContent = title;
  card.append(heading);
  const items = news?.captured_items || news?.items || [];
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "sentiment-empty";
    empty.textContent = emptyText;
    card.append(empty);
    return card;
  }
  const list = document.createElement("div");
  list.className = "sentiment-news-list";
  for (const item of items) {
    const row = document.createElement("article");
    row.className = `sentiment-news-item ${item.included === false ? "filtered" : "included"}`;
    const header = document.createElement("div");
    header.className = "sentiment-news-head";
    const titleNode = item.url ? document.createElement("a") : document.createElement("strong");
    titleNode.textContent = item.title || "无标题新闻";
    if (item.url) {
      titleNode.href = item.url;
      titleNode.target = "_blank";
      titleNode.rel = "noreferrer";
    }
    header.append(titleNode);
    const inclusion = document.createElement("span");
    inclusion.className = `sentiment-news-tag ${item.included === false ? "filtered" : "included"}`;
    inclusion.textContent = item.included === false ? "未纳入评分" : "已纳入评分";
    header.append(inclusion);
    row.append(header);

    const meta = document.createElement("div");
    meta.className = "sentiment-news-meta";
    const dateText = item.published_at ? String(item.published_at).replace("T", " ").slice(0, 16) : "日期未知";
    meta.textContent = `${dateText} · ${item.publisher || "未知来源"} · ${item.event_type || "一般新闻"}`;
    row.append(meta);

    if (item.summary) {
      const summary = document.createElement("p");
      summary.className = "sentiment-news-summary";
      summary.textContent = item.summary;
      row.append(summary);
    }

    const metrics = document.createElement("div");
    metrics.className = "sentiment-news-metrics";
    metrics.textContent = item.included === false
      ? `${item.filter_reason || "未达到相关性阈值"} · 相关性 ${sentimentScoreText(Number(item.relevance) * 100)}%`
      : `方向 ${Number(item.direction || 0) > 0 ? "正面" : Number(item.direction || 0) < 0 ? "负面" : "中性"} · 相关性 ${sentimentScoreText(Number(item.relevance) * 100)}% · 时间权重 ${sentimentScoreText(Number(item.time_weight) * 100)}%`;
    row.append(metrics);
    list.append(row);
  }
  card.append(list);
  return card;
}

function renderChecklistDetail(item) {
  const checklist = checklistForItem(item);
  if (!checklist) {
    const card = document.createElement("section");
    card.className = "card checklist-empty";
    card.innerHTML = "<h3>尚未生成买入前 Checklist</h3>";
    const note = document.createElement("p");
    note.className = "source-note";
    note.textContent = "该公司当前没有可识别的 company-checklist 报告；这不会改变基本面主报告的结论。";
    card.append(note);
    els.detailBody.append(card);
    return;
  }

  const summaryCard = document.createElement("section");
  summaryCard.className = `card checklist-summary-card ${checklistStatusClass(checklist.status)}`;
  const heading = document.createElement("h3");
  heading.textContent = "买入前 Checklist";
  summaryCard.append(heading);
  const summary = document.createElement("dl");
  summary.className = "kv-grid checklist-summary";
  const passed = checklist.passed_count == null ? "待复核" : `${checklist.passed_count}/${checklist.total_gates || 6} 关`;
  const fields = [
    ["Checklist结论", checklist.status || "待复核"],
    ["通过关数", passed],
    ["硬性否决", checklist.hard_veto_label || "待复核"],
    ["镜子测试", checklist.mirror_test || "待复核"],
    ["研究置信度", checklist.confidence || "待复核"],
    ["数据截止", checklist.data_cutoff || "待复核"],
    ["下次复核", checklist.next_review_date || "未安排"],
  ];
  for (const [label, value] of fields) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  summaryCard.append(summary);
  if (checklist.summary) {
    const note = document.createElement("p");
    note.className = "checklist-conclusion";
    note.textContent = checklist.summary;
    summaryCard.append(note);
  }
  if (checklist.hard_veto) {
    const warning = document.createElement("p");
    warning.className = "checklist-warning";
    warning.textContent = "已识别硬性否决信号：Checklist 只允许把该标的挡在新增买入流程外，不会自动改写主研报动作。";
    summaryCard.append(warning);
  }
  els.detailBody.append(summaryCard);

  const gateCard = document.createElement("section");
  gateCard.className = "card";
  const gateTitle = document.createElement("h3");
  gateTitle.textContent = "六关评分";
  gateCard.append(gateTitle);
  const grid = document.createElement("div");
  grid.className = "checklist-gate-grid";
  for (const gate of checklist.gates || []) {
    const row = document.createElement("article");
    row.className = "checklist-gate";
    const head = document.createElement("div");
    head.className = "checklist-gate-head";
    const name = document.createElement("strong");
    name.textContent = gate.name || "未命名关卡";
    const score = document.createElement("span");
    score.className = "checklist-score";
    score.textContent = gate.score || "待复核";
    head.append(name, score);
    row.append(head);
    const result = document.createElement("div");
    result.className = "checklist-result";
    result.textContent = gate.result || "待复核";
    row.append(result);
    if (gate.reason) {
      const reason = document.createElement("p");
      reason.textContent = gate.reason;
      row.append(reason);
    }
    grid.append(row);
  }
  if (!grid.childElementCount) {
    const empty = document.createElement("p");
    empty.className = "source-note";
    empty.textContent = "报告未提供可结构化的六关评分表，请打开原报告复核。";
    gateCard.append(empty);
  } else {
    gateCard.append(grid);
  }
  els.detailBody.append(gateCard);

  const history = checklist.history || [];
  if (history.length > 1) {
    const historyCard = document.createElement("section");
    historyCard.className = "card";
    const historyTitle = document.createElement("h3");
    historyTitle.textContent = "Checklist历史";
    historyCard.append(historyTitle);
    const list = document.createElement("div");
    list.className = "checklist-history-list";
    for (const entry of history) {
      const line = document.createElement("div");
      line.className = "checklist-history-row";
      line.textContent = `${entry.data_cutoff || "待复核"} · ${entry.status || "待复核"} · ${entry.action || "未给出"}`;
      list.append(line);
    }
    historyCard.append(list);
    els.detailBody.append(historyCard);
  }

  const footer = document.createElement("p");
  footer.className = "source-note";
  footer.textContent = "Checklist 是买入前筛选闸门，不覆盖基本面主研报、技术面或情绪面的独立结论。";
  if (checklist.report_path) {
    const link = document.createElement("a");
    link.href = `${repositoryUrl}${checklist.report_path}`;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "打开完整 Checklist 报告";
    footer.append(" ", link);
  }
  els.detailBody.append(footer);
}

function renderSentimentDetail(item) {
  const record = sentimentForItem(item);
  const card = document.createElement("section");
  card.className = "card sentiment-detail";
  const title = document.createElement("h3");
  title.textContent = "情绪摘要";
  card.append(title);
  if (!record) {
    const empty = document.createElement("p");
    empty.className = "sentiment-empty";
    empty.textContent = state.sentimentError ? "情绪快照暂时无法加载" : "该股票暂无情绪快照";
    card.append(empty);
    els.detailBody.append(card);
    return;
  }
  if (state.sentimentStatus?.status === "error") {
    const warning = document.createElement("p");
    warning.className = "sentiment-warning-note";
    warning.textContent = `本次更新失败：${state.sentimentStatus.error || "模型未完成复核"}。以下内容来自上一份成功快照。`;
    card.append(warning);
  }
  const summary = document.createElement("dl");
  summary.className = "kv-grid sentiment-summary";
  const industry = record.industry_sentiment || record.industry_detail;
  const rows = [
    ["综合情绪", `${sentimentScoreText(record.combined_sentiment?.score_0_100)} · ${sentimentStateText(record.combined_sentiment)}`],
    ["个股新闻", `${sentimentScoreText(record.news_sentiment?.score_0_100)} · ${sentimentStateText(record.news_sentiment)}`],
    ["行业情绪", `${sentimentScoreText(industry?.score_0_100)} · ${sentimentStateText(industry)}`],
    ["新闻时效", sentimentRecencyText(record.news_sentiment)],
    ["情绪数据截止", state.sentimentSnapshot?.data_cutoff || "待复核"],
  ];
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  card.append(summary);
  const note = document.createElement("p");
  note.className = "source-note";
  note.textContent = "综合情绪仅作为研究辅助；旧闻会按时间衰减，未纳入评分的新闻仅供核查，不会影响分数。";
  card.append(note);
  els.detailBody.append(card);

  els.detailBody.append(renderNewsList("个股新闻 · 全部抓取结果", record.news_sentiment, {
    emptyText: record.news_sentiment?.state || "暂无个股新闻",
  }));
  els.detailBody.append(renderNewsList("行业新闻 · 全部抓取结果", record.industry_detail, {
    emptyText: industry?.state || "暂无行业新闻",
  }));
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
    ["情绪可用", `${visible.filter((i) => sentimentForItem(i)?.combined_sentiment?.score_0_100 != null).length}/${visible.length}`],
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
  setTableHeader([
    "公司",
    "市场 / 代码",
    "情绪",
    "报告价格行动表",
    "现价",
    "综合操作归类",
    "技术面（辅助）",
    "技术价 / 基本面交叉",
  ]);

  visible.forEach((item, index) => {
    const tr = document.createElement("tr");
    const key = itemKey(item);
    if (key === state.selectedKey) tr.classList.add("active");
    tr.dataset.key = key;
    tr.dataset.index = String(index);
    tr.tabIndex = 0;

    const companyTd = document.createElement("td");
    companyTd.className = "company-cell";
    companyTd.innerHTML = `<div class="company-name">${item.company}</div><div class="company-meta">${item.technical_analysis?.status === "ready" ? "已接入技术面" : "技术面待补"}</div>`;
    const checklist = item.checklist;
    const checklistBadge = document.createElement("span");
    checklistBadge.className = `checklist-badge ${checklistStatusClass(checklist?.status)}`;
    checklistBadge.textContent = checklistBadgeText(checklistForItem(item));
    companyTd.append(checklistBadge);
    tr.append(companyTd);

    const marketTd = document.createElement("td");
    marketTd.innerHTML = `<span class="market-badge ${marketBadgeClass(item.market)}">${item.market || "未识别"}</span><div class="ticker-code">${item.ticker || "无代码"}</div>`;
    tr.append(marketTd);

    tr.append(renderSentimentCell(item));

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

    tr.append(renderTechnicalCell(item));
    tr.append(renderTechnicalCrossCell(item));

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
    document.body.classList.remove("drawer-open");
    els.detailPanel.hidden = true;
    els.workspace.classList.remove("detail-open");
    return;
  }
  document.body.classList.add("drawer-open");
  els.detailPanel.hidden = false;
  els.workspace.classList.add("detail-open");
  els.detailTitle.textContent = item.company;
  const quote = state.quotes.get(item.ticker);
  const change = formatChange(quote);
  els.detailKicker.textContent = `${item.market || "未识别"} · ${item.ticker || "无代码"}`;
  const priceRows = reportPriceRows(item);
  const historicalReference = priceRows[0]?.source === "historical_price_reference";
  const tableBrief = priceRows.length
    ? `${priceRows.length} 档${historicalReference ? "历史价格参照" : "报告价格"}`
    : "未提取价格表";
  const adviceBrief = buyAdviceForItem(item, quote).label;
  els.detailSub.textContent = `${adviceBrief} · ${tableBrief} · 现价 ${formatPrice(quote)} (${change.text}) · 研报 ${item.data_cutoff || "待复核"}`;
  els.detailReport.href = `${repositoryUrl}${item.report_path}`;

  els.detailBody.replaceChildren();
  const tracking = trackingForItem(item);
  const trackingTab = document.querySelector(".tracking-tab");
  if (trackingTab) {
    trackingTab.hidden = !tracking;
    if (!tracking && state.detailTab === "tracking") state.detailTab = "overview";
  }
  const checklistTab = document.querySelector(".checklist-tab");
  const hasChecklist = Boolean(checklistForItem(item));
  if (checklistTab) {
    checklistTab.hidden = !hasChecklist;
    if (!hasChecklist && state.detailTab === "checklist") state.detailTab = "overview";
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
    tip.innerHTML = `<h3>筛选依据</h3><p class="source-note">“综合操作筛选”优先采用实时价格所在的报告档位；无法可靠比价时采用最新报告结论。技术面不会改变上述筛选结果，完整基本面上下文请打开主报告。</p>`;
    els.detailBody.append(tip);
    return;
  }

  if (state.detailTab === "technical") {
    renderTechnicalDetail(item);
    return;
  }

  if (state.detailTab === "sentiment") {
    renderSentimentDetail(item);
    return;
  }

  if (state.detailTab === "checklist") {
    renderChecklistDetail(item);
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
    const historyPriceItem = {
      ...snap,
      market: item.market,
      ticker: item.ticker,
    };
    const historicalPriceRows = reportPriceRows(historyPriceItem, { historicalFallback: false });
    if (historicalPriceRows.length) {
      const priceTitle = document.createElement("p");
      priceTitle.className = "history-price-title";
      priceTitle.textContent = "当期价格行动表（不与当前行情匹配）";
      card.append(priceTitle, renderPriceActionTable(historyPriceItem, null, { compact: false }));
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

function revealTableRow(row) {
  const wrap = els.tableWrap;
  if (!row || !wrap || wrap.scrollHeight <= wrap.clientHeight) return;
  const wrapRect = wrap.getBoundingClientRect();
  const header = wrap.querySelector("thead");
  const topLimit = wrapRect.top + (header?.getBoundingClientRect().height || 0);
  const bottomLimit = wrapRect.bottom;
  const rowRect = row.getBoundingClientRect();
  let delta = 0;
  if (rowRect.top < topLimit) delta = rowRect.top - topLimit;
  else if (rowRect.bottom > bottomLimit) delta = rowRect.bottom - bottomLimit;
  if (delta) wrap.scrollTop += delta;
}

function openDetail(item, { scrollRow = true, updateUrl = true } = {}) {
  if (!item) return;
  const pageScrollY = window.scrollY;
  state.selectedKey = itemKey(item);
  const visible = filteredDecisions();
  state.focusIndex = visible.findIndex((x) => itemKey(x) === state.selectedKey);
  if (updateUrl) updateHash(item);
  renderRows();
  renderDetail();
  if (els.detailBody) els.detailBody.scrollTop = 0;
  if (window.scrollY !== pageScrollY) window.scrollTo(0, pageScrollY);
  if (scrollRow) {
    const row = els.rows.querySelector(`tr[data-key="${CSS.escape(state.selectedKey)}"]`);
    revealTableRow(row);
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
    if (els.detailBody) els.detailBody.scrollTop = 0;
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
      state.detailTab = "technical";
      renderDetail();
    } else if (event.key === "o" && selectedItem()) {
      els.detailReport.click();
    }
  });
}

async function loadSentimentSnapshot() {
  const statusResponse = await fetch(`./data/sentiment_status.json?t=${Date.now()}`, { cache: "no-store" });
  state.sentimentStatus = statusResponse.ok
    ? await statusResponse.json()
    : {status: "unknown"};
  const response = await fetch(`./data/sentiment.json?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("无法加载 sentiment.json");
  const snapshot = await response.json();
  state.sentimentSnapshot = snapshot;
  state.sentiments = new Map(
    (snapshot.companies || [])
      .filter((item) => item?.ticker)
      .map((item) => [item.ticker, {
        ...item,
        industry_detail: snapshot.industry_sentiments?.[item.industry]?.sentiment || null,
      }]),
  );
  updateSentimentAlert();
}

async function loadDashboard() {
  setLiveStatus("idle", "加载决策数据…");
  const response = await fetch(`./data/decision_board.json?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("无法加载 decision_board.json");
  const board = await response.json();
  state.decisions = board.decisions || [];
  try {
    await loadSentimentSnapshot();
  } catch (error) {
    state.sentimentError = error;
    state.sentimentStatus = {status: "error", error: error.message};
    state.sentimentSnapshot = null;
    state.sentiments = new Map();
    updateSentimentAlert();
  }
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
