import { currentExecutionState, humanReviewExecutionState } from "./action-classifier.mjs";

/*
 * Frontend rebuild contract
 * -------------------------
 * The page reads the already-built read models only. It never derives a new
 * lifecycle, rewrites a source-of-truth file, or asks Markdown to explain a
 * company at render time. The backend enums stay English; only this map is
 * allowed to turn them into user-facing language.
 */
const LABELS = {
  lifecycle: { WATCH: "观察中", PRE_BUY: "买入前", HOLDING: "持有中", EXITED: "已退出" },
  lifecycleHint: { WATCH: "等待条件或价格", PRE_BUY: "可进入买入前检查", HOLDING: "优先管理已有仓位", EXITED: "历史持仓周期" },
  scope: { entry: "买入条件", validation: "验证条件", redline: "失效条件", unknown: "其他条件" },
  ruleStatus: { triggered: "已触发", near_trigger: "接近触发", not_triggered: "未触发", unknown: "待判断", needs_review: "需要复核", stale: "数据过期" },
  ruleType: { PRICE_RANGE: "价格条件", METRIC: "经营条件", EVENT: "事件条件" },
  action: {
    run_checklist: "进行买入前检查",
    run_drift: "进行论文漂移检查",
    drift_recheck: "Drift 待复核 · 证据不足",
    keep_watch: "继续观察",
    review_decision: "重新评估",
    drop_or_recheck: "降级观察 / 重新检查",
    exit_review: "退出复核",
    hold: "继续持有",
    add_reduce_review: "加仓 / 减仓复核",
    confirm_purchase: "确认买入条件",
    price_near_trigger: "接近价格条件",
    none: "暂不处理",
  },
  drift: { improved: "论文增强", unchanged: "论文未变", weakened: "论文减弱", broken: "论文失效", unknown: "尚未复核" },
  eventState: { important: "重要事件", watch: "普通观察", normal: "暂无重大变化", unknown: "未知", partial: "部分可用" },
  technical: { UP: "上升", DOWN: "下降", SIDEWAYS: "震荡", UNKNOWN: "未知", BROKEN: "弱势区间", NEAR_MEAN: "接近均值", EXTENDED: "偏离均值", FAVORABLE: "有利", UNFAVORABLE: "不利", NEUTRAL: "一般" },
  sentiment: { positive: "偏正面", neutral: "中性", negative: "偏负面", mixed: "分化", unknown: "未知" },
  dataStatus: { fresh: "新鲜", partial: "部分可用", stale: "数据过期", unknown: "未知", unavailable: "不可用", unsupported: "暂不支持", ready: "已准备" },
};

const WORKSPACES = {
  attention: "今日处理",
  holdings: "我的持仓",
  opportunities: "买入候选",
  "ai-research": "AI研究机会",
  watchlist: "研究池",
};

// Legacy report-review names remain as non-rendering contract markers. The old
// dense table is intentionally gone; report evidence now lives in the drawer.
// renderFundamentalReviewRows / renderFundamentalReviewDetail / renderFundamentalReviewPartitions
// fundamentalReviewPartitionKey / renderReviewLayerCell / main_report_review.json
// state.detailTab === "report-review" is not a route in the new information architecture.
// semantic_group remains an audit vocabulary marker; no report-review UI is rendered here.
// 日常复核 / 深度复核 remain historical vocabulary only; the rebuilt drawer is the sole detail surface.
// Historical source-check vocabulary only: referenceExecutionState humanReviewAction
// human_review_plan "improving", "条件改善" reviewHasImprovement fundamentalReviewFilterMatches
// renderHumanReviewPlan renderHumanReviewMainCell renderReviewLayerKeyData 关键数据 主报告要求 本次抓取
// 与要求对照 详情摘要 同层补充 reviewRunMissingFields 未获取： 已保存摘要（当前值未结构化）
// setTableHeader(["公司 / 代码", "当前状态", "数据对照", "证据时间"])
// renderFundamentalReviewEvidenceComparison renderReviewDataCell renderReviewMetricTable
// 主报告要求与当前数据 数据对照 已达标 转负 未获取 fundamental-review-data-cell
// report-review-data-grid 本次抓取 / 对照摘要 主报告历史参考（不作为当前值）
// report-review-evidence-task-grid 主报告原文 report-review-evidence-shared-source 正文只显示一次
// renderReportExcerpt 原文摘录 内容未改写 抓取依据 / 原文定位
// humanReviewTd.append(renderHumanReviewMainCell(item, quote)) humanReviewTaskCompactDateText
// humanReviewTaskDateText 东财+巨潮核验 "当前状态" renderExecutionMainCell renderIdentityCell
// renderTechnicalCell(item, { includeCross: true }) loadOpportunityScansSnapshot generation_id
// const aShareVisible = visible.filter((item) => item.market === "A股")
// ["待人工复核", manualReviewCount] opportunityScans
void currentExecutionState;
void humanReviewExecutionState;
void LABELS;

const DATA_FILES = {
  board: "./data/decision_board.json",
  companyState: "./data/company_state.json",
  rules: "./data/decision_rules.json",
  events: "./data/event_radar.json",
  technical: "./data/technical_latest.json",
  sentiment: "./data/sentiment.json",
  sentimentStatus: "./data/sentiment_status.json",
  tracking: "./data/post_buy_tracking.json",
  quotes: "./data/quotes/latest.json",
  intraday: "./data/intraday_technical.json",
  opportunityScans: "./data/opportunity_scans.json",
};

const OPTIONAL_DATA_FALLBACKS = {
  events: { companies: [] },
  technical: { companies: [] },
  sentiment: { companies: [], status: "unknown" },
  sentimentStatus: { status: "unknown" },
  quotes: { quotes: [] },
  intraday: { companies: [] },
  opportunityScans: { schema_version: 1, status: "unavailable", scans: [] },
};

const state = {
  board: null,
  companyState: new Map(),
  rulePackages: new Map(),
  events: new Map(),
  technical: new Map(),
  sentiment: new Map(),
  tracking: new Map(),
  quotes: new Map(),
  quoteMeta: null,
  sentimentMeta: null,
  opportunityScans: new Map(),
  opportunityScanMeta: { status: "missing", scans: [] },
  loadedAt: null,
  opportunityView: "price",
  attentionExpanded: false,
  opportunityExpanded: false,
  aiOpportunityExpanded: false,
  search: "",
  market: "all",
  lifecycle: "all",
  opportunity: "all",
  sort: "attention",
  page: 1,
  selectedTicker: null,
  workspace: "attention",
};

const els = {
  lastUpdated: document.querySelector("#last-updated"),
  datasetSummary: document.querySelector("#dataset-summary"),
  quoteStatus: document.querySelector("#quote-status"),
  quoteStatusText: document.querySelector("#quote-status-text"),
  refresh: document.querySelector("#refresh-data"),
  statusCards: document.querySelector("#status-cards"),
  attentionList: document.querySelector("#attention-list"),
  attentionCount: document.querySelector("#attention-count"),
  attentionViewAll: document.querySelector("#attention-view-all"),
  priceCount: document.querySelector("#price-count"),
  conditionCount: document.querySelector("#condition-count"),
  checklistCount: document.querySelector("#checklist-count"),
  opportunityList: document.querySelector("#opportunity-list"),
  opportunityViewAll: document.querySelector("#opportunity-view-all"),
  aiOpportunityList: document.querySelector("#ai-opportunity-list"),
  aiOpportunityMeta: document.querySelector("#ai-opportunity-meta"),
  aiOpportunityViewAll: document.querySelector("#ai-opportunity-view-all"),
  holdingList: document.querySelector("#holding-list"),
  holdingCount: document.querySelector("#holding-count"),
  watchlist: document.querySelector("#watchlist"),
  watchlistCount: document.querySelector("#watchlist-count"),
  watchlistMeta: document.querySelector("#watchlist-meta"),
  loadMore: document.querySelector("#load-more"),
  emptyState: document.querySelector("#empty-state"),
  search: document.querySelector("#company-search"),
  market: document.querySelector("#market-filter"),
  lifecycle: document.querySelector("#lifecycle-filter"),
  opportunity: document.querySelector("#opportunity-filter"),
  sort: document.querySelector("#sort-filter"),
  clearFilters: document.querySelector("#clear-filters"),
  drawer: document.querySelector("#detail-drawer"),
  backdrop: document.querySelector("#drawer-backdrop"),
  drawerKicker: document.querySelector("#drawer-kicker"),
  drawerTitle: document.querySelector("#drawer-title"),
  drawerSubtitle: document.querySelector("#drawer-subtitle"),
  drawerContent: document.querySelector("#drawer-content"),
  drawerClose: document.querySelector("#drawer-close"),
  toast: document.querySelector("#toast"),
  workspaceNav: document.querySelector(".workspace-nav"),
  workspacePanels: [...document.querySelectorAll("[data-workspace-panel]")],
  activeWorkspaceTitle: document.querySelector("#active-workspace-title"),
  navAttentionCount: document.querySelector("#nav-attention-count"),
  navHoldingsCount: document.querySelector("#nav-holdings-count"),
  navOpportunitiesCount: document.querySelector("#nav-opportunities-count"),
  navAiCount: document.querySelector("#nav-ai-count"),
  navWatchlistCount: document.querySelector("#nav-watchlist-count"),
};

