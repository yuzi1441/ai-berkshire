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
  lifecycleHint: { WATCH: "等待条件或价格", PRE_BUY: "买入前流程中的公司", HOLDING: "优先管理已有仓位", EXITED: "历史持仓周期" },
  scope: { entry: "买入条件", validation: "验证条件", redline: "失效条件", unknown: "其他条件" },
  ruleStatus: { triggered: "已触发", near_trigger: "接近触发", not_triggered: "未触发", unknown: "待判断", needs_review: "需要复核", stale: "数据过期" },
  ruleType: { PRICE_RANGE: "价格条件", METRIC: "经营条件", EVENT: "事件条件" },
  action: {
    run_checklist: "进行买入前检查",
    run_drift: "进行投资逻辑漂移检查",
    drift_recheck: "补充投资逻辑复核证据",
    keep_watch: "继续观察",
    review_decision: "重新评估",
    drop_or_recheck: "降级观察 / 重新检查",
    exit_review: "退出复核",
    hold: "继续持有",
    add_reduce_review: "加仓 / 减仓复核",
    reduce_review: "减仓复核",
    confirm_purchase: "确认买入条件",
    price_near_trigger: "接近价格条件",
    condition_near_trigger: "接近经营条件",
    review_holding: "持仓投资逻辑复核",
    none: "暂不处理",
  },
  drift: { improved: "投资逻辑改善", unchanged: "投资逻辑未变", weakened: "投资逻辑走弱", broken: "投资逻辑失效", unknown: "尚未复核" },
  eventState: { important: "重要事件", watch: "普通观察", normal: "暂无重大变化", unknown: "未知", partial: "部分可用" },
  technical: { UP: "上升", DOWN: "下降", SIDEWAYS: "震荡", UNKNOWN: "未知", BROKEN: "弱势区间", NEAR_MEAN: "接近均值", EXTENDED: "偏离均值", FAVORABLE: "有利", UNFAVORABLE: "不利", NEUTRAL: "一般" },
  sentiment: { positive: "偏正面", neutral: "中性", negative: "偏负面", mixed: "分化", unknown: "未知" },
  dataStatus: { fresh: "新鲜", partial: "部分可用", stale: "数据过期", unknown: "未知", unavailable: "不可用", unsupported: "暂不支持", not_applicable: "不适用", ready: "已准备" },
};

const WORKSPACES = {
  attention: "今日处理",
  holdings: "我的持仓",
  opportunities: "买入候选",
  "ai-research": "AI 每日机会",
  watchlist: "研究池",
};

const SKILL_DISPLAY_LABELS = {
  "thesis-drift": "正式投资逻辑复核",
  "thesis-tracker": "持仓投资逻辑跟踪",
  "investment-research": "完整投资研究",
};

const CHECKLIST_DISPLAY_LABELS = {
  PASS: "通过",
  CONDITIONAL_PASS: "条件通过",
  FAIL: "未通过",
  UNKNOWN: "尚未检查",
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
  originalTheses: "./data/original_buy_theses.json",
  quotes: "./data/quotes/latest.json",
  intraday: "./data/intraday_technical.json",
  opportunityScans: "./data/opportunity_scans.json",
  opportunityScanStatus: "./data/opportunity_scan_status.json",
};

const OPTIONAL_DATA_FALLBACKS = {
  events: { companies: [] },
  technical: { companies: [] },
  sentiment: { companies: [], status: "unknown" },
  sentimentStatus: { status: "unknown" },
  quotes: { quotes: [] },
  originalTheses: { schema_version: 2, cycles: {}, active_position_ids: {} },
  intraday: { companies: [] },
  opportunityScans: { schema_version: 1, status: "unavailable", scans: [] },
  opportunityScanStatus: { schema_version: 1 },
};

const state = {
  board: null,
  companyState: new Map(),
  rulePackages: new Map(),
  events: new Map(),
  technical: new Map(),
  sentiment: new Map(),
  tracking: new Map(),
  originalTheses: { schema_version: 2, cycles: {}, active_position_ids: {} },
  quotes: new Map(),
  quoteMeta: null,
  sentimentMeta: null,
  opportunityScans: new Map(),
  opportunityScanMeta: { status: "missing", scans: [] },
  dispositionAccess: false,
  dispositionAuthority: null,
  pendingDisposition: null,
  loadedAt: null,
  loadSequence: 0,
  opportunityView: "checklist",
  attentionExpanded: false,
  opportunityExpanded: false,
  aiOpportunityExpanded: false,
  search: "",
  market: "all",
  lifecycle: "all",
  actionStatus: "all",
  skill: "all",
  lightThesis: "all",
  formalDrift: "all",
  blocker: "all",
  checklist: "all",
  priceNear: false,
  opportunity: "all",
  sort: "attention",
  quickFilter: "all",
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
  checklistTabCount: document.querySelector("#checklist-tab-count"),
  opportunityPrimaryNote: document.querySelector("#opportunity-primary-note"),
  opportunityPoolNote: document.querySelector("#opportunity-pool-note"),
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
  actionStatus: document.querySelector("#action-status-filter"),
  skill: document.querySelector("#skill-filter"),
  lightThesis: document.querySelector("#light-thesis-filter"),
  formalDrift: document.querySelector("#formal-drift-filter"),
  blocker: document.querySelector("#blocker-filter"),
  checklist: document.querySelector("#checklist-filter"),
  opportunity: document.querySelector("#opportunity-filter"),
  sort: document.querySelector("#sort-filter"),
  quickFilters: document.querySelector(".quick-filter-bar"),
  moreFilters: document.querySelector("#more-filters"),
  advancedFilterCount: document.querySelector("#advanced-filter-count"),
  activeFilterChips: document.querySelector("#active-filter-chips"),
  clearFilters: document.querySelector("#clear-filters"),
  drawer: document.querySelector("#detail-drawer"),
  backdrop: document.querySelector("#drawer-backdrop"),
  drawerKicker: document.querySelector("#drawer-kicker"),
  drawerTitle: document.querySelector("#drawer-title"),
  drawerSubtitle: document.querySelector("#drawer-subtitle"),
  drawerContent: document.querySelector("#drawer-content"),
  drawerClose: document.querySelector("#drawer-close"),
  dispositionDialog: document.querySelector("#disposition-dialog"),
  dispositionDialogTitle: document.querySelector("#disposition-dialog-title"),
  dispositionDialogCopy: document.querySelector("#disposition-dialog-copy"),
  dispositionCancel: document.querySelector("#disposition-cancel"),
  dispositionConfirm: document.querySelector("#disposition-confirm"),
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
const PAGE_RESUME_REFRESH_AGE_MS = 60_000;
let dataRequestSequence = 0;

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

function shortText(value, limit = 72) {
  const normalized = String(value ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) return "—";
  return normalized.length > limit ? `${normalized.slice(0, Math.max(1, limit - 1))}…` : normalized;
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

function originalThesisFor(record) {
  const tracking = trackingFor(record);
  if (!tracking || lifecycleOf(record) !== "HOLDING") return null;
  const payload = state.originalTheses || {};
  const ticker = record?.ticker;
  const cycleId = tracking.position_id || (ticker && tracking.buy_date ? `${ticker}:${tracking.buy_date}` : null);
  const activeId = payload.active_position_ids?.[ticker];
  const cycles = payload.cycles || {};
  // Prefer the position's explicit cycle binding.  The active map is only a
  // compatibility fallback for older tracking records.
  return (cycleId && cycles[cycleId]) || (activeId && cycles[activeId]) || payload.positions?.[ticker] || null;
}

function renderFrozenThesis(snapshot) {
  if (!snapshot) return "";
  const sourceText = String(snapshot.source_text || "").trim();
  const provenance = snapshot.backfilled ? "历史补录，不能完全还原买入时快照" : "买入时冻结";
  const captured = snapshot.captured_at ? ` · 保存于 ${formatDateTime(snapshot.captured_at)}` : "";
  const body = sourceText
    ? `<details class="thesis-snapshot"><summary>查看买入时冻结逻辑（${escapeHtml(provenance)}${escapeHtml(captured)}）</summary><div class="thesis-snapshot-text">${escapeHtml(sourceText)}</div></details>`
    : `<div class="source-line">${escapeHtml(provenance)}${escapeHtml(captured)}；当前只保存投资逻辑哈希。</div>`;
  return body;
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
  return record?.action_guidance?.requires_user_action === true;
}

function guidanceFor(record) {
  return record?.action_guidance || {
    blocker_code: "state_projection_missing",
    blocker_text: "当前导航状态尚未生成",
    next_action_code: "wait_for_state_refresh",
    next_action_text: "等待系统刷新状态",
    recommended_skill: [],
    recommended_skill_reason: "缺少确定性导航投影，不能从页面自行推断任务",
    priority: "none",
    requires_user_action: false,
    completion_target: "状态刷新后重新判断",
  };
}

function skillDisplayLabel(skill) {
  return SKILL_DISPLAY_LABELS[skill] || skill;
}

function recommendedSkillIds(record) {
  const guidance = guidanceFor(record);
  if (!guidance.requires_user_action) return [];
  const skills = Array.isArray(guidance.recommended_skill) ? guidance.recommended_skill : [];
  return skills.filter(Boolean);
}

function recommendedSkillText(record) {
  const guidance = guidanceFor(record);
  if (!guidance.requires_user_action) return "无需运行";
  const skills = recommendedSkillIds(record);
  return skills.length ? skills.map(skillDisplayLabel).join(" + ") : "无需重复运行 · 人工判断";
}

function renderRecommendedSkill(record) {
  const skills = recommendedSkillIds(record);
  if (!skills.length) return escapeHtml(recommendedSkillText(record));
  return `<span class="skill-display-list">${skills.map((skill) => `<span class="skill-display"><span>${escapeHtml(skillDisplayLabel(skill))}</span><small>${escapeHtml(skill)}</small></span>`).join("")}</span>`;
}

function actionLabel(record) {
  return text(guidanceFor(record).next_action_text, label("action", record?.next_action, "继续观察"));
}

function driftScanLabel(record) {
  const review = record?.drift_review || {};
  const scan = record?.drift_scan || {};
  if (review.category === "true_current_drift") return "系统建议重新复核投资逻辑";
  if (review.category === "new_evidence_other_action") return "存在新材料，当前动作不是投资逻辑漂移";
  if (review.category === "reviewed_not_recognized") return "投资逻辑复核状态异常";
  if (review.category === "never_reviewed") return "从未完成投资逻辑漂移复核";
  if (review.category === "reviewed_insufficient_evidence") return "投资逻辑已复核 · 证据不足";
  if (review.category === "reviewed_current") return "投资逻辑已复核 · 当前有效";
  if (scan.status === "current" && scan.result === "unchanged") return "Drift 已复核 · 无变化";
  if (scan.status === "current" && scan.result === "unknown") return "Drift 待复核 · 证据不足";
  if (scan.status === "stale") return "投资逻辑复核水位待更新";
  if (scan.status === "missing") return "从未完成投资逻辑漂移复核";
  return label("drift", record?.drift?.direction);
}

function ruleActionLabel(rule) {
  return rule?.action ? label("action", rule.action, "动作待确认") : "动作待确认";
}

function actionTone(action) {
  if (["run_drift", "drop_or_recheck", "exit_review", "reduce_review"].includes(action)) return "red";
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

function todayInShanghai() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(new Date());
}

function opportunityScanDayStatus(meta) {
  const status = meta?.status || "missing";
  if (["ok", "ready", "partial"].includes(status)) {
    const attemptedAt = meta?.scan_generated_at || meta?.generated_at || meta?.attempted_at;
    if (attemptedAt && formatDate(attemptedAt) !== todayInShanghai()) return "not_run_today";
  }
  return status;
}

function opportunityScanDisplayTimestamp(meta) {
  return meta?.display_result_generated_at
    || meta?.last_success_scan_generated_at
    || meta?.last_success_at
    || meta?.generated_at
    || null;
}

function hasDisplayableOpportunityScan(meta) {
  return Boolean(opportunityScanDisplayTimestamp(meta) && state.opportunityScans.size);
}

function opportunityScanDisplayMode(meta) {
  const status = opportunityScanDayStatus(meta);
  if (!hasDisplayableOpportunityScan(meta)) return "empty";
  if (["ok", "ready", "partial"].includes(status)) return "current";
  if (status === "not_run_today") return "carry_forward";
  if (["error", "stale"].includes(status)) return "fallback";
  return "historical";
}

function aiOpportunityDisplayStatusText(meta) {
  const status = opportunityScanDayStatus(meta);
  const mode = opportunityScanDisplayMode(meta);
  if (mode === "carry_forward") return "今日尚未刷新 · 展示最近一次成功结果";
  if (mode === "fallback") {
    return status === "error"
      ? "今日刷新失败 · 展示最近一次成功结果"
      : "最新刷新异常 · 展示最近一次成功结果";
  }
  return aiScanStatusText(status);
}

function aiNavigationCount() {
  if (!hasDisplayableOpportunityScan(state.opportunityScanMeta)) return "—";
  return String(aiOpportunityItems().length);
}

function renderWorkspaceNav() {
  const attentionToday = attentionRecords().length;
  const counts = {
    attention: attentionToday,
    holdings: stateCount("HOLDING"),
    opportunities: stateCount("PRE_BUY"),
    "ai-research": aiNavigationCount(),
    watchlist: stateRecords().filter((record) => !["HOLDING", "EXITED"].includes(lifecycleOf(record))).length,
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

function formalImportantEvent(record) {
  const radar = record?.event_radar || {};
  const events = Array.isArray(radar.events) ? radar.events : [];
  return events.find((event) => (
    ["A", "B"].includes(event.highest_source_tier)
      && event.thesis_relevant === true
      && ["important", "critical"].includes(event.state)
  )) || null;
}

function hasUncoveredFormalImportantEvent(record) {
  const event = formalImportantEvent(record);
  if (!event) return false;
  const review = record?.drift_review || {};
  const scan = record?.drift_scan || {};
  // A current unchanged checkpoint already covers the event.  Keep the event
  // visible in the detail view, but do not recreate the same human task.
  if (
    review.category === "reviewed_current"
      || (scan.status === "current" && scan.result === "unchanged")
  ) return false;
  return true;
}

function hasFormalImportantEvent(record) {
  const radar = record?.event_radar || {};
  return ["important", "critical"].includes(radar.state) && hasUncoveredFormalImportantEvent(record);
}

function reviewDue(record) {
  const nextReview = trackingFor(record)?.next_review_date;
  if (!nextReview) return false;
  const today = todayInShanghai();
  return String(nextReview).slice(0, 10) <= today;
}

function attentionTier(record) {
  return guidanceFor(record).priority === "urgent" ? "must" : "soon";
}

function attentionTierLabel(tier) {
  return { must: "需要及时处置", soon: "需要人工完成" }[tier] || "需要人工完成";
}

function attentionReasonType(record) {
  const action = guidanceFor(record).next_action_code;
  return {
    review_investment_thesis: "投资逻辑复核",
    review_holding_thesis: "持仓投资逻辑复核",
    review_holding_cycle: "持仓复核",
    decide_research_disposition: "研究去留判断",
    decide_holding_disposition: "持仓判断",
    make_purchase_decision: "买入判断",
    run_investment_checklist: "买入前检查",
    verify_condition_evidence: "事实核验",
  }[action] || "人工决策";
}

function attentionSummary(record) {
  return shortText(guidanceFor(record).blocker_text, 120);
}

function attentionTone(record) {
  return guidanceFor(record).priority === "urgent" ? "danger" : "warning";
}

function statusCard(lifecycle, value, hint, tone) {
  return `<button class="status-card" type="button" data-lifecycle-jump="${lifecycle}" data-tone="${tone}">
    <span class="status-card-label">${escapeHtml(label("lifecycle", lifecycle))}</span>
    <strong class="status-card-value">${escapeHtml(value)}</strong>
    <span class="status-card-hint">${escapeHtml(hint)}</span>
  </button>`;
}

function renderStatusCards() {
  const attentionCount = attentionRecords().length;
  els.statusCards.innerHTML = [
    statusCard("WATCH", stateCount("WATCH"), label("lifecycleHint", "WATCH"), "blue"),
    statusCard("PRE_BUY", stateCount("PRE_BUY"), label("lifecycleHint", "PRE_BUY"), "yellow"),
    statusCard("HOLDING", stateCount("HOLDING"), label("lifecycleHint", "HOLDING"), "green"),
    `<button class="status-card" type="button" data-opportunity-jump="attention" data-tone="red">
      <span class="status-card-label">需要人工处理</span>
      <strong class="status-card-value">${escapeHtml(attentionCount)}</strong>
      <span class="status-card-hint">其余变化由系统继续观察</span>
    </button>`,
  ].join("");
}

function renderTopMeta() {
  const generated = state.board?.generated_at || state.loadedAt;
  els.lastUpdated.textContent = formatDateTime(generated);
  const total = stateRecords().length;
  const ruleCount = [...state.rulePackages.values()].reduce((sum, pack) => sum + (Array.isArray(pack?.rules) ? pack.rules.length : 0), 0);
  els.datasetSummary.textContent = `${total} 家公司 · ${ruleCount} 条规则`;
  const annualHealth = state.board?.data_health?.annual_report_dates || {};
  if (["partial", "failed"].includes(annualHealth.status)) {
    const healthLabel = annualHealth.status === "failed" ? "更新失败，保留历史" : "部分来源可用";
    els.datasetSummary.textContent += ` · 财报日期${healthLabel}（成功 ${formatDateTime(annualHealth.last_success_at)}；尝试 ${formatDateTime(annualHealth.last_attempt_at)}）`;
  }
  els.datasetSummary.title = (annualHealth.source_outcomes || [])
    .filter((item) => item.status === "failed")
    .map((item) => `${item.source} ${item.report_period}: ${item.error || "获取失败"}`).join("\n");
  const quoteUniverse = stateRecords().filter((record) => ["A股", "港股"].includes(record.market));
  const quoteCount = quoteUniverse.filter((record) => state.quotes.has(record.ticker)).length;
  const quoteTotal = quoteUniverse.length;
  const quoteMeta = state.quoteMeta || {};
  const quoteDate = quoteMeta.data_cutoff || quoteMeta.generated_at;
  const phase = quoteMeta.quote_phase;
  const sourceStatus = quoteMeta.source_status || (quoteCount ? "partial" : "unavailable");
  const isComplete = quoteCount === quoteTotal && sourceStatus === "ok";
  els.quoteStatus.dataset.tone = isComplete ? "fresh" : "stale";
  let quoteLabel = sourceStatus === "unavailable"
    ? quoteCount ? "行情更新失败 · 保留上次数据" : "行情更新失败"
    : quoteCount < quoteTotal
      ? "行情部分可用"
      : phase === "intraday"
        ? "行情盘中"
        : phase === "historical_close"
          ? "行情历史收盘"
          : "行情收盘";
  const cutoffLabel = quoteDate && phase !== "intraday" ? ` · 截至 ${formatDate(quoteDate)} 收盘` : quoteDate ? ` · ${formatDateTime(quoteDate)}` : "";
  els.quoteStatusText.textContent = `${quoteLabel} · ${quoteCount}/${quoteTotal}${cutoffLabel}`;
}

function cardCompany(record) {
  const quote = quoteFor(record);
  return `<div class="card-company"><span class="company-name">${escapeHtml(text(record.company))}</span><span class="company-code">${escapeHtml(record.market || "待识别")} · ${escapeHtml(record.ticker)}</span><span class="price-value">${escapeHtml(formatPrice(quote))}</span></div>`;
}

function compactCompany(record) {
  return `<div class="card-company"><span class="company-name">${escapeHtml(text(record.company))}</span><span class="company-code">${escapeHtml(record.market || "待识别")} · ${escapeHtml(record.ticker)}</span></div>`;
}

function renderAttentionCard(record) {
  const guidance = guidanceFor(record);
  return `<article class="attention-card" data-ticker="${escapeHtml(record.ticker)}" data-tone="${attentionTone(record)}" tabindex="0" role="button">
    <div class="card-topline">${compactCompany(record)}<span class="lifecycle-badge" data-lifecycle="${escapeHtml(lifecycleOf(record))}">${escapeHtml(label("lifecycle", lifecycleOf(record)))}</span></div>
    <div class="attention-kind">${escapeHtml(attentionReasonType(record))}</div>
    <p class="attention-reason"><strong>${escapeHtml(attentionSummary(record))}</strong></p>
    <div class="attention-route"><span>下一步</span><strong>${escapeHtml(actionLabel(record))}</strong></div>
    <div class="attention-route"><span>使用 Skill</span><strong>${renderRecommendedSkill(record)}</strong></div>
    <p class="attention-explain">${escapeHtml(guidance.recommended_skill_reason)}</p>
    <div class="attention-completion">完成标准：${escapeHtml(guidance.completion_target)}</div>
  </article>`;
}

function attentionRecords() {
  return stateRecords().filter(hasAttention).sort((a, b) => {
    const priorityScore = { urgent: 2, normal: 1, none: 0 };
    return (priorityScore[guidanceFor(b).priority] || 0) - (priorityScore[guidanceFor(a).priority] || 0)
      || String(a.company).localeCompare(String(b.company), "zh-CN");
  });
}

function renderAttention() {
  const records = attentionRecords();
  const count = records.length;
  const tierCounts = records.reduce((result, record) => {
    const tier = attentionTier(record);
    result[tier] += 1;
    return result;
  }, { must: 0, soon: 0, changes: 0 });
  els.attentionCount.textContent = `${count} 项 · 及时处置 ${tierCounts.must}`;
  const visible = state.attentionExpanded ? records : records.slice(0, 8);
  const grouped = ["must", "soon"].map((tier) => ({ tier, records: visible.filter((record) => attentionTier(record) === tier) })).filter((group) => group.records.length);
  els.attentionList.innerHTML = grouped.length
    ? grouped.map(({ tier, records: tierRecords }) => `<div class="attention-layer"><div class="attention-layer-heading"><span>${escapeHtml(attentionTierLabel(tier))}</span><span>${tierRecords.length}${state.attentionExpanded ? " 项" : " 项已显示"}</span></div><div class="attention-layer-grid">${tierRecords.map(renderAttentionCard).join("")}</div></div>`).join("")
    : `<div class="loading-card">今天没有需要你处理的事项，系统会继续观察。</div>`;
  els.attentionViewAll.hidden = records.length <= 8;
  els.attentionViewAll.textContent = state.attentionExpanded ? "收起" : `查看全部（${count}）`;
}

function opportunityStatus(item) {
  return item?.status || "unknown";
}

function opportunityPriority(item) {
  return { triggered: 3, near_trigger: 2, unknown: 1, not_triggered: 0 }[opportunityStatus(item)] || 0;
}

function currentOpportunityStatusCounts(items) {
  return items.reduce((counts, item) => {
    const status = opportunityStatus(item.opportunity);
    if (Object.hasOwn(counts, status)) counts[status] += 1;
    else counts.unknown += 1;
    return counts;
  }, { triggered: 0, near_trigger: 0, unknown: 0, not_triggered: 0 });
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

function checklistRecords() {
  return stateRecords()
    .filter((record) => !["HOLDING", "EXITED"].includes(lifecycleOf(record)) && ["run_checklist", "confirm_purchase"].includes(record.next_action))
    .map((record) => {
      const candidates = [...priceOpportunities(record), ...conditionOpportunities(record)]
        .filter((opportunity) => {
          const rule = rulesFor(record).find((candidate) => candidate.rule_id === opportunity.rule_id);
          return rule?.rule_scope !== "redline";
        })
        .sort((a, b) => opportunityPriority(b) - opportunityPriority(a));
      return {
        record,
        stage: lifecycleOf(record) === "PRE_BUY"
          ? record.next_action === "confirm_purchase" ? "检查已完成，等待本人决策" : "已进入买入前检查"
          : "研究推进候选",
        opportunity: candidates[0] || {
          type: "CHECKLIST",
          status: "unknown",
          condition: "当前动作已进入研究推进；请查看检查依据",
        },
      };
    });
}

function opportunityTarget(opportunity, record) {
  if (opportunity.type === "PRICE_RANGE" || opportunity.min != null || opportunity.max != null) return opportunity.condition || "报告价格区间";
  return opportunity.condition || record?.conclusion_summary || "等待正文条件确认";
}

function renderOpportunityCard(item, kind) {
  const { record, opportunity } = item;
  const status = opportunityStatus(opportunity);
  const contextLabel = kind === "price" ? "价格条件" : kind === "condition" ? "待验证条件" : "当前阶段";
  const contextValue = kind === "checklist"
    ? item.stage
    : opportunityTarget(opportunity, record);
  return `<article class="opportunity-card" data-ticker="${escapeHtml(record.ticker)}" tabindex="0" role="button">
    <div class="opportunity-topline">${cardCompany(record)}<span class="mini-badge opportunity-status" data-status="${escapeHtml(status)}">${escapeHtml(label("ruleStatus", status))}</span></div>
    <div class="opportunity-context"><span class="opportunity-label">${escapeHtml(contextLabel)}</span><span class="opportunity-condition">${escapeHtml(contextValue)}</span></div>
    <div class="opportunity-action" data-tone="${escapeHtml(actionTone(record.next_action))}">${escapeHtml(actionLabel(record))}<span aria-hidden="true">→</span></div>
  </article>`;
}

function renderOpportunities() {
  const prices = opportunityRecords("price");
  const conditions = opportunityRecords("condition");
  const checklists = checklistRecords();
  const preBuyCount = stateCount("PRE_BUY");
  const preBuyChecklists = checklists.filter(({ record }) => lifecycleOf(record) === "PRE_BUY");
  const researchCandidates = checklists.filter(({ record }) => lifecycleOf(record) === "WATCH");
  els.priceCount.textContent = String(prices.length);
  els.conditionCount.textContent = String(conditions.length);
  els.checklistCount.textContent = String(preBuyCount);
  if (els.checklistTabCount) els.checklistTabCount.textContent = String(checklists.length);
  if (els.opportunityPrimaryNote) {
    els.opportunityPrimaryNote.textContent = `${preBuyCount} 家处于买入前流程；${researchCandidates.length} 家仍是观察中的研究推进候选。价格和经营条件只作为二级条件池，不等于当前机会。`;
  }
  if (els.opportunityPoolNote) {
    if (state.opportunityView === "checklist") {
      els.opportunityPoolNote.textContent = "只展示当前已有推进动作的候选；观察中的公司不会被自动改成买入前生命周期。";
    } else {
      const statusCounts = currentOpportunityStatusCounts(state.opportunityView === "price" ? prices : conditions);
      els.opportunityPoolNote.textContent = `这是条件池：已触发 ${statusCounts.triggered} · 接近 ${statusCounts.near_trigger} · 待判断 ${statusCounts.unknown} · 未触发 ${statusCounts.not_triggered}。只有已触发且通过资格校验的条件，才会进入买入前检查。`;
    }
  }
  const current = state.opportunityView === "checklist" ? checklists : state.opportunityView === "price" ? prices : conditions;
  const visible = state.opportunityExpanded ? current : current.slice(0, 8);
  els.opportunityList.innerHTML = current.length ? visible.map((item) => renderOpportunityCard(item, state.opportunityView)).join("") : `<div class="loading-card">暂时没有可展示的机会。</div>`;
  els.opportunityViewAll.hidden = current.length <= 8;
  const viewLabel = state.opportunityView === "checklist" ? "研究候选" : "条件池";
  els.opportunityViewAll.textContent = state.opportunityExpanded ? `收起${viewLabel}` : `查看全部${viewLabel}（${current.length}）`;
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
    partial: "部分完成",
    stale: "结果过期",
    not_run_today: "今日尚未扫描",
    error: "扫描失败",
    missing: "尚未扫描",
    unavailable: "不可用",
  }[status] || "待复核";
}

function aiOpportunityItems() {
  if (!hasDisplayableOpportunityScan(state.opportunityScanMeta)) return [];
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
  const generatedAt = scan.generated_at || opportunityScanDisplayTimestamp(state.opportunityScanMeta);
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
  const status = opportunityScanDayStatus(meta);
  const displayMode = opportunityScanDisplayMode(meta);
  const hasDisplayable = hasDisplayableOpportunityScan(meta);
  const coverage = hasDisplayable && Number.isFinite(Number(meta.display_scan_count)) && Number.isFinite(Number(meta.display_expected_scan_count))
    ? ` · ${meta.display_scan_count}/${meta.display_expected_scan_count}`
    : "";
  const currentCount = hasDisplayable && Number.isFinite(Number(meta.display_current_opportunity_count)) ? Number(meta.display_current_opportunity_count) : null;
  const nearCount = hasDisplayable && Number.isFinite(Number(meta.display_near_opportunity_count)) ? Number(meta.display_near_opportunity_count) : null;
  const opportunitySummary = currentCount !== null
    ? ` · 当前机会 ${currentCount}${nearCount !== null ? ` · 临近 ${nearCount}` : ""}`
    : "";
  const displayAt = opportunityScanDisplayTimestamp(meta);
  els.aiOpportunityMeta.textContent = `${aiOpportunityDisplayStatusText(meta)}${coverage}${opportunitySummary}${displayAt ? ` · ${formatDateTime(displayAt)}` : ""}`;
  if (items.length) {
    const visible = state.aiOpportunityExpanded ? items : items.slice(0, 6);
    els.aiOpportunityList.innerHTML = visible.map(renderAiOpportunityCard).join("");
    els.aiOpportunityViewAll.hidden = items.length <= 6;
    els.aiOpportunityViewAll.textContent = state.aiOpportunityExpanded ? "收起" : `查看全部 AI 研究机会（${items.length}）`;
    return;
  }
  els.aiOpportunityViewAll.hidden = true;
  if (hasDisplayable) {
    const suffix = displayMode === "carry_forward"
      ? "；今日尚未刷新。"
      : displayMode === "fallback"
        ? "；今日刷新未成功，当前仍展示最近一次成功结果。"
        : "。";
    const base = currentCount === 0 && nearCount === 0
      ? `最近一次成功扫描（${formatDateTime(displayAt)}）没有筛出当前或临近研究机会`
      : `当前展示最近一次成功扫描（${formatDateTime(displayAt)}）的结果`;
    els.aiOpportunityList.innerHTML = `<div class="ai-opportunity-empty">${escapeHtml(base + suffix)}</div>`;
    return;
  }
  const message = status === "missing"
    ? "本地暂无 AI 每日研究机会扫描结果。结果生成后会显示在这里，不影响其他看板模块。"
    : status === "error"
      ? "今日 AI 研究机会扫描失败，且当前没有可展示的成功结果。"
    : status === "unavailable"
        ? "AI 每日研究机会暂时不可用；未生成研究机会，也未改变买入候选。"
      : status === "partial"
        ? "今日 AI 研究机会扫描仅部分完成；结果不代表完整覆盖，请以扫描状态为准。"
      : status === "stale"
        ? "最近一次 AI 研究机会结果已过期；未将过期结果当作当前机会。"
        : currentCount === 0 && nearCount === 0
          ? "今日扫描完成，当前没有筛出机会。"
          : "本次扫描没有筛出当前或临近研究机会。";
  els.aiOpportunityList.innerHTML = `<div class="ai-opportunity-empty">${escapeHtml(message)}</div>`;
}

function renderAiOpportunitySection(record) {
  const scan = state.opportunityScans.get(record?.ticker);
  if (!scan || !hasDisplayableOpportunityScan(state.opportunityScanMeta)) return "";
  const classification = aiScanClassification(scan);
  const whyNow = aiScanText(scan, "why_now");
  const summary = aiScanText(scan, "opportunity_summary");
  const satisfied = aiScanAssessments(scan).flatMap(({ assessment }) => Array.isArray(assessment.satisfied_conditions) ? assessment.satisfied_conditions : []).filter(Boolean);
  const unmet = aiScanAssessments(scan).flatMap(({ assessment }) => Array.isArray(assessment.unmet_conditions) ? assessment.unmet_conditions : []).filter(Boolean);
  const historicalNote = opportunityScanDisplayMode(state.opportunityScanMeta) === "current"
    ? ""
    : `<div class="source-line">当前展示最近一次成功 AI 机会结果 · ${escapeHtml(formatDateTime(opportunityScanDisplayTimestamp(state.opportunityScanMeta)))}</div>`;
  return `<div class="detail-section ai-opportunity-detail"><div class="detail-section-head"><h3>AI 每日研究机会</h3><span class="data-badge" data-status="${escapeHtml(scan.status || "unknown")}">${escapeHtml(classification)}</span></div><p class="detail-copy">这是独立的研究发现，不改变当前生命周期、决策规则或买入候选。</p>${whyNow ? `<div class="detail-field"><div class="detail-field-label">为什么现在</div><div class="detail-field-value">${escapeHtml(whyNow)}</div></div>` : ""}${summary ? `<div class="detail-field" style="margin-top:12px"><div class="detail-field-label">机会摘要</div><div class="detail-field-value">${escapeHtml(summary)}</div></div>` : ""}${satisfied.length ? `<div class="detail-field" style="margin-top:12px"><div class="detail-field-label">已满足条件</div><div class="detail-field-value">${escapeHtml(satisfied.join("；"))}</div></div>` : ""}${unmet.length ? `<div class="detail-field" style="margin-top:12px"><div class="detail-field-label">仍待确认</div><div class="detail-field-value">${escapeHtml(unmet.join("；"))}</div></div>` : ""}${historicalNote}</div>`;
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
  const snapshot = originalThesisFor(record);
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
      <div><div class="holding-detail-label">买入日期</div><div class="holding-detail-value">${escapeHtml(formatDate(tracking.buy_date))}</div><div class="holding-detail-label" style="margin-top:9px">原始买入逻辑</div><div class="holding-detail-value">${snapshot ? "已绑定当前持仓周期" : "冻结基线未加载"}</div>${renderFrozenThesis(snapshot)}<div class="holding-detail-label" style="margin-top:9px">最新研究</div><div class="holding-detail-value"><a class="text-link" href="${escapeHtml(reportHref(tracking.thesis_report_path || record.canonical_report))}" target="_blank" rel="noreferrer" data-stop-card>查看最新研究</a></div></div>
      <div><div class="holding-detail-label">投资逻辑状态 / 最近漂移</div><div class="holding-detail-value">${escapeHtml(thesisLabel(tracking.thesis_status))} · ${escapeHtml(label("drift", drift.direction))}</div><div class="holding-detail-label" style="margin-top:9px">关键失效条件</div><ul class="redline-list">${redlines.length ? redlines.map((rule) => `<li>${escapeHtml(rule.condition)}</li>`).join("") : "<li>报告未提取明确失效条件</li>"}</ul></div>
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
  const reviewCategory = record?.drift_review?.category;
  const drift = {
    true_current_drift: "待复核",
    new_evidence_other_action: "有新材料",
    reviewed_not_recognized: "状态异常",
    never_reviewed: "未复核",
    reviewed_insufficient_evidence: "证据不足",
    reviewed_current: "已复核",
  }[reviewCategory] || ({
    current: "已复核",
    stale: "待更新",
    missing: "未复核",
  }[record?.drift_scan?.status] || "待复核");
  const event = label("eventState", record?.event_radar?.state);
  const technical = dataLabel(record?.technical?.freshness || record?.technical?.status);
  const sentiment = sentimentLabel(record).stateText;
  return `<div class="compact-statuses"><span>投资逻辑：${escapeHtml(drift)}</span><span>事件：${escapeHtml(event)}</span><span>技术：${escapeHtml(technical)}</span><span>情绪：${escapeHtml(sentiment)}</span></div>`;
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

function actionableSkills(records) {
  return [...new Set(records.flatMap((record) => {
    const guidance = record?.action_guidance || {};
    return guidance.requires_user_action === true && Array.isArray(guidance.recommended_skill)
      ? guidance.recommended_skill
      : [];
  }))].filter(Boolean).sort();
}

function lightThesisFilterValue(record) {
  const signal = record?.light_thesis_signal || {};
  return signal.status === "current" && signal.signal ? signal.signal : "missing";
}

function checklistDisplayLabel(value) {
  return CHECKLIST_DISPLAY_LABELS[String(value || "UNKNOWN").toUpperCase()] || CHECKLIST_DISPLAY_LABELS.UNKNOWN;
}

function formalDriftMatches(record, value) {
  if (value === "all") return true;
  const drift = record?.drift || {};
  const hasReview = Boolean(drift.last_checked);
  if (value === "has-review") return hasReview;
  if (value === "no-review") return !hasReview;
  if (!hasReview) return false;
  if (value === "major-weakened") return drift.direction === "weakened" && drift.severity === "major";
  if (value === "minor-weakened") return drift.direction === "weakened" && drift.severity === "minor";
  if (value === "improved") return drift.direction === "improved";
  return false;
}

function actionStatusMatches(record, value) {
  if (value === "all") return true;
  const guidance = record?.action_guidance || {};
  const requiresAction = guidance.requires_user_action === true;
  const skills = Array.isArray(guidance.recommended_skill) ? guidance.recommended_skill : [];
  if (value === "attention") return requiresAction;
  if (value === "skill") return requiresAction && skills.length > 0;
  if (value === "manual") return requiresAction && skills.length === 0;
  if (value === "observe") return !requiresAction;
  return false;
}

function skillMatches(record, value) {
  if (value === "all") return true;
  const guidance = record?.action_guidance || {};
  const skills = Array.isArray(guidance.recommended_skill) ? guidance.recommended_skill : [];
  if (value === "none") return guidance.requires_user_action !== true || skills.length === 0;
  return guidance.requires_user_action === true && skills.includes(value);
}

function matchesUnifiedFilters(record, filters) {
  const search = String(filters.search || "").toLowerCase();
  const guidance = record?.action_guidance || {};
  const checklistStatus = String(record?.checklist?.status || "UNKNOWN").toUpperCase();
  const matchesSearch = !search || `${record.company || ""} ${record.ticker || ""}`.toLowerCase().includes(search);
  const matchesMarket = filters.market === "all" || record.market === filters.market;
  const matchesLifecycle = filters.lifecycle === "all" || lifecycleOf(record) === filters.lifecycle;
  const matchesLight = filters.lightThesis === "all" || lightThesisFilterValue(record) === filters.lightThesis;
  const matchesBlocker = filters.blocker === "all" || guidance.blocker_code === filters.blocker;
  const matchesChecklist = filters.checklist === "all" || checklistStatus === filters.checklist;
  const matchesOpportunity = filters.opportunity === "all"
    || (filters.opportunity === "price" && priceOpportunities(record).length > 0)
    || (filters.opportunity === "condition" && conditionOpportunities(record).length > 0);
  const matchesPriceNear = !filters.priceNear
    || priceOpportunities(record).some((item) => item.status === "near_trigger");
  return matchesSearch
    && matchesMarket
    && matchesLifecycle
    && actionStatusMatches(record, filters.actionStatus)
    && skillMatches(record, filters.skill)
    && matchesLight
    && formalDriftMatches(record, filters.formalDrift)
    && matchesBlocker
    && matchesChecklist
    && matchesOpportunity
    && matchesPriceNear;
}

function filteredRecords() {
  const records = stateRecords().filter((record) => matchesUnifiedFilters(record, state));
  records.sort((a, b) => {
    if (state.sort === "name") return String(a.company).localeCompare(String(b.company), "zh-CN");
    if (state.sort === "lifecycle") return String(label("lifecycle", lifecycleOf(a))).localeCompare(String(label("lifecycle", lifecycleOf(b))), "zh-CN");
    if (state.sort === "price") return (priceOpportunities(b).length - priceOpportunities(a).length) || String(a.company).localeCompare(String(b.company), "zh-CN");
    return (hasAttention(b) ? 1 : 0) - (hasAttention(a) ? 1 : 0) || (lifecycleOf(a) === "HOLDING" ? -1 : 0) - (lifecycleOf(b) === "HOLDING" ? -1 : 0) || String(a.company).localeCompare(String(b.company), "zh-CN");
  });
  return records;
}

function setSelectOptions(select, options, selected) {
  select.innerHTML = options.map(({ value, label: optionLabel }) => `<option value="${escapeHtml(value)}">${escapeHtml(optionLabel)}</option>`).join("");
  select.value = options.some((item) => item.value === selected) ? selected : "all";
}

function populateDynamicFilters() {
  const records = stateRecords();
  setSelectOptions(els.skill, [
    { value: "all", label: "全部当前 Skill" },
    { value: "none", label: "无需运行 Skill" },
    ...actionableSkills(records).map((value) => ({ value, label: skillDisplayLabel(value) })),
  ], state.skill);
  state.skill = els.skill.value;
  const blockers = new Map();
  for (const record of records) {
    const guidance = record?.action_guidance || {};
    if (guidance.blocker_code) {
      const previous = blockers.get(guidance.blocker_code) || { label: "", count: 0 };
      const stableText = text(guidance.blocker_text, guidance.blocker_code).split(/[：:]/, 1)[0];
      blockers.set(guidance.blocker_code, {
        label: previous.label || shortText(stableText, 40),
        count: previous.count + 1,
      });
    }
  }
  setSelectOptions(els.blocker, [
    { value: "all", label: "全部卡点" },
    ...[...blockers.entries()]
      .sort((a, b) => a[1].label.localeCompare(b[1].label, "zh-CN"))
      .map(([value, item]) => ({ value, label: `${item.label} · ${item.count}` })),
  ], state.blocker);
  state.blocker = els.blocker.value;
}

function selectedOptionText(select) {
  return select?.selectedOptions?.[0]?.textContent?.trim() || "";
}

function activeFilterEntries() {
  const entries = [];
  const presetField = {
    attention: "actionStatus", skill: "actionStatus", manual: "actionStatus", observe: "actionStatus",
    "light-improved": "lightThesis", "light-weakened": "lightThesis", "price-near": "priceNear",
  }[state.quickFilter];
  const quickLabel = document.querySelector(`[data-quick-filter="${state.quickFilter}"]`)?.textContent?.trim();
  if (state.quickFilter !== "all" && quickLabel) entries.push({ key: "quickFilter", label: `快捷：${quickLabel}` });
  if (state.search) entries.push({ key: "search", label: `搜索：${state.search}` });
  for (const [key, select, prefix] of [
    ["market", els.market, "市场"], ["lifecycle", els.lifecycle, "阶段"],
    ["actionStatus", els.actionStatus, "处理"], ["skill", els.skill, "Skill"],
    ["lightThesis", els.lightThesis, "轻量逻辑"], ["formalDrift", els.formalDrift, "正式复核"],
    ["blocker", els.blocker, "卡点"], ["checklist", els.checklist, "Checklist"],
    ["opportunity", els.opportunity, "条件"],
  ]) {
    if (state[key] !== "all" && key !== presetField) entries.push({ key, label: `${prefix}：${selectedOptionText(select)}` });
  }
  if (state.priceNear && presetField !== "priceNear") entries.push({ key: "priceNear", label: "价格接近" });
  if (state.sort !== "attention") entries.push({ key: "sort", label: `排序：${selectedOptionText(els.sort)}` });
  return entries;
}

function renderFilterState() {
  document.querySelectorAll("[data-quick-filter]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.quickFilter === state.quickFilter);
  });
  const entries = activeFilterEntries();
  els.activeFilterChips.innerHTML = entries.length
    ? entries.map((entry) => `<button type="button" class="active-filter-chip" data-clear-filter="${escapeHtml(entry.key)}">${escapeHtml(entry.label)}<span aria-hidden="true">×</span></button>`).join("")
    : `<span class="filter-empty-note">当前显示全部公司</span>`;
  const advancedCount = ["market", "lifecycle", "actionStatus", "skill", "lightThesis", "formalDrift", "blocker", "checklist", "opportunity"].filter((key) => state[key] !== "all").length;
  els.advancedFilterCount.textContent = advancedCount ? `${advancedCount} 项已启用` : "未启用";
}

function renderWatchlist() {
  const records = filteredRecords();
  const pageRecords = records.slice(0, state.page * PAGE_SIZE);
  els.watchlist.innerHTML = pageRecords.map(renderWatchRow).join("");
  els.watchlistCount.textContent = `${records.length} / ${stateRecords().length} 家`;
  els.watchlistMeta.textContent = `当前结果：${records.length} / ${stateRecords().length} 家${pageRecords.length < records.length ? ` · 已显示 ${pageRecords.length} 家` : ""}`;
  els.loadMore.hidden = pageRecords.length >= records.length;
  els.loadMore.textContent = `加载更多（剩余 ${Math.max(0, records.length - pageRecords.length)} 家）`;
  els.emptyState.hidden = records.length > 0;
  renderFilterState();
}

function currentRecord(ticker) {
  return state.companyState.get(ticker) || null;
}

const DISPOSITION_LABELS = {
  keep_watch: "继续观察",
  redo_research: "重做研究",
  formal_drift: "正式 Drift",
  archive_drop: "停止重点跟踪",
};

const DISPOSITION_CONFIRM_COPY = {
  keep_watch: "关闭当前证据 fingerprint 对应的提醒。新证据或基线变化后会重新打开。",
  redo_research: "只记录研究意图，不会自动运行模型、生成报告或覆盖主报告。",
  formal_drift: "只记录正式复核意图，不会自动运行模型或写入正式 Drift 结论。",
  archive_drop: "只停止重点跟踪；不会删除研究、修改持仓、退出生命周期或移除 Rule。",
};

function renderDispositionControls(record) {
  const manual = record?.manual_disposition || {};
  const options = Array.isArray(manual.allowed_options) ? manual.allowed_options : [];
  if (!options.length) return "";
  if (manual.status === "current" && manual.selected_disposition) {
    return `<div class="detail-section disposition-panel"><div class="detail-section-head"><h3>人工处置</h3><span class="mini-badge">已记录</span></div><p class="detail-copy">${escapeHtml(DISPOSITION_LABELS[manual.selected_disposition] || manual.selected_disposition)}</p><div class="source-line">绑定当前任务 fingerprint${manual.selected_at ? ` · ${escapeHtml(formatDateTime(manual.selected_at))}` : ""}<br />新的证据、报告基线或正式 Drift 触发会重新打开任务。</div></div>`;
  }
  if (!state.dispositionAccess) {
    return `<div class="detail-section disposition-panel"><div class="detail-section-head"><h3>人工处置</h3><span class="mini-badge">只读</span></div><p class="detail-copy">请从受保护的管理入口记录处置。公开看板不能写入任何决定。</p></div>`;
  }
  if (record?.action_guidance?.requires_user_action !== true) return "";
  return `<div class="detail-section disposition-panel"><div class="detail-section-head"><h3>人工处置</h3><span class="mini-badge">需要本人确认</span></div><p class="detail-copy">选择只会写入运行态 disposition authority，并绑定当前任务 fingerprint。</p><div class="disposition-actions">${options.map((option) => `<button class="button ${option === "archive_drop" ? "button-quiet" : "button-outline"}" type="button" data-disposition="${escapeHtml(option)}">${escapeHtml(DISPOSITION_LABELS[option] || option)}</button>`).join("")}</div>${options.includes("archive_drop") ? `<div class="source-line">“停止重点跟踪”不会删除研究、不改持仓、不设为已退出。</div>` : ""}</div>`;
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
  const renderEvent = (event) => `<li class="event-item"><div class="event-item-top"><span class="event-headline">${escapeHtml(text(event.headline, "未命名事件"))}</span><span class="mini-badge">${escapeHtml(eventTierLabel(event.highest_source_tier))}</span></div><div class="event-meta">${escapeHtml(text(event.summary, "暂无摘要"))} · ${escapeHtml(event.recommended_action === "run_drift" ? "建议检查投资逻辑" : "仅作辅助观察")}</div></li>`;
  return `<div class="detail-section"><div class="detail-section-head"><h3>事件雷达</h3><span class="data-badge" data-status="${escapeHtml(radar.source_status || "unknown")}">${escapeHtml(label("eventState", radar.state))}</span></div><div class="detail-grid"><div class="detail-field"><div class="detail-field-label">投资逻辑相关性</div><div class="detail-field-value">${escapeHtml(radar.thesis_relevant ? "已标记为投资逻辑相关" : "未标记为投资逻辑相关")}</div></div><div class="detail-field"><div class="detail-field-label">数据状态</div><div class="detail-field-value">${escapeHtml(dataLabel(radar.source_status))} · 截止 ${escapeHtml(formatDate(radar.data_cutoff))}</div></div></div>${formal.length ? `<div class="event-block"><div class="holding-detail-label" style="margin:15px 0 7px">重要事件</div><ul class="event-list">${formal.map(renderEvent).join("")}</ul></div>` : ""}${discussion.length ? `<div class="event-block"><div class="holding-detail-label" style="margin:15px 0 7px">市场讨论 / 背景</div><ul class="event-list">${discussion.map(renderEvent).join("")}</ul></div>` : ""}${!formal.length && !discussion.length ? `<p class="detail-copy" style="margin-top:12px">暂无可展示事件；来源不可用时只显示未知，不推断为正常。</p>` : ""}</div>`;
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
    const snapshot = originalThesisFor(record);
    return `<div class="detail-section"><div class="detail-section-head"><h3>原始买入逻辑</h3><span class="mini-badge">当前持仓周期</span></div><div class="thesis-banner">冻结基线与当前持仓周期绑定，不会因后续报告改写而被替换。</div><div class="detail-grid"><div class="detail-field"><div class="detail-field-label">投资逻辑状态</div><div class="detail-field-value">${escapeHtml(thesisLabel(tracking.thesis_status))} · ${escapeHtml(label("drift", drift.direction))}</div></div><div class="detail-field"><div class="detail-field-label">健康度</div><div class="detail-field-value">${tracking.health_score == null ? "—" : escapeHtml(`${tracking.health_score}/10`)}</div></div><div class="detail-field"><div class="detail-field-label">买入日期</div><div class="detail-field-value">${escapeHtml(formatDate(tracking.buy_date))}</div></div><div class="detail-field"><div class="detail-field-label">下一次复核</div><div class="detail-field-value">${escapeHtml(formatDate(tracking.next_review_date))}</div></div></div>${snapshot ? renderFrozenThesis(snapshot) : "<div class=\"source-line\">当前周期冻结投资逻辑未加载。</div>"}<div class="source-line">当前持仓周期已绑定原始买入逻辑<br />最近漂移检查：${escapeHtml(formatDateTime(drift.last_checked))}</div><a class="drawer-report-link" href="${escapeHtml(reportHref(tracking.thesis_report_path || record.canonical_report))}" target="_blank" rel="noreferrer">查看最新研究 ↗</a></div>`;
  }
  const light = record.light_thesis_signal || {};
  const lightText = light.status === "current" ? lightThesisSignalLabel(light.signal) : light.status === "stale" ? "已有结果已过期" : "尚无轻量检查结果";
  return `<div class="detail-section"><div class="detail-section-head"><h3>当前投资逻辑</h3><span class="mini-badge">${escapeHtml(driftScanLabel(record))}</span></div><p class="detail-copy">当前为${escapeHtml(label("lifecycle", lifecycleOf(record)))}；正式漂移复核与日常轻量信号分开记录。</p><div class="detail-grid" style="margin-top:14px"><div class="detail-field"><div class="detail-field-label">正式投资逻辑复核</div><div class="detail-field-value">${escapeHtml(driftScanLabel(record))}</div></div><div class="detail-field"><div class="detail-field-label">轻量投资逻辑信号</div><div class="detail-field-value">${escapeHtml(lightText)}</div></div></div><div class="source-line">Canonical 主报告已关联<br />最近正式复核：${escapeHtml(formatDateTime(drift.last_checked))}</div><a class="drawer-report-link" href="${escapeHtml(reportHref(record.canonical_report))}" target="_blank" rel="noreferrer">打开主报告 ↗</a></div>`;
}

function lightThesisSignalLabel(signal) {
  return {
    improved: "改善",
    unchanged: "无明显变化",
    weakened: "走弱",
    insufficient_evidence: "证据不足",
  }[signal] || "尚无结果";
}

function renderLightThesisReason(record) {
  const thesis = record?.light_thesis_signal;
  if (!thesis || thesis.status !== "current") return "";
  const summary = shortText(String(thesis.summary || "").trim(), 600);
  const evidence = Array.isArray(thesis.material_evidence) ? thesis.material_evidence.slice(0, 4) : [];
  const evidenceHtml = evidence.length
    ? `<ul class="event-list">${evidence.map((item) => `<li class="event-item"><div class="event-item-top"><span class="event-headline">${escapeHtml(shortText(item.summary || "证据", 280))}</span>${item.date ? `<span class="mini-badge">${escapeHtml(formatDate(item.date))}</span>` : ""}</div><div class="event-meta">来源：${escapeHtml(item.source || "未注明")}</div></li>`).join("")}</ul>`
    : `<div class="source-line">本次没有单独列出关键证据。</div>`;
  const provenance = [thesis.model, thesis.provider, thesis.provenance].filter(Boolean).join(" · ");
  return `<div class="detail-section light-thesis-reason"><div class="detail-section-head"><h3>轻量投资逻辑</h3><span class="data-badge" data-status="${escapeHtml(thesis.signal || "unknown")}">${escapeHtml(lightThesisSignalLabel(thesis.signal))}</span></div><div class="detail-field"><div class="detail-field-label">为什么</div><div class="detail-field-value">${escapeHtml(summary || "本次结果未提供简短原因说明。")}</div></div><div class="holding-detail-label" style="margin:15px 0 7px">关键证据</div>${evidenceHtml}<div class="source-line">${thesis.checked_at ? `检查时间：${escapeHtml(formatDateTime(thesis.checked_at))}<br />` : ""}${provenance ? `模型来源：${escapeHtml(provenance)}<br />` : ""}性质：轻量检查，不等于正式 Thesis Drift</div></div>`;
}

function renderCurrentJudgment(record) {
  const quote = quoteFor(record);
  const sentiment = sentimentLabel(record);
  const radar = record.event_radar || {};
  return `<div class="detail-section"><div class="detail-section-head"><h3>当前判断</h3><span class="lifecycle-badge" data-lifecycle="${escapeHtml(lifecycleOf(record))}">${escapeHtml(label("lifecycle", lifecycleOf(record)))}</span></div><div class="detail-grid"><div class="detail-field"><div class="detail-field-label">当前价格</div><div class="detail-field-value large">${escapeHtml(formatPrice(quote))}</div></div><div class="detail-field"><div class="detail-field-label">下一步</div><div class="detail-field-value large">${escapeHtml(actionLabel(record))}</div></div><div class="detail-field"><div class="detail-field-label">研究判断</div><div class="detail-field-value">${escapeHtml(text(record.action, "观察"))}</div></div><div class="detail-field"><div class="detail-field-label">Checklist</div><div class="detail-field-value">${escapeHtml(checklistDisplayLabel(record?.checklist?.status))}</div></div><div class="detail-field"><div class="detail-field-label">情绪辅助</div><div class="detail-field-value">${escapeHtml(sentiment.stateText)}${sentiment.score == null ? "" : ` · ${formatNumber(sentiment.score, 1)}`}</div></div><div class="detail-field"><div class="detail-field-label">最近事件</div><div class="detail-field-value">${escapeHtml(label("eventState", radar.state))}${radar.thesis_relevant ? " · 投资逻辑相关" : ""}</div></div><div class="detail-field"><div class="detail-field-label">数据范围</div><div class="detail-field-value">${escapeHtml(record.realtime_scope === "research_only" ? "仅研究" : "A/H 实时支持")}</div></div></div>${record.conclusion_summary ? `<p class="source-line">${escapeHtml(record.conclusion_summary)}</p>` : ""}</div>`;
}

function decisionContextValues(record) {
  const guidance = guidanceFor(record);
  return {
    lifecycle: label("lifecycle", lifecycleOf(record)),
    blocker: guidance.blocker_text,
    nextStep: guidance.next_action_text,
    skill: recommendedSkillText(record),
    reason: guidance.recommended_skill_reason,
    completion: guidance.completion_target,
    today: guidance.requires_user_action ? "是" : "否，系统继续观察",
  };
}

function renderDecisionContext(record) {
  const context = decisionContextValues(record);
  const fields = [
    { name: "当前阶段", value: context.lifecycle },
    { name: "当前卡点", value: context.blocker },
    { name: "下一步", value: context.nextStep },
    { name: "建议 Skill", value: renderRecommendedSkill(record), html: true },
    { name: "为什么", value: context.reason },
    { name: "完成后", value: context.completion },
    { name: "今天需要处理", value: context.today },
  ];
  return `<div class="detail-section decision-context"><div class="detail-section-head"><h3>现在该做什么</h3><span class="mini-badge">确定性状态导航</span></div><div class="decision-context-grid">${fields.map(({ name, value, html = false }) => `<div class="decision-context-item"><div class="detail-field-label">${escapeHtml(name)}</div><div class="detail-field-value">${html ? value : escapeHtml(value)}</div></div>`).join("")}</div></div>`;
}

function renderDetail(record) {
  const ruleCount = rulesFor(record).length;
  els.drawerKicker.textContent = `${record.market || "待识别"} · ${record.ticker}`;
  els.drawerTitle.textContent = text(record.company);
  els.drawerSubtitle.textContent = `${label("lifecycle", lifecycleOf(record))} · ${actionLabel(record)} · ${ruleCount} 条已保存规则`;
  els.drawerContent.innerHTML = [
    renderDecisionContext(record),
    renderDispositionControls(record),
    renderCurrentJudgment(record),
    renderLightThesisReason(record),
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

function openDispositionDialog(record, selectedDisposition) {
  const manual = record?.manual_disposition || {};
  if (!state.dispositionAccess || !manual.allowed_options?.includes(selectedDisposition)) return;
  state.pendingDisposition = {
    ticker: record.ticker,
    selected_disposition: selectedDisposition,
    disposition_target_fingerprint: manual.disposition_target_fingerprint,
  };
  els.dispositionDialogTitle.textContent = `确认：${DISPOSITION_LABELS[selectedDisposition] || selectedDisposition}`;
  els.dispositionDialogCopy.textContent = DISPOSITION_CONFIRM_COPY[selectedDisposition] || "确认记录这项人工处置。";
  els.dispositionDialog.showModal();
}

async function submitDisposition() {
  const pending = state.pendingDisposition;
  if (!pending) return;
  els.dispositionConfirm.disabled = true;
  try {
    const response = await fetch("/api/investment-dispositions", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pending),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `保存失败（${response.status}）`);
    const overlay = payload.resolved_current_task;
    const current = currentRecord(pending.ticker);
    if (current && overlay && dispositionOverlayMatches(current, overlay)) {
      state.companyState.set(pending.ticker, { ...current, ...overlay });
    } else {
      await loadData({ silent: true });
    }
    els.dispositionDialog.close();
    state.pendingDisposition = null;
    renderAll();
    const updated = currentRecord(pending.ticker);
    if (updated) renderDetail(updated);
    toast(payload.status === "noop" ? "该处置已记录，无需重复保存" : "人工处置已安全记录");
  } catch (error) {
    toast(error.message);
  } finally {
    els.dispositionConfirm.disabled = false;
  }
}

async function loadJson(path) {
  const separator = path.includes("?") ? "&" : "?";
  const requestVersion = `${Date.now()}-${++dataRequestSequence}`;
  const response = await fetch(`${path}${separator}v=${requestVersion}`, {
    cache: "no-store",
    headers: { "Cache-Control": "no-cache" },
  });
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

async function loadDispositionAuthority() {
  try {
    const response = await fetch(`/api/investment-dispositions?v=${Date.now()}`, {
      cache: "no-store",
      headers: { "Cache-Control": "no-cache" },
    });
    if (response.status === 403 || response.status === 404) return { authorized: false, payload: null };
    if (!response.ok) throw new Error(`investment dispositions (${response.status})`);
    return { authorized: true, payload: await response.json() };
  } catch {
    return { authorized: false, payload: null };
  }
}

function dispositionOverlayMatches(current, overlay) {
  const fingerprint = current?.manual_disposition?.disposition_target_fingerprint;
  return Boolean(fingerprint && fingerprint === overlay?.manual_disposition?.disposition_target_fingerprint);
}

function applyDispositionAuthority(result) {
  state.dispositionAccess = result.authorized === true;
  state.dispositionAuthority = result.payload;
  for (const overlay of result.payload?.resolved_companies || []) {
    const current = state.companyState.get(overlay.ticker);
    if (!current || !dispositionOverlayMatches(current, overlay)) continue;
    state.companyState.set(overlay.ticker, { ...current, ...overlay });
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
  const loadSequence = ++state.loadSequence;
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
  const dispositionResult = await loadDispositionAuthority();
  if (loadSequence !== state.loadSequence) return false;
  if (!payload.companyState || !Array.isArray(payload.companyState.companies)) throw new Error("公司状态数据不可用");
  state.board = payload.board;
  state.companyState = indexByTicker(payload.companyState.companies);
  applyDispositionAuthority(dispositionResult);
  state.rulePackages = indexByTicker(payload.rules?.companies);
  state.events = indexByTicker(payload.events?.companies);
  state.technical = indexByTicker(payload.technical?.companies);
  state.sentiment = indexByTicker(payload.sentiment?.companies);
  state.tracking = normalizeTracking(payload.tracking);
  state.originalTheses = payload.originalTheses || { schema_version: 2, cycles: {}, active_position_ids: {} };
  state.quotes = indexByTicker(payload.quotes?.quotes);
  state.quoteMeta = payload.quotes;
  state.sentimentMeta = { ...(payload.sentiment || {}), ...(payload.sentimentStatus || {}) };
  const scanPayload = payload.opportunityScans && Array.isArray(payload.opportunityScans.scans)
    ? payload.opportunityScans
    : { schema_version: 1, status: "unavailable", scans: [] };
  const scanStatus = payload.opportunityScanStatus || {};
  state.opportunityScanMeta = {
    ...scanPayload,
    ...scanStatus,
    generated_at: scanStatus.scan_generated_at || scanPayload.generated_at || scanStatus.last_success_scan_generated_at || scanStatus.last_success_at || null,
    scan_generated_at: scanStatus.scan_generated_at || scanPayload.generated_at || null,
    display_result_generated_at: scanPayload.generated_at || scanStatus.last_success_scan_generated_at || scanStatus.last_success_at || null,
    display_scan_count: scanPayload.scan_count ?? scanStatus.last_success_scan_count ?? null,
    display_expected_scan_count: scanPayload.expected_scan_count ?? scanStatus.last_success_expected_scan_count ?? null,
    display_current_opportunity_count: scanPayload.current_opportunity_count ?? scanStatus.last_success_current_opportunity_count ?? null,
    display_near_opportunity_count: scanPayload.near_opportunity_count ?? scanStatus.last_success_near_opportunity_count ?? null,
    scan_count: scanStatus.scan_count ?? scanPayload.scan_count,
    expected_scan_count: scanStatus.expected_scan_count ?? scanPayload.expected_scan_count,
    current_opportunity_count: scanStatus.current_opportunity_count ?? scanPayload.current_opportunity_count,
    near_opportunity_count: scanStatus.near_opportunity_count ?? scanPayload.near_opportunity_count,
  };
  state.opportunityScans = indexByTicker(state.opportunityScanMeta.scans);
  state.loadedAt = new Date().toISOString();
  populateDynamicFilters();
  renderAll();
  syncWorkspaceFromLocation();
  return true;
}

function shouldRefreshOnPageResume(now = Date.now()) {
  if (!state.loadedAt) return false;
  const loadedAt = Date.parse(state.loadedAt);
  return Number.isFinite(loadedAt) && now - loadedAt >= PAGE_RESUME_REFRESH_AGE_MS;
}

async function refreshDataOnPageResume({ force = false } = {}) {
  if (document.visibilityState !== "visible") return false;
  if (!force && !shouldRefreshOnPageResume()) return false;
  try {
    return await loadData({ silent: true });
  } catch {
    toast("自动重新读取失败，当前仍显示上次读取的数据；可点击重新读取。");
    return false;
  }
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
  state.actionStatus = opportunity === "attention" ? "attention" : "all";
  state.opportunity = opportunity === "attention" ? "all" : opportunity;
  state.quickFilter = opportunity === "attention" ? "attention" : "all";
  state.page = 1;
  els.lifecycle.value = lifecycle;
  els.actionStatus.value = state.actionStatus;
  els.opportunity.value = state.opportunity;
  const targetWorkspace = lifecycle !== "all" ? "watchlist" : opportunity === "attention" ? "attention" : "watchlist";
  setWorkspace(targetWorkspace);
  if (targetWorkspace === "watchlist") {
    renderWatchlist();
    document.querySelector("#watchlist-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function resetFilterState({ preserveSearch = false } = {}) {
  if (!preserveSearch) state.search = "";
  state.market = "all";
  state.lifecycle = "all";
  state.actionStatus = "all";
  state.skill = "all";
  state.lightThesis = "all";
  state.formalDrift = "all";
  state.blocker = "all";
  state.checklist = "all";
  state.priceNear = false;
  state.opportunity = "all";
  state.sort = "attention";
  state.quickFilter = "all";
  state.page = 1;
}

function syncFilterControls() {
  els.search.value = state.search;
  els.market.value = state.market;
  els.lifecycle.value = state.lifecycle;
  els.actionStatus.value = state.actionStatus;
  els.skill.value = state.skill;
  els.lightThesis.value = state.lightThesis;
  els.formalDrift.value = state.formalDrift;
  els.blocker.value = state.blocker;
  els.checklist.value = state.checklist;
  els.opportunity.value = state.opportunity;
  els.sort.value = state.sort;
}

function applyQuickFilter(value) {
  if (value === "all") {
    resetFilterState();
  } else {
    resetFilterState({ preserveSearch: true });
    state.quickFilter = value;
    if (["attention", "skill", "manual", "observe"].includes(value)) state.actionStatus = value;
    if (value === "light-improved") state.lightThesis = "improved";
    if (value === "light-weakened") state.lightThesis = "weakened";
    if (value === "price-near") state.priceNear = true;
  }
  syncFilterControls();
  renderWatchlist();
}

function clearSingleFilter(key) {
  if (key === "quickFilter") {
    const value = state.quickFilter;
    if (["attention", "skill", "manual", "observe"].includes(value)) state.actionStatus = "all";
    if (["light-improved", "light-weakened"].includes(value)) state.lightThesis = "all";
    if (value === "price-near") state.priceNear = false;
    state.quickFilter = "all";
  } else if (key === "search") {
    state.search = "";
  } else if (key === "priceNear") {
    state.priceNear = false;
  } else if (key === "sort") {
    state.sort = "attention";
  } else if (Object.hasOwn(state, key)) {
    state[key] = "all";
  }
  state.page = 1;
  syncFilterControls();
  renderWatchlist();
}

function bindEvents() {
  els.workspaceNav?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-workspace]");
    if (button) setWorkspace(button.dataset.workspace);
  });
  window.addEventListener("hashchange", syncWorkspaceFromLocation);
  window.addEventListener("popstate", syncWorkspaceFromLocation);
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) void refreshDataOnPageResume({ force: true });
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void refreshDataOnPageResume();
  });
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
  for (const [select, key] of [
    [els.market, "market"], [els.lifecycle, "lifecycle"], [els.actionStatus, "actionStatus"],
    [els.skill, "skill"], [els.lightThesis, "lightThesis"], [els.formalDrift, "formalDrift"],
    [els.blocker, "blocker"], [els.checklist, "checklist"], [els.opportunity, "opportunity"], [els.sort, "sort"],
  ]) {
    select.addEventListener("change", () => {
      state[key] = select.value;
      state.quickFilter = "all";
      state.page = 1;
      renderWatchlist();
    });
  }
  els.quickFilters.addEventListener("click", (event) => {
    const button = event.target.closest("[data-quick-filter]");
    if (button) applyQuickFilter(button.dataset.quickFilter);
  });
  els.activeFilterChips.addEventListener("click", (event) => {
    const button = event.target.closest("[data-clear-filter]");
    if (button) clearSingleFilter(button.dataset.clearFilter);
  });
  els.clearFilters.addEventListener("click", () => {
    resetFilterState();
    syncFilterControls();
    renderWatchlist();
  });
  els.loadMore.addEventListener("click", () => { state.page += 1; renderWatchlist(); });
  els.drawerClose.addEventListener("click", closeDetail);
  els.backdrop.addEventListener("click", closeDetail);
  els.drawerContent.addEventListener("click", (event) => {
    const button = event.target.closest("[data-disposition]");
    const record = state.selectedTicker ? currentRecord(state.selectedTicker) : null;
    if (button && record) openDispositionDialog(record, button.dataset.disposition);
  });
  els.dispositionCancel.addEventListener("click", () => {
    state.pendingDisposition = null;
    els.dispositionDialog.close();
  });
  els.dispositionConfirm.addEventListener("click", submitDisposition);
  els.dispositionDialog.addEventListener("cancel", () => { state.pendingDisposition = null; });
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