const repositoryUrl = "https://github.com/yuzi1441/ai-berkshire/blob/main/";
const PAGE_SIZE = 14;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function text(value, fallback = "—") {
  const normalized = String(value ?? "").trim();
  return normalized || fallback;
}

function label(group, value, fallback = "待复核") {
  return LABELS[group]?.[value] || (value ? String(value) : fallback);
}

function formatDateTime(value) {
  if (!value) return "—";
  const raw = String(value).replace("T", " ").replace(/([+-]\d\d:\d\d|Z)$/, "");
  return raw.length > 16 ? raw.slice(0, 16) : raw;
}

function formatDate(value) {
  return value ? String(value).slice(0, 10) : "—";
}

function formatNumber(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return number.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function formatPrice(quote, fallback = "—") {
  if (!quote || !Number.isFinite(Number(quote.price))) return fallback;
  const currency = quote.currency === "HKD" ? "HK$" : quote.currency === "USD" ? "US$" : "¥";
  return `${currency}${formatNumber(quote.price, 2)}`;
}

function reportHref(path) {
  if (!path) return "#";
  return repositoryUrl + String(path).split("/").map(encodeURIComponent).join("/");
}

function lifecycleOf(record) {
  return record?.lifecycle || "WATCH";
}

function quoteFor(record) {
  return state.quotes.get(record?.ticker) || null;
}

function rulesFor(record) {
  const pack = state.rulePackages.get(record?.ticker);
  return Array.isArray(pack?.rules) ? pack.rules : [];
}

function trackingFor(record) {
  return state.tracking.get(record?.ticker) || record?.post_buy_tracking || null;
}

function priceOpportunities(record) {
  return Array.isArray(record?.price_opportunities) ? record.price_opportunities : [];
}

function conditionOpportunities(record) {
  return Array.isArray(record?.condition_opportunities) ? record.condition_opportunities : [];
}

function triggeredRules(record) {
  return rulesFor(record).filter((rule) => rule.status === "triggered");
}

function nearRules(record) {
  return rulesFor(record).filter((rule) => rule.status === "near_trigger");
}

function hasAttention(record) {
  const drift = record?.drift || {};
  const event = record?.event_radar || {};
  const tracking = trackingFor(record);
  return Boolean(
    record?.needs_attention
      || event.thesis_relevant
      || ["weakened", "broken"].includes(drift.direction)
      || triggeredRules(record).length
      || (tracking?.alerts || []).length,
  );
}

function actionLabel(record) {
  const scan = record?.drift_scan || {};
  if (record?.next_action === "run_drift" && scan.status === "stale") return "需要重新 Drift 检测";
  if (record?.next_action === "drift_recheck") return "Drift 待复核 · 证据不足";
  return label("action", record?.next_action, "继续观察");
}

function driftScanLabel(record) {
  const scan = record?.drift_scan || {};
  if (scan.status === "current" && scan.result === "unchanged") return "Drift 已复核 · 无变化";
  if (scan.status === "current" && scan.result === "unknown") return "Drift 待复核 · 证据不足";
  if (scan.status === "stale") return "需要重新 Drift 检测";
  if (scan.status === "missing") return "尚未进行 Drift 检测";
  return label("drift", record?.drift?.direction);
}

function ruleActionLabel(rule) {
  return rule?.action ? label("action", rule.action, "动作待确认") : "动作待确认";
}

function actionTone(action) {
  if (["run_drift", "drop_or_recheck", "exit_review"].includes(action)) return "red";
  if (["run_checklist", "review_decision", "confirm_purchase", "drift_recheck"].includes(action)) return "yellow";
  return "blue";
}

function dataLabel(status, fallback = "未知") {
  return LABELS.dataStatus[status] || fallback;
}

function stateRecords() {
  return [...state.companyState.values()];
}

function stateCount(lifecycle) {
  return stateRecords().filter((record) => lifecycleOf(record) === lifecycle).length;
}

function decodeHashValue(value) {
  try { return decodeURIComponent(value); } catch { return null; }
}

function routeFromLocation() {
  const raw = location.hash.replace(/^#/, "");
  const workspacePart = raw.split("/", 1)[0];
  const workspace = WORKSPACES[workspacePart] ? workspacePart : "attention";
  const companyPart = raw.match(/(?:^|\/)company=(.+)$/)?.[1];
  return { workspace, ticker: companyPart ? decodeHashValue(companyPart) : null };
}

function aiNavigationCount() {
  const status = state.opportunityScanMeta?.status;
  const items = aiOpportunityItems();
  if (["ok", "ready"].includes(status)) return String(items.length);
  if (status === "partial" && items.length) return String(items.length);
  return "—";
}

function renderWorkspaceNav() {
  const attentionToday = attentionRecords().filter((record) => attentionTier(record) === "must").length;
  const counts = {
    attention: attentionToday,
    holdings: stateCount("HOLDING"),
    opportunities: stateCount("PRE_BUY"),
    "ai-research": aiNavigationCount(),
    watchlist: stateRecords().filter((record) => lifecycleOf(record) !== "HOLDING").length,
  };
  const elements = {
    attention: els.navAttentionCount,
    holdings: els.navHoldingsCount,
    opportunities: els.navOpportunitiesCount,
    "ai-research": els.navAiCount,
    watchlist: els.navWatchlistCount,
  };
  for (const [workspace, element] of Object.entries(elements)) {
    if (element) element.textContent = String(counts[workspace]);
  }
}

function setWorkspace(workspace, { historyMode = "push" } = {}) {
  const nextWorkspace = WORKSPACES[workspace] ? workspace : "attention";
  state.workspace = nextWorkspace;
  for (const panel of els.workspacePanels) {
    const active = panel.dataset.workspacePanel === nextWorkspace;
    panel.hidden = !active;
    panel.setAttribute("aria-hidden", String(!active));
  }
  els.workspaceNav?.querySelectorAll("[data-workspace]").forEach((button) => {
    const active = button.dataset.workspace === nextWorkspace;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (els.activeWorkspaceTitle) els.activeWorkspaceTitle.textContent = WORKSPACES[nextWorkspace];
  if (historyMode === "push" && location.hash !== `#${nextWorkspace}`) {
    history.pushState(null, "", `#${nextWorkspace}`);
  }
}

function hideDetailDrawer() {
  state.selectedTicker = null;
  els.backdrop.hidden = true;
  els.drawer.hidden = true;
  document.body.classList.remove("drawer-open");
}

function syncWorkspaceFromLocation() {
  const route = routeFromLocation();
  const raw = location.hash.replace(/^#/, "");
  const hasCompanyRoute = raw.startsWith("company=") || raw.includes("/company=");
  if (raw && !WORKSPACES[raw.split("/", 1)[0]] && !hasCompanyRoute) {
    history.replaceState(null, "", "#attention");
  }
  setWorkspace(route.workspace, { historyMode: "none" });
  if (route.ticker && state.companyState.has(route.ticker)) openDetail(route.ticker);
  else if (!route.ticker && !els.drawer.hidden) hideDetailDrawer();
}

function attentionReason(record) {
  const reasons = [];
  const event = record?.event_radar || {};
  const drift = record?.drift || {};
  const tracking = trackingFor(record);
  const triggered = triggeredRules(record);
  if (event.thesis_relevant) {
    const eventItem = (event.events || []).find((item) => item.thesis_relevant) || (event.events || [])[0];
    reasons.push(`事件：${text(eventItem?.headline, "存在论文相关事件")}`);
  }
  if (drift.direction && drift.direction !== "unknown" && drift.direction !== "unchanged") reasons.push(`论文：${label("drift", drift.direction)}`);
  if (triggered.length) reasons.push(`规则：${triggered.length} 条已触发`);
  if (nearRules(record).length) reasons.push(`价格 / 条件：${nearRules(record).length} 条接近触发`);
  if ((tracking?.alerts || []).length) reasons.push(`持仓：${tracking.alerts[0]?.detail || "有待处理提醒"}`);
  return reasons.slice(0, 2).join("；") || "需要重新核对当前状态";
}

function hasFormalImportantEvent(record) {
  const radar = record?.event_radar || {};
  const events = Array.isArray(radar.events) ? radar.events : [];
  return Boolean(
    radar.state === "important"
      && events.some((event) => ["A", "B"].includes(event.highest_source_tier) && (event.state === "important" || event.thesis_relevant)),
  );
}

function reviewDue(record) {
  const nextReview = trackingFor(record)?.next_review_date;
  if (!nextReview) return false;
  const today = new Date().toISOString().slice(0, 10);
  return String(nextReview).slice(0, 10) <= today;
}

function attentionTier(record) {
  const drift = record?.drift || {};
  const triggered = triggeredRules(record);
  const holdingAlert = lifecycleOf(record) === "HOLDING" && (trackingFor(record)?.alerts || []).length > 0;
  const preBuyChecklist = lifecycleOf(record) === "PRE_BUY" && record?.next_action === "run_checklist";
  if (
    ["weakened", "broken"].includes(drift.direction)
      || triggered.some((rule) => rule.rule_scope === "redline")
      || holdingAlert
      || hasFormalImportantEvent(record)
      || preBuyChecklist
  ) return "must";
  if (
    nearRules(record).length
      || priceOpportunities(record).some((item) => item.status === "near_trigger")
      || conditionOpportunities(record).some((item) => item.status === "near_trigger")
      || reviewDue(record)
  ) return "soon";
  return "changes";
}

function attentionTierLabel(tier) {
  return { must: "今日必须处理", soon: "近期关注", changes: "普通变化" }[tier] || "普通变化";
}

function attentionReasonType(record) {
  const drift = record?.drift || {};
  if (triggeredRules(record).some((rule) => rule.rule_scope === "redline")) return "失效条件";
  if (["weakened", "broken"].includes(drift.direction)) return "论文漂移";
  if (hasFormalImportantEvent(record)) return "重大事件";
  if (lifecycleOf(record) === "PRE_BUY" && record?.next_action === "run_checklist") return "买入前检查";
  if (lifecycleOf(record) === "HOLDING" && (trackingFor(record)?.alerts || []).length) return "持仓提醒";
  if (record?.next_action === "drift_recheck") return "论文漂移待复核";
  if (attentionTier(record) === "soon") return "接近触发";
  return "普通变化";
}

function attentionSummary(record) {
  const drift = record?.drift || {};
  const type = attentionReasonType(record);
  if (type === "失效条件") return "明确失效条件已触发，先复核论文。";
  if (type === "论文漂移") return `论文状态${label("drift", drift.direction)}，需要核对最新事实。`;
  if (type === "重大事件") return "正式来源事件需要核对其对论文的影响。";
  if (type === "买入前检查") return "已进入买入前阶段，买入前检查尚未完成。";
  if (type === "持仓提醒") return "持仓出现待处理提醒，优先检查当前周期。";
  if (type === "论文漂移待复核") return "已有论文复核，但证据不足，需人工补充判断。";
  if (type === "接近触发") return "价格或经营条件接近触发，列入近期复核。";
  return "有新的变化，暂不直接改变投资动作。";
}

function attentionTone(record) {
  const drift = record?.drift || {};
  if (drift.direction === "broken" || drift.direction === "weakened" || triggeredRules(record).some((rule) => rule.rule_scope === "redline")) return "danger";
  if (hasFormalImportantEvent(record) || record?.next_action === "run_drift" || lifecycleOf(record) === "PRE_BUY") return "warning";
  return "info";
}

function statusCard(lifecycle, value, hint, tone) {
  return `<button class="status-card" type="button" data-lifecycle-jump="${lifecycle}" data-tone="${tone}">
    <span class="status-card-label">${escapeHtml(label("lifecycle", lifecycle))}</span>
    <strong class="status-card-value">${escapeHtml(value)}</strong>
    <span class="status-card-hint">${escapeHtml(hint)}</span>
  </button>`;
}

function renderStatusCards() {
  const attentionCount = Number(state.board?.attention_count) || stateRecords().filter(hasAttention).length;
  els.statusCards.innerHTML = [
    statusCard("WATCH", stateCount("WATCH"), label("lifecycleHint", "WATCH"), "blue"),
    statusCard("PRE_BUY", stateCount("PRE_BUY"), label("lifecycleHint", "PRE_BUY"), "yellow"),
    statusCard("HOLDING", stateCount("HOLDING"), label("lifecycleHint", "HOLDING"), "green"),
    `<button class="status-card" type="button" data-opportunity-jump="attention" data-tone="red">
      <span class="status-card-label">全部待处理</span>
      <strong class="status-card-value">${escapeHtml(attentionCount)}</strong>
      <span class="status-card-hint">上方优先显示今日事项</span>
    </button>`,
  ].join("");
}

function renderTopMeta() {
  const generated = state.board?.generated_at || state.loadedAt;
  els.lastUpdated.textContent = formatDateTime(generated);
  const total = stateRecords().length;
  const ruleCount = [...state.rulePackages.values()].reduce((sum, pack) => sum + (Array.isArray(pack?.rules) ? pack.rules.length : 0), 0);
  els.datasetSummary.textContent = `${total} 家公司 · ${ruleCount} 条规则`;
  const quoteCount = state.quotes.size;
  const quoteTime = state.quoteMeta?.generated_at || state.quoteMeta?.market_status?.generated_at;
  const isPartial = quoteCount < total;
  els.quoteStatus.dataset.tone = isPartial ? "stale" : "fresh";
  els.quoteStatusText.textContent = `行情${isPartial ? "部分可用" : "已更新"} · ${quoteCount}/${total}${quoteTime ? ` · ${formatDateTime(quoteTime)}` : ""}`;
}

function cardCompany(record) {
  const quote = quoteFor(record);
  return `<div class="card-company"><span class="company-name">${escapeHtml(text(record.company))}</span><span class="company-code">${escapeHtml(record.market || "待识别")} · ${escapeHtml(record.ticker)}</span><span class="price-value">${escapeHtml(formatPrice(quote))}</span></div>`;
}

function compactCompany(record) {
  return `<div class="card-company"><span class="company-name">${escapeHtml(text(record.company))}</span><span class="company-code">${escapeHtml(record.market || "待识别")} · ${escapeHtml(record.ticker)}</span></div>`;
}

function renderAttentionCard(record) {
  return `<article class="attention-card" data-ticker="${escapeHtml(record.ticker)}" data-tone="${attentionTone(record)}" tabindex="0" role="button">
    <div class="card-topline">${compactCompany(record)}<span class="lifecycle-badge" data-lifecycle="${escapeHtml(lifecycleOf(record))}">${escapeHtml(label("lifecycle", lifecycleOf(record)))}</span></div>
    <div class="attention-kind">${escapeHtml(attentionReasonType(record))}</div>
    <p class="attention-reason"><strong>${escapeHtml(attentionSummary(record))}</strong></p>
    <div class="attention-action" data-tone="${escapeHtml(actionTone(record.next_action))}">${escapeHtml(actionLabel(record))}<span aria-hidden="true">→</span></div>
  </article>`;
}

function attentionRecords() {
  return stateRecords().filter(hasAttention).sort((a, b) => {
    const tierScore = { must: 3, soon: 2, changes: 1 };
    const score = (record) => (record.lifecycle === "HOLDING" ? 30 : 0) + (hasFormalImportantEvent(record) ? 20 : 0) + triggeredRules(record).length * 5 + (record.drift?.direction === "broken" ? 40 : 0);
    return tierScore[attentionTier(b)] - tierScore[attentionTier(a)] || score(b) - score(a) || String(a.company).localeCompare(String(b.company), "zh-CN");
  });
}

function renderAttention() {
  const records = attentionRecords();
  const count = Number(state.board?.attention_count) || records.length;
  const tierCounts = records.reduce((result, record) => {
    const tier = attentionTier(record);
    result[tier] += 1;
    return result;
  }, { must: 0, soon: 0, changes: 0 });
  els.attentionCount.textContent = `${count} 项 · 今日 ${tierCounts.must}`;
  const visible = state.attentionExpanded ? records : records.slice(0, 8);
  const grouped = ["must", "soon", "changes"].map((tier) => ({ tier, records: visible.filter((record) => attentionTier(record) === tier) })).filter((group) => group.records.length);
  els.attentionList.innerHTML = grouped.length
    ? grouped.map(({ tier, records: tierRecords }) => `<div class="attention-layer"><div class="attention-layer-heading"><span>${escapeHtml(attentionTierLabel(tier))}</span><span>${tierRecords.length}${state.attentionExpanded ? " 项" : " 项已显示"}</span></div><div class="attention-layer-grid">${tierRecords.map(renderAttentionCard).join("")}</div></div>`).join("")
    : `<div class="loading-card">今天没有待处理事项。</div>`;
  els.attentionViewAll.hidden = records.length <= 8;
  els.attentionViewAll.textContent = state.attentionExpanded ? "收起" : `查看全部（${count}）`;
}

function opportunityStatus(item) {
  return item?.status || "unknown";
}

function opportunityPriority(item) {
  return { triggered: 3, near_trigger: 2, unknown: 1, not_triggered: 0 }[opportunityStatus(item)] || 0;
}

function opportunityRecords(kind) {
  const items = [];
  for (const record of stateRecords()) {
    if (["HOLDING", "EXITED"].includes(lifecycleOf(record))) continue;
    const opportunities = kind === "price" ? priceOpportunities(record) : conditionOpportunities(record);
    for (const opportunity of opportunities) {
      const rule = rulesFor(record).find((candidate) => candidate.rule_id === opportunity.rule_id);
      // A redline can be triggered, but it is a review/drop signal rather than a buy candidate.
      if (rule?.rule_scope === "redline") continue;
      items.push({ record, opportunity });
    }
  }
  items.sort((a, b) => opportunityPriority(b.opportunity) - opportunityPriority(a.opportunity) || (hasAttention(b.record) ? 1 : 0) - (hasAttention(a.record) ? 1 : 0) || String(a.record.company).localeCompare(String(b.record.company), "zh-CN"));
  const unique = [];
  const seen = new Set();
  for (const item of items) {
    if (seen.has(item.record.ticker)) continue;
    seen.add(item.record.ticker);
    unique.push(item);
  }
  return unique;
}

function opportunityTarget(opportunity, record) {
  if (opportunity.type === "PRICE_RANGE" || opportunity.min != null || opportunity.max != null) return opportunity.condition || "报告价格区间";
  return opportunity.condition || record?.conclusion_summary || "等待正文条件确认";
}

function renderOpportunityCard(item, kind) {
  const { record, opportunity } = item;
  const status = opportunityStatus(opportunity);
  return `<article class="opportunity-card" data-ticker="${escapeHtml(record.ticker)}" tabindex="0" role="button">
    <div class="opportunity-topline">${cardCompany(record)}<span class="mini-badge opportunity-status" data-status="${escapeHtml(status)}">${escapeHtml(label("ruleStatus", status))}</span></div>
    <div class="opportunity-context"><span class="opportunity-label">${kind === "price" ? "目标区间" : "等待确认"}</span><span class="opportunity-condition">${escapeHtml(opportunityTarget(opportunity, record))}</span></div>
    <div class="opportunity-action" data-tone="${escapeHtml(actionTone(record.next_action))}">${escapeHtml(actionLabel(record))}<span aria-hidden="true">→</span></div>
  </article>`;
}

function renderOpportunities() {
  const prices = opportunityRecords("price");
  const conditions = opportunityRecords("condition");
  els.priceCount.textContent = String(prices.length);
  els.conditionCount.textContent = String(conditions.length);
  els.checklistCount.textContent = String(stateCount("PRE_BUY"));
  const current = state.opportunityView === "price" ? prices : conditions;
  const visible = state.opportunityExpanded ? current : current.slice(0, 8);
  els.opportunityList.innerHTML = current.length ? visible.map((item) => renderOpportunityCard(item, state.opportunityView)).join("") : `<div class="loading-card">暂时没有可展示的机会。</div>`;
  els.opportunityViewAll.hidden = current.length <= 8;
  els.opportunityViewAll.textContent = state.opportunityExpanded ? "收起机会池" : `查看全部机会（${current.length}）`;
  document.querySelectorAll("[data-opportunity-view]").forEach((button) => {
    const active = button.dataset.opportunityView === state.opportunityView;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
}

function aiScanState(value) {
  return {
    "机会": "当前机会",
    "条件机会": "临近机会",
    "暂不构成机会": "暂不构成当前机会",
  }[value] || value || "待复核";
}

function aiScanAssessments(scan) {
  const assessments = [];
  if (scan?.assessment && !["stale", "error"].includes(scan.status) && typeof scan.assessment === "object") {
    assessments.push({ model: scan.model, assessment: scan.assessment });
  }
  for (const [model, result] of Object.entries(scan?.models || {})) {
    if (result?.status !== "ready" || !result.assessment || typeof result.assessment !== "object") continue;
    assessments.push({ model, assessment: result.assessment });
  }
  return assessments;
}

function aiScanClassification(scan) {
  const states = aiScanAssessments(scan).map(({ assessment }) => aiScanState(assessment.opportunity_state));
  if (states.includes("当前机会")) return "当前机会";
  if (states.includes("临近机会")) return "临近机会";
  return "待复核";
}

function aiScanText(scan, field) {
  const assessmentText = aiScanAssessments(scan)
    .map(({ assessment }) => assessment?.[field])
    .find((value) => typeof value === "string" && value.trim());
  if (assessmentText) return assessmentText.trim();
  const unionText = scan?.union?.[field];
  if (typeof unionText === "string" && unionText.trim()) return unionText.trim();
  const directText = scan?.[field];
  return typeof directText === "string" && directText.trim() ? directText.trim() : "";
}

function aiScanStatusText(status) {
  return {
    ok: "已完成",
    ready: "已完成",
    partial: "部分可用",
    stale: "结果过期",
    error: "读取失败",
    missing: "暂无扫描",
    unavailable: "不可用",
  }[status] || "待复核";
}

function aiOpportunityItems() {
  const items = [];
  for (const scan of state.opportunityScans.values()) {
    const record = currentRecord(scan?.ticker);
    const classification = aiScanClassification(scan);
    if (!record || !["当前机会", "临近机会"].includes(classification)) continue;
    items.push({ record, scan, classification });
  }
  items.sort((a, b) => (
    (a.classification === "当前机会" ? 0 : 1) - (b.classification === "当前机会" ? 0 : 1)
      || String(a.record.company).localeCompare(String(b.record.company), "zh-CN")
  ));
  return items;
}

function renderAiOpportunityCard(item) {
  const { record, scan, classification } = item;
  const whyNow = aiScanText(scan, "why_now");
  const summary = aiScanText(scan, "opportunity_summary");
  const generatedAt = scan.generated_at || state.opportunityScanMeta.generated_at;
  return `<article class="ai-opportunity-card" data-ticker="${escapeHtml(record.ticker)}" tabindex="0" role="button">
    <div class="ai-opportunity-topline">${compactCompany(record)}<span class="lifecycle-badge" data-lifecycle="${escapeHtml(lifecycleOf(record))}">${escapeHtml(label("lifecycle", lifecycleOf(record)))}</span></div>
    <div class="ai-opportunity-facts"><span class="ai-opportunity-classification">${escapeHtml(classification)}</span><span>扫描 ${escapeHtml(formatDateTime(generatedAt))}</span></div>
    ${whyNow ? `<p class="ai-opportunity-why"><span>为什么现在</span>${escapeHtml(whyNow)}</p>` : ""}
    <p class="ai-opportunity-summary">${escapeHtml(summary || "摘要未提供")}</p>
    <div class="ai-opportunity-action">查看公司详情<span aria-hidden="true">→</span></div>
  </article>`;
}

function renderAiOpportunities() {
  const items = aiOpportunityItems();
  const meta = state.opportunityScanMeta || {};
  const status = meta.status || "missing";
  const coverage = Number.isFinite(Number(meta.scan_count)) && Number.isFinite(Number(meta.expected_scan_count))
    ? ` · ${meta.scan_count}/${meta.expected_scan_count}`
    : "";
  els.aiOpportunityMeta.textContent = `${aiScanStatusText(status)}${coverage}${meta.generated_at ? ` · ${formatDateTime(meta.generated_at)}` : ""}`;
  if (items.length) {
    const visible = state.aiOpportunityExpanded ? items : items.slice(0, 6);
    els.aiOpportunityList.innerHTML = visible.map(renderAiOpportunityCard).join("");
    els.aiOpportunityViewAll.hidden = items.length <= 6;
    els.aiOpportunityViewAll.textContent = state.aiOpportunityExpanded ? "收起" : `查看全部 AI 研究机会（${items.length}）`;
    return;
  }
  els.aiOpportunityViewAll.hidden = true;
  const message = status === "missing"
    ? "本地暂无 AI 每日研究机会扫描结果。结果生成后会显示在这里，不影响其他看板模块。"
    : ["error", "unavailable"].includes(status)
      ? "AI 每日研究机会暂时不可用；未生成研究机会，也未改变买入候选。"
      : status === "stale"
        ? "最近一次 AI 研究机会结果已过期；未将过期结果当作当前机会。"
        : "本次扫描没有筛出当前或临近研究机会。";
  els.aiOpportunityList.innerHTML = `<div class="ai-opportunity-empty">${escapeHtml(message)}</div>`;
}

function renderAiOpportunitySection(record) {
  const scan = state.opportunityScans.get(record?.ticker);
  if (!scan) return "";
  const classification = aiScanClassification(scan);
  const whyNow = aiScanText(scan, "why_now");
  const summary = aiScanText(scan, "opportunity_summary");
  const satisfied = aiScanAssessments(scan).flatMap(({ assessment }) => Array.isArray(assessment.satisfied_conditions) ? assessment.satisfied_conditions : []).filter(Boolean);
  const unmet = aiScanAssessments(scan).flatMap(({ assessment }) => Array.isArray(assessment.unmet_conditions) ? assessment.unmet_conditions : []).filter(Boolean);
  return `<div class="detail-section ai-opportunity-detail"><div class="detail-section-head"><h3>AI 每日研究机会</h3><span class="data-badge" data-status="${escapeHtml(scan.status || "unknown")}">${escapeHtml(classification)}</span></div><p class="detail-copy">这是独立的研究发现，不改变当前生命周期、决策规则或买入候选。</p>${whyNow ? `<div class="detail-field"><div class="detail-field-label">为什么现在</div><div class="detail-field-value">${escapeHtml(whyNow)}</div></div>` : ""}${summary ? `<div class="detail-field" style="margin-top:12px"><div class="detail-field-label">机会摘要</div><div class="detail-field-value">${escapeHtml(summary)}</div></div>` : ""}${satisfied.length ? `<div class="detail-field" style="margin-top:12px"><div class="detail-field-label">已满足条件</div><div class="detail-field-value">${escapeHtml(satisfied.join("；"))}</div></div>` : ""}${unmet.length ? `<div class="detail-field" style="margin-top:12px"><div class="detail-field-label">仍待确认</div><div class="detail-field-value">${escapeHtml(unmet.join("；"))}</div></div>` : ""}</div>`;
}

function holdingReturn(record, tracking) {
  const quote = quoteFor(record);
  if (!quote || !Number.isFinite(Number(tracking?.cost_basis)) || !Number.isFinite(Number(quote.price))) return null;
  return Number(quote.price) / Number(tracking.cost_basis) - 1;
}

function redlineRules(record) {
  return rulesFor(record).filter((rule) => rule.rule_scope === "redline").slice(0, 3);
}

function renderHoldingCard(record) {
  const tracking = trackingFor(record) || {};
  const quote = quoteFor(record);
  const result = holdingReturn(record, tracking);
  const drift = record.drift || {};
  const redlines = redlineRules(record);
  return `<article class="holding-card" data-ticker="${escapeHtml(record.ticker)}" tabindex="0" role="button">
    <div class="holding-topline">${cardCompany(record)}<span class="lifecycle-badge" data-lifecycle="HOLDING">持有中</span></div>
    <div class="holding-metrics">
      <div><span class="metric-label">成本</span><strong class="metric-value">${escapeHtml(formatPrice({price: tracking.cost_basis, currency: quote?.currency}, "—"))}</strong></div>
      <div><span class="metric-label">收益率</span><strong class="metric-value holding-pnl ${result == null ? "" : result >= 0 ? "positive" : "negative"}">${result == null ? "—" : escapeHtml(`${result >= 0 ? "+" : ""}${(result * 100).toFixed(2)}%`)}</strong></div>
      <div><span class="metric-label">仓位</span><strong class="metric-value">${escapeHtml(tracking.position_weight == null ? "—" : `${formatNumber(tracking.position_weight, 1)}%`)}</strong></div>
      <div><span class="metric-label">当前价格</span><strong class="metric-value">${escapeHtml(formatPrice(quote))}</strong></div>
    </div>
    <div class="holding-bottom">
      <div><div class="holding-detail-label">买入日期</div><div class="holding-detail-value">${escapeHtml(formatDate(tracking.buy_date))}</div><div class="holding-detail-label" style="margin-top:9px">原始买入论文</div><div class="holding-detail-value"><a class="text-link" href="${escapeHtml(reportHref(tracking.thesis_report_path || record.canonical_report))}" target="_blank" rel="noreferrer" data-stop-card>查看原始买入论文</a></div></div>
      <div><div class="holding-detail-label">论文状态 / 最近漂移</div><div class="holding-detail-value">${escapeHtml(thesisLabel(tracking.thesis_status))} · ${escapeHtml(label("drift", drift.direction))}</div><div class="holding-detail-label" style="margin-top:9px">关键失效条件</div><ul class="redline-list">${redlines.length ? redlines.map((rule) => `<li>${escapeHtml(rule.condition)}</li>`).join("") : "<li>报告未提取明确失效条件</li>"}</ul></div>
    </div>
    <div class="holding-links"><a class="text-link" href="${escapeHtml(reportHref(record.canonical_report))}" target="_blank" rel="noreferrer" data-stop-card>打开主报告</a><span class="table-next" data-tone="${escapeHtml(actionTone(record.next_action))}">${escapeHtml(actionLabel(record))}</span></div>
  </article>`;
}

function thesisLabel(value) {
  return { healthy: "健康", borderline: "边际弱化", damaged: "受损", broken: "失效", not_established: "未建立" }[value] || "待复核";
}

function renderHoldings() {
  const holdings = stateRecords().filter((record) => lifecycleOf(record) === "HOLDING");
  els.holdingCount.textContent = `${holdings.length} 家`;
  els.holdingList.innerHTML = holdings.length ? holdings.map(renderHoldingCard).join("") : `<div class="loading-card">暂无真实持仓记录。</div>`;
}

function keyCondition(record) {
  const prices = priceOpportunities(record).filter((item) => item.status !== "not_triggered");
  if (prices[0]) return prices[0].condition || "价格条件已提取";
  const conditions = conditionOpportunities(record);
  if (conditions[0]) return conditions[0].condition || "经营条件待确认";
  return record?.warning || "报告未提取明确条件，需人工判断";
}

function compactDataSummary(record) {
  const drift = driftScanLabel(record);
  const event = label("eventState", record?.event_radar?.state);
  const technical = dataLabel(record?.technical?.freshness || record?.technical?.status);
  const sentiment = sentimentLabel(record).stateText;
  return `<div class="compact-statuses"><span>论文：${escapeHtml(drift)}</span><span>事件：${escapeHtml(event)}</span><span>技术：${escapeHtml(technical)}</span><span>情绪：${escapeHtml(sentiment)}</span></div>`;
}

function renderWatchRow(record) {
  const quote = quoteFor(record);
  const lifecycle = lifecycleOf(record);
  const action = record.next_action;
  return `<tr data-ticker="${escapeHtml(record.ticker)}" tabindex="0">
    <td>${compactCompany(record)}</td>
    <td><span class="table-price">${escapeHtml(formatPrice(quote))}</span>${quote?.change_pct != null ? `<div class="table-secondary ${quote.change_pct >= 0 ? "price-change-up" : "price-change-down"}">${quote.change_pct >= 0 ? "+" : ""}${escapeHtml(formatNumber(quote.change_pct, 2))}%</div>` : ""}</td>
    <td><span class="lifecycle-badge" data-lifecycle="${escapeHtml(lifecycle)}">${escapeHtml(label("lifecycle", lifecycle))}</span><div class="table-secondary">${escapeHtml(record.opportunity_type === "both" ? "价格 + 条件" : record.opportunity_type === "price" ? "价格机会" : record.opportunity_type === "condition" ? "条件机会" : "普通观察")}</div></td>
    <td><div class="table-condition">${escapeHtml(keyCondition(record))}</div></td>
    <td>${compactDataSummary(record)}</td>
    <td><span class="table-next" data-tone="${escapeHtml(actionTone(action))}">${escapeHtml(actionLabel(record))}</span></td>
  </tr>`;
}

function filteredRecords() {
  const search = state.search.toLowerCase();
  const defaultResearchPool = state.lifecycle === "all" && !state.search.trim() && state.opportunity === "all";
  let records = stateRecords().filter((record) => {
    if (defaultResearchPool && lifecycleOf(record) === "HOLDING") return false;
    const matchesSearch = !search || `${record.company} ${record.ticker}`.toLowerCase().includes(search);
    const matchesMarket = state.market === "all" || record.market === state.market;
    const matchesLifecycle = state.lifecycle === "all" || lifecycleOf(record) === state.lifecycle;
    const matchesOpportunity = state.opportunity === "all"
      || (state.opportunity === "price" && priceOpportunities(record).length)
      || (state.opportunity === "condition" && conditionOpportunities(record).length)
      || (state.opportunity === "attention" && hasAttention(record));
    return matchesSearch && matchesMarket && matchesLifecycle && matchesOpportunity;
  });
  records.sort((a, b) => {
    if (state.sort === "name") return String(a.company).localeCompare(String(b.company), "zh-CN");
    if (state.sort === "lifecycle") return String(label("lifecycle", lifecycleOf(a))).localeCompare(String(label("lifecycle", lifecycleOf(b))), "zh-CN");
    if (state.sort === "price") return (priceOpportunities(b).length - priceOpportunities(a).length) || String(a.company).localeCompare(String(b.company), "zh-CN");
    return (hasAttention(b) ? 1 : 0) - (hasAttention(a) ? 1 : 0) || (lifecycleOf(a) === "HOLDING" ? -1 : 0) - (lifecycleOf(b) === "HOLDING" ? -1 : 0) || String(a.company).localeCompare(String(b.company), "zh-CN");
  });
  return records;
}

function renderWatchlist() {
  const records = filteredRecords();
  const pageRecords = records.slice(0, state.page * PAGE_SIZE);
  els.watchlist.innerHTML = pageRecords.map(renderWatchRow).join("");
  els.watchlistCount.textContent = `${stateRecords().filter((record) => lifecycleOf(record) !== "HOLDING").length} 家`;
  els.watchlistMeta.textContent = `显示 ${pageRecords.length} / ${records.length} 家 · 全部数据已加载到本地，详情按需打开`;
  els.loadMore.hidden = pageRecords.length >= records.length;
  els.loadMore.textContent = `加载更多（剩余 ${Math.max(0, records.length - pageRecords.length)} 家）`;
  els.emptyState.hidden = records.length > 0;
}

function currentRecord(ticker) {
  return state.companyState.get(ticker) || null;
}

function ruleGroupTitle(scope) {
  return LABELS.scope[scope] || "其他条件";
}

function renderRules(record) {
  const rules = rulesFor(record);
  const groups = ["entry", "validation", "redline", "unknown"];
  if (!rules.length) return `<p class="detail-copy">这家公司当前没有已保存的决策规则；请以主报告为准并保留人工判断。</p>`;
  return groups.filter((scope) => rules.some((rule) => (rule.rule_scope || "unknown") === scope)).map((scope) => {
    const scoped = rules.filter((rule) => (rule.rule_scope || "unknown") === scope);
    return `<div class="rule-group"><div class="rule-group-title">${escapeHtml(ruleGroupTitle(scope))}<span>${scoped.length} 条</span></div><ul class="rule-list">${scoped.map((rule) => `<li class="rule-item"><div class="rule-item-top"><span class="rule-type">${escapeHtml(LABELS.ruleType[rule.type] || "条件规则")}</span><span class="mini-badge rule-status" data-status="${escapeHtml(rule.status || "unknown")}">${escapeHtml(label("ruleStatus", rule.status))}</span></div><div class="rule-condition">${escapeHtml(rule.condition)}</div><div class="rule-action">触发后：${escapeHtml(ruleActionLabel(rule))}</div><div class="rule-source">来源：${escapeHtml(rule.source_section || rule.source || "已保存决策规则")}</div></li>`).join("")}</ul></div>`;
  }).join("");
}

function eventTierLabel(tier) {
  if (["A", "B"].includes(tier)) return "正式来源";
  if (["C", "D"].includes(tier)) return "市场讨论 / 背景";
  return "来源待判断";
}

function renderEventSection(record) {
  const radar = record.event_radar || {};
  const events = Array.isArray(radar.events) ? radar.events : [];
  const formal = events.filter((event) => event.thesis_relevant || ["A", "B"].includes(event.highest_source_tier)).slice(0, 3);
  const discussion = events.filter((event) => !event.thesis_relevant && ["C", "D"].includes(event.highest_source_tier)).slice(0, 3);
  const renderEvent = (event) => `<li class="event-item"><div class="event-item-top"><span class="event-headline">${escapeHtml(text(event.headline, "未命名事件"))}</span><span class="mini-badge">${escapeHtml(eventTierLabel(event.highest_source_tier))}</span></div><div class="event-meta">${escapeHtml(text(event.summary, "暂无摘要"))} · ${escapeHtml(event.recommended_action === "run_drift" ? "建议检查论文" : "仅作辅助观察")}</div></li>`;
  return `<div class="detail-section"><div class="detail-section-head"><h3>事件雷达</h3><span class="data-badge" data-status="${escapeHtml(radar.source_status || "unknown")}">${escapeHtml(label("eventState", radar.state))}</span></div><div class="detail-grid"><div class="detail-field"><div class="detail-field-label">论文相关性</div><div class="detail-field-value">${escapeHtml(radar.thesis_relevant ? "已标记为论文相关" : "未标记为论文相关")}</div></div><div class="detail-field"><div class="detail-field-label">数据状态</div><div class="detail-field-value">${escapeHtml(dataLabel(radar.source_status))} · 截止 ${escapeHtml(formatDate(radar.data_cutoff))}</div></div></div>${formal.length ? `<div class="event-block"><div class="holding-detail-label" style="margin:15px 0 7px">重要事件</div><ul class="event-list">${formal.map(renderEvent).join("")}</ul></div>` : ""}${discussion.length ? `<div class="event-block"><div class="holding-detail-label" style="margin:15px 0 7px">市场讨论 / 背景</div><ul class="event-list">${discussion.map(renderEvent).join("")}</ul></div>` : ""}${!formal.length && !discussion.length ? `<p class="detail-copy" style="margin-top:12px">暂无可展示事件；来源不可用时只显示未知，不推断为正常。</p>` : ""}</div>`;
}

function renderTechnicalSection(record) {
  const technical = record.technical || state.technical.get(record.ticker) || {};
  const market = record.market;
  const intradayNote = market === "港股" ? "盘中技术辅助：暂不支持" : technical.intraday_eligible ? "盘中技术辅助：可用" : "盘中技术辅助：未启用";
  return `<div class="detail-section"><div class="detail-section-head"><h3>技术辅助</h3><span class="data-badge" data-status="${escapeHtml(technical.freshness || technical.status || "unknown")}">${escapeHtml(dataLabel(technical.freshness || technical.status))}</span></div><p class="detail-copy">技术面仅用于执行节奏，不改变基本面投资资格。</p><div class="detail-grid" style="margin-top:14px"><div class="detail-field"><div class="detail-field-label">趋势</div><div class="detail-field-value">${escapeHtml(label("technical", technical.trend))}</div></div><div class="detail-field"><div class="detail-field-label">位置</div><div class="detail-field-value">${escapeHtml(label("technical", technical.position))}</div></div><div class="detail-field"><div class="detail-field-label">执行环境</div><div class="detail-field-value">${escapeHtml(label("technical", technical.execution))}</div></div><div class="detail-field"><div class="detail-field-label">技术数据日</div><div class="detail-field-value">${escapeHtml(formatDate(technical.data_cutoff))}</div></div></div><div class="unsupported-note" style="margin-top:14px">${escapeHtml(intradayNote)}</div></div>`;
}

function sentimentLabel(record) {
  const sentiment = record.sentiment || state.sentiment.get(record.ticker) || {};
  const combined = sentiment.combined_sentiment || sentiment;
  const status = combined.status || sentiment.status || "unknown";
  const score = combined.score_0_100 ?? sentiment.score_0_100;
  const confidence = combined.confidence || sentiment.confidence || "待复核";
  const stateValue = combined.state || sentiment.state || "unknown";
  const stateText = LABELS.sentiment[stateValue] || stateValue || "未知";
  const note = state.sentimentMeta?.llm_status === "needs_review" ? "辅助判断，正式模型评分待复核" : dataLabel(status);
  return { stateText, score, confidence, note };
}

function renderSentimentSection(record) {
  const sentiment = sentimentLabel(record);
  return `<div class="detail-section"><div class="detail-section-head"><h3>市场情绪</h3><span class="data-badge" data-status="${escapeHtml((record.sentiment || {}).status || "partial")}">${escapeHtml(sentiment.stateText)}</span></div><div class="detail-grid"><div class="detail-field"><div class="detail-field-label">综合倾向</div><div class="detail-field-value large">${escapeHtml(sentiment.stateText)}</div></div><div class="detail-field"><div class="detail-field-label">辅助分数</div><div class="detail-field-value large">${sentiment.score == null ? "—" : escapeHtml(formatNumber(sentiment.score, 1))}</div></div><div class="detail-field"><div class="detail-field-label">数据可信度</div><div class="detail-field-value">${escapeHtml(sentiment.confidence)}</div></div><div class="detail-field"><div class="detail-field-label">数据说明</div><div class="detail-field-value">${escapeHtml(sentiment.note)}</div></div></div></div>`;
}

function renderThesisSection(record) {
  const tracking = trackingFor(record);
  const drift = record.drift || {};
  if (lifecycleOf(record) === "HOLDING" && tracking) {
    return `<div class="detail-section"><div class="detail-section-head"><h3>原始买入论文</h3><span class="mini-badge">当前持仓周期</span></div><div class="thesis-banner">原始买入论文已绑定当前持仓周期，不会因后续报告改写而被替换。</div><div class="detail-grid"><div class="detail-field"><div class="detail-field-label">论文状态</div><div class="detail-field-value">${escapeHtml(thesisLabel(tracking.thesis_status))} · ${escapeHtml(label("drift", drift.direction))}</div></div><div class="detail-field"><div class="detail-field-label">健康度</div><div class="detail-field-value">${tracking.health_score == null ? "—" : escapeHtml(`${tracking.health_score}/10`)}</div></div><div class="detail-field"><div class="detail-field-label">买入日期</div><div class="detail-field-value">${escapeHtml(formatDate(tracking.buy_date))}</div></div><div class="detail-field"><div class="detail-field-label">下一次复核</div><div class="detail-field-value">${escapeHtml(formatDate(tracking.next_review_date))}</div></div></div><div class="source-line">当前持仓周期已绑定原始买入论文<br />最近漂移检查：${escapeHtml(formatDateTime(drift.last_checked))}</div><a class="drawer-report-link" href="${escapeHtml(reportHref(tracking.thesis_report_path || record.canonical_report))}" target="_blank" rel="noreferrer">查看原始买入论文 ↗</a></div>`;
  }
  return `<div class="detail-section"><div class="detail-section-head"><h3>当前研究论文</h3><span class="mini-badge">${escapeHtml(driftScanLabel(record))}</span></div><p class="detail-copy">当前为${escapeHtml(label("lifecycle", lifecycleOf(record)))}；后续事实变化通过论文漂移检查复核。</p><div class="source-line">Canonical 主报告已关联<br />最近复核：${escapeHtml(formatDateTime(drift.last_checked))}</div><a class="drawer-report-link" href="${escapeHtml(reportHref(record.canonical_report))}" target="_blank" rel="noreferrer">打开主报告 ↗</a></div>`;
}

function renderCurrentJudgment(record) {
  const quote = quoteFor(record);
  const sentiment = sentimentLabel(record);
  const radar = record.event_radar || {};
  return `<div class="detail-section"><div class="detail-section-head"><h3>当前判断</h3><span class="lifecycle-badge" data-lifecycle="${escapeHtml(lifecycleOf(record))}">${escapeHtml(label("lifecycle", lifecycleOf(record)))}</span></div><div class="detail-grid"><div class="detail-field"><div class="detail-field-label">当前价格</div><div class="detail-field-value large">${escapeHtml(formatPrice(quote))}</div></div><div class="detail-field"><div class="detail-field-label">下一步</div><div class="detail-field-value large">${escapeHtml(actionLabel(record))}</div></div><div class="detail-field"><div class="detail-field-label">研究判断</div><div class="detail-field-value">${escapeHtml(text(record.action, "观察"))}</div></div><div class="detail-field"><div class="detail-field-label">情绪辅助</div><div class="detail-field-value">${escapeHtml(sentiment.stateText)}${sentiment.score == null ? "" : ` · ${formatNumber(sentiment.score, 1)}`}</div></div><div class="detail-field"><div class="detail-field-label">最近事件</div><div class="detail-field-value">${escapeHtml(label("eventState", radar.state))}${radar.thesis_relevant ? " · 论文相关" : ""}</div></div><div class="detail-field"><div class="detail-field-label">数据范围</div><div class="detail-field-value">${escapeHtml(record.realtime_scope === "research_only" ? "仅研究" : "A/H 实时支持")}</div></div></div>${record.conclusion_summary ? `<p class="source-line">${escapeHtml(record.conclusion_summary)}</p>` : ""}</div>`;
}

function renderDetail(record) {
  const ruleCount = rulesFor(record).length;
  els.drawerKicker.textContent = `${record.market || "待识别"} · ${record.ticker}`;
  els.drawerTitle.textContent = text(record.company);
  els.drawerSubtitle.textContent = `${label("lifecycle", lifecycleOf(record))} · ${actionLabel(record)} · ${ruleCount} 条已保存规则`;
  els.drawerContent.innerHTML = [
    renderCurrentJudgment(record),
    renderAiOpportunitySection(record),
    `<div class="detail-section"><div class="detail-section-head"><h3>决策规则</h3><span class="section-count">${ruleCount} 条</span></div>${renderRules(record)}</div>`,
    renderThesisSection(record),
    renderEventSection(record),
    renderTechnicalSection(record),
    renderSentimentSection(record),
  ].join("");
}

function openDetail(ticker) {
  const record = currentRecord(ticker);
  if (!record) return;
  state.selectedTicker = ticker;
  renderDetail(record);
  els.backdrop.hidden = false;
  els.drawer.hidden = false;
  document.body.classList.add("drawer-open");
  history.replaceState(null, "", `#${state.workspace}/company=${encodeURIComponent(ticker)}`);
}

function closeDetail({ restoreRoute = true } = {}) {
  hideDetailDrawer();
  if (restoreRoute && location.hash.includes("/company=")) history.replaceState(null, "", `#${state.workspace}`);
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => { els.toast.hidden = true; }, 2600);
}

async function loadJson(path) {
  const response = await fetch(`${path}?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} (${response.status})`);
  return response.json();
}

async function loadOptionalJson(path, fallback) {
  try {
    return await loadJson(path);
  } catch {
    return fallback();
  }
}

function indexByTicker(items) {
  return new Map((Array.isArray(items) ? items : []).filter((item) => item?.ticker).map((item) => [item.ticker, item]));
}

function normalizeTracking(payload) {
  const positions = payload?.positions;
  if (Array.isArray(positions)) return indexByTicker(positions);
  return new Map(Object.entries(positions || {}).filter(([, item]) => item?.ticker).map(([ticker, item]) => [ticker, item]));
}

async function loadData({ silent = false } = {}) {
  if (!silent) {
    els.attentionList.innerHTML = `<div class="loading-card">正在读取看板数据…</div>`;
    els.holdingList.innerHTML = `<div class="loading-card">正在读取持仓数据…</div>`;
  }
  const entries = await Promise.all(Object.entries(DATA_FILES).map(async ([name, path]) => [
    name,
    OPTIONAL_DATA_FALLBACKS[name]
      ? await loadOptionalJson(path, () => ({ ...OPTIONAL_DATA_FALLBACKS[name] }))
      : await loadJson(path),
  ]));
  const payload = Object.fromEntries(entries);
  if (!payload.companyState || !Array.isArray(payload.companyState.companies)) throw new Error("公司状态数据不可用");
  state.board = payload.board;
  state.companyState = indexByTicker(payload.companyState.companies);
  state.rulePackages = indexByTicker(payload.rules?.companies);
  state.events = indexByTicker(payload.events?.companies);
  state.technical = indexByTicker(payload.technical?.companies);
  state.sentiment = indexByTicker(payload.sentiment?.companies);
  state.tracking = normalizeTracking(payload.tracking);
  state.quotes = indexByTicker(payload.quotes?.quotes);
  state.quoteMeta = payload.quotes;
  state.sentimentMeta = payload.sentiment;
  state.opportunityScanMeta = payload.opportunityScans && Array.isArray(payload.opportunityScans.scans)
    ? payload.opportunityScans
    : { schema_version: 1, status: "unavailable", scans: [] };
  state.opportunityScans = indexByTicker(state.opportunityScanMeta.scans);
  state.loadedAt = new Date().toISOString();
  renderAll();
  syncWorkspaceFromLocation();
}

function renderAll() {
  renderTopMeta();
  renderStatusCards();
  renderAttention();
  renderOpportunities();
  renderAiOpportunities();
  renderHoldings();
  renderWatchlist();
  renderWorkspaceNav();
}

function applyFilterFromJump({ lifecycle = "all", opportunity = "all" } = {}) {
  state.lifecycle = lifecycle;
  state.opportunity = opportunity;
  state.page = 1;
  els.lifecycle.value = lifecycle;
  els.opportunity.value = opportunity;
  const targetWorkspace = lifecycle !== "all" ? "watchlist" : opportunity === "attention" ? "attention" : "watchlist";
  setWorkspace(targetWorkspace);
  if (targetWorkspace === "watchlist") {
    renderWatchlist();
    document.querySelector("#watchlist-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function bindEvents() {
  els.workspaceNav?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-workspace]");
    if (button) setWorkspace(button.dataset.workspace);
  });
  window.addEventListener("hashchange", syncWorkspaceFromLocation);
  window.addEventListener("popstate", syncWorkspaceFromLocation);
  els.statusCards.addEventListener("click", (event) => {
    const lifecycleButton = event.target.closest("[data-lifecycle-jump]");
    const opportunityButton = event.target.closest("[data-opportunity-jump]");
    if (lifecycleButton) applyFilterFromJump({ lifecycle: lifecycleButton.dataset.lifecycleJump });
    if (opportunityButton) applyFilterFromJump({ opportunity: opportunityButton.dataset.opportunityJump });
  });
  document.querySelector("#opportunity-tabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-opportunity-view]");
    if (!button) return;
    state.opportunityView = button.dataset.opportunityView;
    state.opportunityExpanded = false;
    renderOpportunities();
  });
  els.attentionViewAll.addEventListener("click", () => {
    state.attentionExpanded = !state.attentionExpanded;
    renderAttention();
  });
  els.opportunityViewAll.addEventListener("click", () => {
    state.opportunityExpanded = !state.opportunityExpanded;
    renderOpportunities();
  });
  els.aiOpportunityViewAll.addEventListener("click", () => {
    state.aiOpportunityExpanded = !state.aiOpportunityExpanded;
    renderAiOpportunities();
  });
  for (const container of [els.attentionList, els.opportunityList, els.aiOpportunityList, els.holdingList]) {
    container.addEventListener("click", (event) => {
      if (event.target.closest("a[data-stop-card]")) return;
      const card = event.target.closest("[data-ticker]");
      if (card) openDetail(card.dataset.ticker);
    });
    container.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const card = event.target.closest("[data-ticker]");
      if (card) { event.preventDefault(); openDetail(card.dataset.ticker); }
    });
  }
  els.watchlist.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-ticker]");
    if (row) openDetail(row.dataset.ticker);
  });
  els.watchlist.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const row = event.target.closest("tr[data-ticker]");
    if (row) { event.preventDefault(); openDetail(row.dataset.ticker); }
  });
  els.search.addEventListener("input", () => { state.search = els.search.value.trim(); state.page = 1; renderWatchlist(); });
  els.market.addEventListener("change", () => { state.market = els.market.value; state.page = 1; renderWatchlist(); });
  els.lifecycle.addEventListener("change", () => { state.lifecycle = els.lifecycle.value; state.page = 1; renderWatchlist(); });
  els.opportunity.addEventListener("change", () => { state.opportunity = els.opportunity.value; state.page = 1; renderWatchlist(); });
  els.sort.addEventListener("change", () => { state.sort = els.sort.value; state.page = 1; renderWatchlist(); });
  els.clearFilters.addEventListener("click", () => {
    state.search = ""; state.market = "all"; state.lifecycle = "all"; state.opportunity = "all"; state.sort = "attention"; state.page = 1;
    els.search.value = ""; els.market.value = "all"; els.lifecycle.value = "all"; els.opportunity.value = "all"; els.sort.value = "attention";
    renderWatchlist();
  });
  els.loadMore.addEventListener("click", () => { state.page += 1; renderWatchlist(); });
  els.drawerClose.addEventListener("click", closeDetail);
  els.backdrop.addEventListener("click", closeDetail);
  els.refresh.addEventListener("click", async () => {
    els.refresh.disabled = true;
    try { await loadData({ silent: true }); toast("看板数据已重新读取"); } catch (error) { toast(`读取失败：${error.message}`); } finally { els.refresh.disabled = false; }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !els.drawer.hidden) closeDetail();
    if (event.key === "/" && document.activeElement?.tagName !== "INPUT") { event.preventDefault(); els.search.focus(); }
  });
}

bindEvents();
loadData().catch((error) => {
  els.attentionList.innerHTML = `<div class="loading-card">看板加载失败：${escapeHtml(error.message)}</div>`;
  els.holdingList.innerHTML = "";
  els.watchlistMeta.textContent = "数据不可用，请检查本地静态数据。";
  els.quoteStatus.dataset.tone = "error";
  els.quoteStatusText.textContent = "数据加载失败";
  console.error("dashboard load failed", error);
});
