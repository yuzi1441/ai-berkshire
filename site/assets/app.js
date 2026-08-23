import {
  currentExecutionState,
  currentActionKind,
  executionFilterKey,
  fallbackActionKind,
  parseReportPriceBand,
  primaryJudgmentForItem,
  referenceExecutionState,
} from "./action-classifier.mjs";

const repositoryUrl = "https://github.com/yuzi1441/ai-berkshire/blob/main/";
const TRACKING_HIDDEN_STORAGE_KEY = "ai-berkshire.hidden-post-buy-tracking.v1";
const SNAPSHOT_INTERVAL_MS = 300_000;
const ROW_PAGE_SIZE = 50;
const A_SHARE_INDEX_WATCH = [
  { index_id: "sse", ticker: "000001.SH", symbol: "sh000001", company: "上证指数" },
  { index_id: "szse", ticker: "399001.SZ", symbol: "sz399001", company: "深证成指" },
  { index_id: "chinext", ticker: "399006.SZ", symbol: "sz399006", company: "创业板指" },
  { index_id: "star50", ticker: "000688.SH", symbol: "sh000688", company: "科创50" },
  { index_id: "hs300", ticker: "000300.SH", symbol: "sh000300", company: "沪深300" },
  { index_id: "csi500", ticker: "000905.SH", symbol: "sh000905", company: "中证500" },
  { index_id: "csi1000", ticker: "000852.SH", symbol: "sh000852", company: "中证1000" },
];

const state = {
  decisions: [],
  details: new Map(),
  detailRequests: new Map(),
  detailErrors: new Map(),
  intradayTechnical: new Map(),
  deepReviews: new Map(),
  deepReviewLoadingTicker: null,
  sentimentSnapshot: null,
  sentiments: new Map(),
  sentimentStatus: null,
  sentimentError: null,
  quotes: new Map(),
  indices: new Map(),
  annualReportDates: null,
  automationStatus: null,
  selectedKey: null,
  generationId: null,
  view: "decision",
  market: "all",
  action: "all",
  referenceAction: "all",
  trackingFilter: "all",
  hiddenTrackingKeys: new Set(),
  sort: "execution",
  detailTab: "technical",
  quoteMode: "idle", // snapshot | idle | error
  quoteUpdatedAt: null,
  liveTimer: null,
  snapshotTimer: null,
  focusIndex: -1,
  page: 1,
};

function isAdminOrigin() {
  return window.location.protocol === "https:" && window.location.port === "8443";
}

const els = {
  rows: document.querySelector("#decision-rows"),
  decisionTable: document.querySelector("#decision-table"),
  decisionHead: document.querySelector("#decision-head"),
  summary: document.querySelector("#summary"),
  sentimentAlert: document.querySelector("#sentiment-alert"),
  attentionPanel: document.querySelector("#attention-panel"),
  attentionToggleMeta: document.querySelector("#attention-toggle-meta"),
  attentionToggleState: document.querySelector("#attention-toggle-state"),
  attentionMeta: document.querySelector("#attention-meta"),
  attentionList: document.querySelector("#attention-list"),
  status: document.querySelector("#data-status"),
  companyFilter: document.querySelector("#company-filter"),
  sortSelect: document.querySelector("#sort-select"),
  clearFilters: document.querySelector("#clear-filters"),
  marketChips: document.querySelector("#market-chips"),
  actionChips: document.querySelector("#action-chips"),
  referenceActionChips: document.querySelector("#reference-action-chips"),
  viewTabs: document.querySelector("#view-tabs"),
  trackingFilterRow: document.querySelector("#tracking-filter-row"),
  trackingCount: document.querySelector("#tracking-count"),
  restoreTracking: document.querySelector("#restore-tracking"),
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
  loadMoreRows: document.querySelector("#load-more-rows"),
  indexCards: document.querySelector("#index-cards"),
  indexBandMeta: document.querySelector("#index-band-meta"),
  annualPanelMeta: document.querySelector("#annual-panel-meta"),
  annualDateContent: document.querySelector("#annual-date-content"),
  automationPanelMeta: document.querySelector("#automation-panel-meta"),
  automationStatusContent: document.querySelector("#automation-status-content"),
};

function trackingForItem(item) {
  const tracking = item?.post_buy_tracking;
  if (!tracking || tracking.status === "not_tracked") return null;
  if (state.hiddenTrackingKeys.has(itemKey(item))) return null;
  return tracking;
}

function loadHiddenTrackingKeys() {
  try {
    const stored = JSON.parse(localStorage.getItem(TRACKING_HIDDEN_STORAGE_KEY) || "[]");
    return new Set(Array.isArray(stored) ? stored.filter((value) => typeof value === "string") : []);
  } catch {
    return new Set();
  }
}

function saveHiddenTrackingKeys() {
  try {
    localStorage.setItem(TRACKING_HIDDEN_STORAGE_KEY, JSON.stringify([...state.hiddenTrackingKeys]));
  } catch {
    showToast("浏览器不允许保存隐藏状态");
  }
}

function updateTrackingControls() {
  const visibleCount = state.decisions.filter((item) => trackingForItem(item)).length;
  if (els.trackingCount) els.trackingCount.textContent = String(visibleCount);
  if (els.restoreTracking) els.restoreTracking.hidden = state.hiddenTrackingKeys.size === 0;
}

function hideTrackingForCurrentBrowser(item) {
  const key = itemKey(item);
  if (!window.confirm(`确认从本机看板隐藏 ${item.company} 的买入后跟踪记录？\n\n源数据不会被删除；以后可点击“恢复已隐藏”。`)) return;
  state.hiddenTrackingKeys.add(key);
  saveHiddenTrackingKeys();
  closeDetail();
  updateTrackingControls();
  showToast("已从本机看板隐藏，源数据未删除");
}

function restoreHiddenTracking() {
  if (!state.hiddenTrackingKeys.size) return;
  state.hiddenTrackingKeys.clear();
  saveHiddenTrackingKeys();
  updateTrackingControls();
  renderAll();
  showToast("已恢复本机隐藏的跟踪记录");
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

function numericSentimentScore(score) {
  if (score === null || score === undefined || score === "") return null;
  const value = Number(score);
  return Number.isFinite(value) ? value : null;
}

function sentimentTone(score) {
  const value = numericSentimentScore(score);
  if (value === null) return "sentiment-muted";
  if (value >= 70) return "sentiment-positive";
  if (value <= 45) return "sentiment-negative";
  return "sentiment-neutral";
}

function sentimentScoreText(score) {
  const value = numericSentimentScore(score);
  return value === null ? "—" : value.toFixed(1);
}

function sentimentStateText(sentiment) {
  return sentiment?.state || "无有效分数";
}

function sentimentProgressLabel() {
  if (state.sentimentSnapshot?.status !== "partial") return null;
  const stage = state.sentimentSnapshot?.progress?.stage;
  return {
    industry_mapping: "数据准备中",
    company_news: "个股新闻抓取中",
    industry_news: "行业新闻抓取中",
    primary_scoring: "主模型评分中",
    review_scoring: "复核模型评分中",
    interrupted: "本次中断，保留已完成结果",
  }[stage] || null;
}

function sentimentPendingLabel(sentiment) {
  const progressLabel = sentimentProgressLabel();
  if (!progressLabel) return null;
  const coverage = sentiment?.coverage || {};
  const hasScoredCompanyOrIndustry = coverage.company || coverage.industry;
  if (
    sentiment?.status === "pending"
    || (sentiment?.status === "context_only" && !hasScoredCompanyOrIndustry)
  ) {
    return progressLabel;
  }
  return null;
}

function sentimentDisplayScore(sentiment) {
  return sentimentPendingLabel(sentiment) ? null : sentiment?.score_0_100;
}

function sentimentDisplayState(sentiment) {
  return sentimentPendingLabel(sentiment) || sentimentStateText(sentiment);
}

function sentimentRecencyText(news) {
  return news?.recency_state || news?.state || "暂无新闻时效信息";
}

function updateSentimentAlert() {
  if (!els.sentimentAlert) return;
  const status = state.sentimentStatus;
  const partial = status?.status === "partial";
  const failed = status?.status === "error";
  if (!partial && !failed) {
    els.sentimentAlert.hidden = true;
    els.sentimentAlert.textContent = "";
    delete els.sentimentAlert.dataset.status;
    return;
  }
  els.sentimentAlert.hidden = false;
  els.sentimentAlert.dataset.status = status.status;
  if (failed) {
    els.sentimentAlert.textContent = `情绪数据更新失败：${status.error || "模型未完成复核"}。当前显示上一份成功快照。`;
    return;
  }
  const progressStage = status.progress?.stage;
  const inProgressStages = new Set([
    "industry_mapping",
    "company_news",
    "industry_news",
    "primary_scoring",
    "review_scoring",
  ]);
  if (inProgressStages.has(progressStage)) {
    const progress = status.progress || {};
    const companyPart = `${progress.company_news_completed || 0}/${progress.company_news_total || 0}`;
    const industryPart = `${progress.industry_news_completed || 0}/${progress.industry_news_total || 0}`;
    els.sentimentAlert.textContent = `情绪数据更新中：${progress.stage_label || "正在处理"}；个股 ${companyPart}，行业 ${industryPart}。已保存阶段性结果，未完成层暂不计入。`;
    return;
  }
  const skipped = Array.isArray(status.skipped_articles) ? status.skipped_articles : [];
  const skippedCount = Number(status.skipped_count || skipped.length || 0);
  const labels = skipped
    .slice(0, 4)
    .map((item) => `${item.ticker || item.id || "未知标的"}（${item.provider === "review" ? "复核模型" : "主模型"}）`)
    .join("、");
  const more = skippedCount > 4 ? `等${skippedCount}项` : "";
  const detail = labels ? `跳过：${labels}${more}。` : "部分来源异常，但成功结果已保留。";
  els.sentimentAlert.textContent = `情绪数据部分更新：${skippedCount} 条新闻已重试仍失败并跳过，其余成功结果已写入。${detail}`;
}

function renderSentimentBadge(sentiment, label = "综合") {
  const badge = document.createElement("span");
  const pendingLabel = sentimentPendingLabel(sentiment);
  const score = pendingLabel ? null : sentiment?.score_0_100;
  badge.className = `sentiment-badge ${sentimentTone(score)}`;
  const displayLabel = pendingLabel || (sentiment?.status === "context_only" ? "上下文" : label);
  badge.textContent = `${displayLabel} ${sentimentScoreText(score)}`;
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
  stateLine.textContent = sentimentDisplayState(combined);
  cell.append(stateLine);
  const industry = record?.industry_sentiment || record?.industry_detail;
  const market = state.sentimentSnapshot?.market_sentiment?.[item.market];
  const layers = document.createElement("div");
  layers.className = "sentiment-layers";
  layers.textContent = `个股 ${sentimentScoreText(sentimentDisplayScore(record?.news_sentiment))} · 行业 ${sentimentScoreText(sentimentDisplayScore(industry))} · 市场 ${sentimentScoreText(sentimentDisplayScore(market))}`;
  layers.title = "个股新闻 · 行业新闻 · 市场情绪；缺失层显示为 —，不会自动放大其他层权重";
  cell.append(layers);
  const freshness = document.createElement("div");
  freshness.className = "sentiment-freshness";
  freshness.textContent = state.sentimentStatus?.status === "error"
    ? `更新失败 · 上次快照 ${state.sentimentSnapshot?.data_cutoff || "未知"}`
    : state.sentimentStatus?.status === "partial"
      ? `部分更新 · 跳过 ${state.sentimentStatus?.skipped_count || 0} 条`
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
  const count = checklist.passed_count == null ? "待复核" : `${checklist.passed_count}/${checklist.total_gates || 6}`;
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

function renderPrimaryJudgment(item, { compact = true } = {}) {
  const judgment = primaryJudgmentForItem(item);
  if (!judgment) return null;
  const wrap = document.createElement("div");
  wrap.className = `primary-judgment${compact ? " primary-judgment-compact" : ""}`;

  const eyebrow = document.createElement("div");
  eyebrow.className = "primary-judgment-eyebrow";
  eyebrow.textContent = "主报告判断";
  const label = document.createElement("strong");
  label.className = "primary-judgment-label";
  label.textContent = judgment.label;
  const emptyAction = document.createElement("p");
  emptyAction.className = "primary-judgment-action";
  emptyAction.textContent = `空仓者：${judgment.empty_position_action}`;
  const trigger = document.createElement("p");
  trigger.className = "primary-judgment-trigger";
  trigger.textContent = `触发条件：${judgment.trigger_condition}`;
  const summary = document.createElement("p");
  summary.className = "primary-judgment-summary";
  summary.textContent = judgment.summary;
  wrap.append(eyebrow, label, emptyAction, trigger, summary);

  if (judgment.human_reviewed === true) {
    const reviewed = document.createElement("p");
    reviewed.className = "primary-judgment-consensus";
    reviewed.textContent = "已人工核对主报告原文 · 主报告结论优先于模型标签分歧";
    wrap.append(reviewed);
  } else if (judgment.model_consensus === true) {
    const consensus = document.createElement("p");
    consensus.className = "primary-judgment-consensus";
    const modelNames = Object.values(judgment.models || {}).filter(Boolean).join(" + ");
    consensus.textContent = `双模型一致${modelNames ? ` · ${modelNames}` : ""}`;
    wrap.append(consensus);
  } else if (judgment.screening_consensus === true) {
    const consensus = document.createElement("p");
    consensus.className = "primary-judgment-consensus";
    consensus.textContent = "双模型均不支持当前直接买入 · 细分口径按保守交集展示";
    wrap.append(consensus);
  }

  if (judgment.report_field_conflict) {
    const conflict = document.createElement("p");
    conflict.className = "primary-judgment-conflict";
    conflict.textContent = `字段冲突：${judgment.conflict_note || "粗粒度字段与报告正文不一致"}`;
    wrap.append(conflict);
  }
  if (!compact) {
    const source = document.createElement("p");
    source.className = "primary-judgment-source";
    source.textContent = `判断依据：${judgment.source_basis}`;
    wrap.append(source);
    if (Array.isArray(judgment.evidence) && judgment.evidence.length) {
      const evidenceTitle = document.createElement("p");
      evidenceTitle.className = "primary-judgment-evidence-title";
      evidenceTitle.textContent = "报告原文证据";
      const evidenceList = document.createElement("ul");
      evidenceList.className = "primary-judgment-evidence";
      for (const item of judgment.evidence) {
        const li = document.createElement("li");
        li.textContent = `L${item.line_start}${item.line_end !== item.line_start ? `–${item.line_end}` : ""}：${item.quote}`;
        evidenceList.append(li);
      }
      wrap.append(evidenceTitle, evidenceList);
    }
  }
  return wrap;
}

function renderExecutionState(item, quote, { compact = true } = {}) {
  const execution = currentExecutionState(item, quote, reportFallbackKind(item));
  const wrap = document.createElement("div");
  const tone = {
    actionable: "inside_entry",
    trial: "trial",
    validation: "unavailable",
    wait_price: "above_entry",
    wait_event: "unavailable",
    hold: "unavailable",
    no: "unavailable",
    paused: "unavailable",
    review: "unavailable",
    research: "unavailable",
  }[execution.key] || "unavailable";
  wrap.className = `primary-judgment-aux primary-judgment-aux-${tone}`;
  const label = document.createElement("strong");
  label.textContent = execution.label;
  const detail = document.createElement("p");
  detail.textContent = execution.detail;
  wrap.append(label, detail);
  if (execution.key === "paused" && execution.referenceExecution) {
    const reference = document.createElement("p");
    reference.className = "primary-judgment-aux-note";
    reference.textContent = `非实时参考分区：${execution.referenceExecution.label}。按最近行情快照与有效人工结论归类，仅供盘前/盘后研究，不是当前可下单信号。`;
    wrap.append(reference);
    if (execution.referenceExecution.referenceCaveat) {
      const caveat = document.createElement("p");
      caveat.className = "primary-judgment-aux-note";
      caveat.textContent = `参考限制：${execution.referenceExecution.referenceCaveat}`;
      wrap.append(caveat);
    }
  }
  if (execution.policy?.reliability === "conservative") {
    const consensus = document.createElement("p");
    consensus.className = "primary-judgment-aux-note";
    consensus.textContent = "双模型细分口径有分歧；本状态只采用两者对“当前不可直接买入”的安全交集。";
    wrap.append(consensus);
  }
  if (!compact) {
    if (execution.policy?.guard_condition) {
      const guard = document.createElement("p");
      guard.className = "primary-judgment-aux-note";
      guard.textContent = `买入前仍须核对报告红线/保护条件：${execution.policy.guard_condition}`;
      wrap.append(guard);
    }
    const note = document.createElement("p");
    note.className = "primary-judgment-aux-note";
    note.textContent = execution.manualReview
      ? "当前状态来自逐股人工复核；Checklist 硬性否决优先，技术面与情绪面仅作辅助。"
      : "当前可执行状态由主报告动作许可、报告价格档、经营前提和现价共同生成；Checklist、技术面与情绪面不参与该归类。";
    wrap.append(note);
  }
  return wrap;
}

function appendReviewList(card, title, values, className = "") {
  if (!Array.isArray(values) || !values.length) return;
  const section = document.createElement("section");
  section.className = "decision-review-list-block";
  const heading = document.createElement("h4");
  heading.className = "decision-review-list-title";
  heading.textContent = title;
  const list = document.createElement("ul");
  list.className = `decision-review-list ${className}`.trim();
  for (const value of values) {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  }
  section.append(heading, list);
  card.append(section);
}

async function deepReviewRequest(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
    },
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = { error: "服务器返回了无效响应" };
  }
  if (!response.ok) throw new Error(payload.error || `深度复核请求失败（${response.status}）`);
  return payload;
}

async function loadDeepReviews() {
  if (!isAdminOrigin()) return;
  try {
    const payload = await deepReviewRequest("/api/deep-reviews");
    state.deepReviews = new Map(
      (payload.reviews || [])
        .filter((review) => review?.ticker && review?.market === "A股")
        .map((review) => [review.ticker, review]),
    );
  } catch (error) {
    console.warn("deep reviews are unavailable", error);
  }
}

async function startDeepReview(item, button) {
  if (!item?.ticker || item.market !== "A股" || !isAdminOrigin()) return;
  if (state.deepReviewLoadingTicker) {
    showToast("已有深度复核正在进行，请等待完成");
    return;
  }
  state.deepReviewLoadingTicker = item.ticker;
  const previousText = button?.textContent;
  if (button) {
    button.disabled = true;
    button.textContent = "V4 Pro + Luna 复核中…";
  }
  try {
    const payload = await deepReviewRequest("/api/deep-reviews", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: item.ticker }),
    });
    if (payload.review?.ticker) state.deepReviews.set(payload.review.ticker, payload.review);
    state.detailTab = "deep-review";
    openDetail(item);
    showToast(payload.status === "cached" ? "已打开本报告版本的深度复核" : "双模型深度复核已完成");
  } catch (error) {
    showToast(error instanceof Error ? error.message : "深度复核失败");
    if (button) {
      button.disabled = false;
      button.textContent = previousText || "启动深度复核";
    }
  } finally {
    state.deepReviewLoadingTicker = null;
  }
}

function modelAssessmentCard(model, record) {
  const section = document.createElement("section");
  section.className = "deep-review-model";
  const heading = document.createElement("h4");
  heading.textContent = model;
  section.append(heading);
  if (record?.status !== "ready") {
    const error = document.createElement("p");
    error.className = "decision-review-error";
    error.textContent = `本模型未完成：${record?.error || "结果缺失"}`;
    section.append(error);
    return section;
  }
  const assessment = record.assessment || {};
  const summary = document.createElement("dl");
  summary.className = "technical-summary decision-review-summary";
  const rows = [
    ["机会判断", assessment.opportunity_state || "待复核"],
    ["置信度", assessment.confidence || "待复核"],
    ["最高推理", record.reasoning?.effective || record.reasoning?.requested || "待复核"],
    ["完成时间", record.generated_at || "待复核"],
  ];
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  section.append(summary);
  const explanation = document.createElement("p");
  explanation.className = "decision-review-explanation";
  explanation.textContent = assessment.opportunity_summary || "未提供机会解释";
  section.append(explanation);
  if (assessment.why_now) {
    const whyNow = document.createElement("p");
    whyNow.className = "deep-review-boundary";
    whyNow.textContent = `为什么是现在：${assessment.why_now}`;
    section.append(whyNow);
  }
  appendReviewList(section, "已满足条件", assessment.satisfied_conditions);
  appendReviewList(section, "尚未满足条件", assessment.unmet_conditions, "warning");
  if (assessment.constraint_override_reason) {
    const override = document.createElement("p");
    override.className = "deep-review-challenge";
    override.textContent = `突破原约束的依据：${assessment.constraint_override_reason}`;
    section.append(override);
  }
  appendReviewList(section, "支持依据", assessment.supporting_evidence);
  appendReviewList(section, "风险或反面证据", assessment.risks_or_counterevidence, "warning");
  appendReviewList(section, "你需要亲自确认", assessment.human_questions, "conflict");
  if (assessment.thesis_challenge) {
    const challenge = document.createElement("p");
    challenge.className = "deep-review-challenge";
    challenge.textContent = `反证挑战：${assessment.thesis_challenge}`;
    section.append(challenge);
  }
  if (assessment.decision_boundary) {
    const boundary = document.createElement("p");
    boundary.className = "deep-review-boundary";
    boundary.textContent = `人工决策边界：${assessment.decision_boundary}`;
    section.append(boundary);
  }
  return section;
}

function renderDeepReviewDetail(item) {
  const review = deepReviewForItem(item);
  const card = document.createElement("section");
  card.className = "card decision-review-detail deep-review-detail";
  const title = document.createElement("h3");
  title.textContent = "双模型深度复核 · V4 Pro + GPT‑5.6 Luna";
  card.append(title);

  const disclaimer = document.createElement("p");
  disclaimer.className = "decision-review-disclaimer";
  disclaimer.textContent = "两份高推理意见并列展示，帮助你理解机会与反证；它们不生成买卖指令，也不会覆盖主报告、行情、技术面、情绪或 Checklist。最终决定由你作出。";
  card.append(disclaimer);

  if (review.status === "missing") {
    const empty = document.createElement("p");
    empty.className = "technical-empty";
    empty.textContent = "尚未进行深度复核。点击后会调用 V4 Pro 和 GPT‑5.6 Luna 的最高推理档；结果只保存在服务器运行目录，不写入公开静态站。";
    const start = document.createElement("button");
    start.type = "button";
    start.className = "btn primary deep-review-start";
    start.textContent = state.deepReviewLoadingTicker === item.ticker ? "V4 Pro + Luna 复核中…" : "启动双模型深度复核";
    start.disabled = state.deepReviewLoadingTicker === item.ticker;
    start.addEventListener("click", () => startDeepReview(item, start));
    card.append(empty, start);
    els.detailBody.append(card);
    return;
  }
  if (review.status === "error" && !Object.keys(review.models || {}).length) {
    const error = document.createElement("p");
    error.className = "decision-review-error";
    error.textContent = `本次深度复核失败：${review.error || "未知错误"}。你仍可从报告与全量扫描判断机会。`;
    card.append(error);
    els.detailBody.append(card);
    return;
  }

  const summary = document.createElement("dl");
  summary.className = "technical-summary decision-review-summary";
  const rows = [
    ["结果状态", review.status || "待复核"],
    ["模型判断关系", review.synthesis?.state_agreement || "待复核"],
    ["结果规则", review.synthesis?.rule || "不形成买卖结论"],
    ["生成时间", review.generated_at || "待复核"],
  ];
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  card.append(summary);

  for (const [model, result] of Object.entries(review.models || {})) {
    card.append(modelAssessmentCard(model, result));
  }

  const source = document.createElement("p");
  source.className = "source-note";
  source.textContent = "复核输入：主报告、价格规则、日线技术面、30分钟技术面、情绪和 Checklist。它们均为模型理解机会的事实，不是自动买卖条件。";
  card.append(source);
  els.detailBody.append(card);
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

function rawSelectedItem() {
  if (!state.selectedKey) return null;
  return state.decisions.find((item) => itemKey(item) === state.selectedKey) || null;
}

function detailLoaded(item) {
  return !item?.detail_id || state.details.has(itemKey(item));
}

function selectedItem() {
  const item = rawSelectedItem();
  if (!item) return null;
  const detail = state.details.get(itemKey(item));
  return detail ? { ...item, ...detail } : item;
}

async function fetchDecisionBoard() {
  let response = await fetch(`./data/decision_board_summary.json?t=${Date.now()}`, { cache: "no-cache" });
  if (!response.ok) response = await fetch(`./data/decision_board.json?t=${Date.now()}`, { cache: "no-cache" });
  if (!response.ok) throw new Error("无法加载 decision_board_summary.json 或 decision_board.json");
  return response.json();
}

async function reloadBoardGeneration() {
  const board = await fetchDecisionBoard();
  state.decisions = board.decisions || [];
  state.generationId = board.generation_id || null;
  state.details.clear();
  state.detailErrors.clear();
  return board;
}

async function loadDecisionDetail(item) {
  if (!item?.detail_path) return item;
  const key = itemKey(item);
  if (state.details.has(key)) return state.details.get(key);
  if (state.detailRequests.has(key)) return state.detailRequests.get(key);
  const request = fetch(item.detail_path, { cache: "no-cache" })
    .then(async (response) => {
      if (!response.ok) throw new Error(`详细研报加载失败（${response.status}）`);
      let detail = await response.json();
      if (
        state.generationId
        && detail?.generation_id
        && detail.generation_id !== state.generationId
      ) {
        await reloadBoardGeneration();
        const latestItem = state.decisions.find(
          (candidate) => candidate.market === item.market && candidate.ticker === item.ticker,
        );
        if (!latestItem?.detail_path) throw new Error("摘要与个股明细代次不一致，请稍后重试");
        const retry = await fetch(`${latestItem.detail_path}?t=${Date.now()}`, { cache: "no-cache" });
        if (!retry.ok) throw new Error(`详细研报重新加载失败（${retry.status}）`);
        detail = await retry.json();
        if (detail?.generation_id !== state.generationId) {
          throw new Error("摘要与个股明细仍处于不同发布代次，请稍后重试");
        }
      }
      state.details.set(key, detail);
      state.detailErrors.delete(key);
      return detail;
    })
    .catch((error) => {
      state.detailErrors.set(key, error instanceof Error ? error.message : "详细研报加载失败");
      throw error;
    })
    .finally(() => {
      state.detailRequests.delete(key);
    });
  state.detailRequests.set(key, request);
  return request;
}

function resetRowPage() {
  state.page = 1;
}

function ensureItemPage(item, visible = filteredDecisions()) {
  const index = visible.findIndex((candidate) => itemKey(candidate) === itemKey(item));
  if (index >= 0) state.page = Math.max(state.page, Math.ceil((index + 1) / ROW_PAGE_SIZE));
  return index;
}

function showToast(message) {
  els.toast.hidden = false;
  els.toast.textContent = message;
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    els.toast.hidden = true;
  }, 2200);
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
    valuation_heading: item?.valuation_section?.heading || item?.valuation_heading,
  });
}

function recentUsableHistoryDecision(item) {
  if (item?.recent_history_fallback?.action) return item.recent_history_fallback;
  const usable = (item?.report_history || []).filter((entry) => {
    const action = String(entry?.action || "").trim();
    return action && action !== "未提取";
  });
  return usable.find((entry) => /最终报告/.test(String(entry?.report_path || ""))) || usable[0] || null;
}

function compactReportConclusion(item) {
  const action = String(item?.action || "").trim();
  const recommendation = String(item?.recommendation || item?.conclusion_summary || "").trim();
  const heading = String(item?.valuation_section?.heading || item?.valuation_heading || "").trim();
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
  const primaryJudgment = primaryJudgmentForItem(item);
  if (primaryJudgment) {
    const meta = actionMeta(primaryJudgment.action_kind || "watch");
    return {
      key: meta.key,
      label: primaryJudgment.label,
      detail: `按主报告判断归类 · ${primaryJudgment.source_basis}`,
      sourceAction: primaryJudgment.empty_position_action,
      rank: meta.rank,
      className: meta.className,
      basis: "primary_report_judgment",
    };
  }
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

function researchJudgmentRank(item) {
  const judgment = primaryJudgmentForItem(item);
  if (judgment) return actionMeta(judgment.action_kind || "unknown").rank;
  return { 买入: 5, 分批买入: 4, 持有: 3, 观察: 2, "减仓/卖出": 1 }[item?.action] || 0;
}

function filteredDecisions() {
  const phrase = els.companyFilter.value.trim().toLocaleLowerCase();
  let list = state.decisions.filter((item) => {
    const marketMatch = state.market === "all" || item.market === state.market;
    const tracking = trackingForItem(item);
    const advice = buyAdviceForItem(item, state.quotes.get(item.ticker));
    const adviceMatch = state.action === "all"
      || executionFilterKey(item, state.quotes.get(item.ticker), advice.key) === state.action;
    const reference = referenceExecutionState(item, state.quotes.get(item.ticker), advice.key);
    const referenceMatch = state.referenceAction === "all" || reference.key === state.referenceAction;
    const trackingMatch = state.view !== "tracking"
      || (tracking && (
        state.trackingFilter === "all"
        || (state.trackingFilter === "alert" && trackingAlertLevel(tracking) !== "none")
        || (state.trackingFilter === "review" && trackingNeedsReview(tracking))
      ));
    const searchable = `${item.company} ${item.ticker || ""} ${item.title || ""}`.toLocaleLowerCase();
    return marketMatch
      && (state.view === "tracking" ? true : adviceMatch)
      && (state.view === "tracking" ? true : referenceMatch)
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
    if (state.sort === "execution") {
      const aa = currentExecutionState(a, state.quotes.get(a.ticker), buyAdviceForItem(a, state.quotes.get(a.ticker)).key);
      const bb = currentExecutionState(b, state.quotes.get(b.ticker), buyAdviceForItem(b, state.quotes.get(b.ticker)).key);
      const d = (bb.rank || 0) - (aa.rank || 0);
      if (d) return d;
      return a.company.localeCompare(b.company, "zh");
    }
    if (state.sort === "reference") {
      const aa = referenceExecutionState(a, state.quotes.get(a.ticker), buyAdviceForItem(a, state.quotes.get(a.ticker)).key);
      const bb = referenceExecutionState(b, state.quotes.get(b.ticker), buyAdviceForItem(b, state.quotes.get(b.ticker)).key);
      const d = (bb.rank || 0) - (aa.rank || 0);
      if (d) return d;
      return a.company.localeCompare(b.company, "zh");
    }
    if (state.sort === "action") {
      const d = researchJudgmentRank(b) - researchJudgmentRank(a);
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

function setLiveStatus(mode, text) {
  state.quoteMode = mode;
  els.liveText.textContent = text;
  els.liveDot.classList.remove("on", "warn", "off");
  if (mode === "live") els.liveDot.classList.add("on");
  else if (mode === "snapshot") els.liveDot.classList.add("warn");
  else els.liveDot.classList.add("off");
}

function indexChangeTone(value) {
  if (!Number.isFinite(Number(value)) || Number(value) === 0) return "neutral";
  return Number(value) > 0 ? "positive" : "negative";
}

function renderIndexCards() {
  if (!els.indexCards) return;
  els.indexCards.replaceChildren();
  const records = A_SHARE_INDEX_WATCH
    .map((item) => state.indices.get(item.index_id) || state.indices.get(item.ticker))
    .filter(Boolean);
  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "source-note";
    empty.textContent = "指数行情快照尚未加载。";
    els.indexCards.append(empty);
    if (els.indexBandMeta) els.indexBandMeta.textContent = "等待行情快照";
    return;
  }
  for (const item of records) {
    const card = document.createElement("article");
    card.className = "index-card";
    const name = document.createElement("span");
    name.className = "index-card-name";
    name.textContent = item.name || item.company || item.ticker;
    const price = document.createElement("strong");
    price.className = "index-card-price";
    price.textContent = Number(item.price).toFixed(2);
    const change = document.createElement("span");
    const changePct = Number(item.change_pct);
    change.className = `index-card-change ${indexChangeTone(changePct)}`;
    change.textContent = Number.isFinite(changePct) ? `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%` : "—";
    card.append(name, price, change);
    els.indexCards.append(card);
  }
  if (els.indexBandMeta) {
    els.indexBandMeta.textContent = `${records.length}/${A_SHARE_INDEX_WATCH.length} 个指数 · ${state.quoteUpdatedAt ? new Date(state.quoteUpdatedAt).toLocaleString() : "时间待复核"}`;
  }
}

function renderAnnualReportDates() {
  if (!els.annualDateContent) return;
  const snapshot = state.annualReportDates;
  els.annualDateContent.replaceChildren();
  if (!snapshot || !Array.isArray(snapshot.records)) {
    const empty = document.createElement("p");
    empty.className = "source-note";
    empty.textContent = "年报日期快照尚未加载。";
    els.annualDateContent.append(empty);
    if (els.annualPanelMeta) els.annualPanelMeta.textContent = "等待更新";
    return;
  }
  if (els.annualPanelMeta) {
    els.annualPanelMeta.textContent = `${snapshot.record_count || snapshot.records.length} 家 · 数据截止 ${snapshot.data_cutoff || "待复核"}`;
  }
  const table = document.createElement("table");
  table.className = "annual-date-table";
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  const latestPeriodLabel = (snapshot.latest_report_period || "最近年度") + "实际披露";
  const nextPeriodLabel = (snapshot.next_report_period || "下一年度") + "预约披露";
  for (const label of ["公司", "代码", latestPeriodLabel, "核对状态", nextPeriodLabel, "状态"]) {
    const th = document.createElement("th");
    th.textContent = label;
    headerRow.append(th);
  }
  head.append(headerRow);
  const body = document.createElement("tbody");
  for (const item of snapshot.records) {
    const row = document.createElement("tr");
    const values = [
      item.company || "未识别",
      item.ticker || "—",
      item.latest_actual_disclosure_date || "未公布",
      item.latest_actual_verification === "cross_checked" ? "双源一致" : item.latest_actual_verification === "source_mismatch" ? "来源不一致" : item.latest_actual_verification === "single_source" ? "单源" : "未核验",
      item.next_scheduled_disclosure_date || "未公布",
      item.next_status || "未公布",
    ];
    values.forEach((value, index) => {
      const cell = document.createElement(index === 0 ? "th" : "td");
      cell.textContent = value;
      if (index === 2) cell.className = item.latest_actual_disclosure_date ? "date-ok" : "date-muted";
      if (index === 3 && item.latest_actual_verification === "source_mismatch") cell.className = "date-warn";
      if (index === 4) cell.className = item.next_scheduled_disclosure_date ? "date-ok" : "date-muted";
      row.append(cell);
    });
    body.append(row);
  }
  table.append(head, body);
  els.annualDateContent.append(table);
}

function automationStatusLabel(status) {
  return {
    ok: "正常",
    partial: "部分成功",
    deferred: "延后重试",
    interrupted: "已中断",
    running: "运行中",
    error: "失败",
    skipped: "跳过",
  }[status] || "待首次运行";
}

function renderAutomationStatus() {
  if (!els.automationStatusContent) return;
  const snapshot = state.automationStatus;
  els.automationStatusContent.replaceChildren();
  if (!snapshot) {
    const empty = document.createElement("p");
    empty.className = "source-note";
    empty.textContent = "统一调度器尚未产生状态快照。安装VPS定时器后，这里会显示每项任务的执行时间。";
    els.automationStatusContent.append(empty);
    if (els.automationPanelMeta) els.automationPanelMeta.textContent = "等待调度器";
    return;
  }
  const jobs = snapshot.jobs || {};
  const schedules = Array.isArray(snapshot.schedules) ? snapshot.schedules : [];
  if (els.automationPanelMeta) {
    els.automationPanelMeta.textContent = snapshot.updated_at ? `最后更新 ${new Date(snapshot.updated_at).toLocaleString()}` : "等待首次运行";
  }
  const table = document.createElement("table");
  table.className = "annual-date-table automation-status-table";
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const label of ["任务", "计划时间", "状态", "最近完成", "耗时", "说明"]) {
    const th = document.createElement("th");
    th.textContent = label;
    headerRow.append(th);
  }
  head.append(headerRow);
  const body = document.createElement("tbody");
  for (const schedule of schedules) {
    const job = jobs[schedule.job_id] || {};
    const row = document.createElement("tr");
    const values = [
      schedule.label || schedule.job_id || "未命名任务",
      schedule.schedule || "待配置",
      automationStatusLabel(job.status),
      job.finished_at || job.last_success_at || "待首次运行",
      job.duration_seconds == null ? "—" : `${job.duration_seconds}s`,
      job.message || schedule.description || "",
    ];
    values.forEach((value, index) => {
      const cell = document.createElement(index === 0 ? "th" : "td");
      cell.textContent = value;
      if (index === 2) cell.className = `status-${job.status || "pending"}`;
      row.append(cell);
    });
    body.append(row);
  }
  table.append(head, body);
  els.automationStatusContent.append(table);
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
      snapshot_generated_at: payload.generated_at || null,
    });
    count += 1;
  }
  state.indices.clear();
  for (const index of payload.indices || []) {
    if (!index?.ticker || !Number.isFinite(Number(index.price))) continue;
    const previous = Number(index.previous_close);
    const price = Number(index.price);
    const changePct = Number.isFinite(Number(index.change_pct))
      ? Number(index.change_pct)
      : Number.isFinite(previous) && previous > 0
        ? ((price - previous) / previous) * 100
        : null;
    state.indices.set(index.index_id || index.ticker, {
      ...index,
      price,
      previous_close: previous,
      change_pct: changePct,
      source: index.source || "snapshot",
      snapshot_generated_at: payload.generated_at || null,
    });
  }
  state.quoteUpdatedAt = payload.generated_at || new Date().toISOString();
  renderIndexCards();
  return count;
}

async function refreshQuotes({ silent = false } = {}) {
  try {
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
    refreshQuotes({ silent: true });
  }, SNAPSHOT_INTERVAL_MS);
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

function intradayTechnicalForItem(item) {
  if (item?.market !== "A股") return { status: "not_applicable", lights: [] };
  return state.intradayTechnical.get(item?.ticker) || item?.intraday_technical_analysis || { status: "missing", lights: [] };
}

function deepReviewForItem(item) {
  if (item?.market !== "A股") return { status: "missing" };
  return state.deepReviews.get(item?.ticker) || { status: "missing" };
}

function intradayTone(technical) {
  if (technical?.status !== "ready") return technical?.status === "review" ? "review" : "missing";
  const state = String(technical.technical_state || "");
  if (/防守|数据待复核|数据不足/.test(state)) return "defensive";
  if (/确认|分批/.test(state)) return "positive";
  return "neutral";
}

function intradayLight(technical, dimension) {
  return (technical?.lights || []).find((light) => light?.dimension === dimension) || null;
}

function renderTechnicalCell(item) {
  const technical = item?.technical_analysis || { status: "missing", lights: [] };
  const intraday = intradayTechnicalForItem(item);
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
  if (item.market === "A股") {
    const intradayFreshness = document.createElement("span");
    intradayFreshness.className = "technical-intraday-freshness";
    intradayFreshness.textContent = intraday.status === "ready"
      ? `盘中30m：${intraday.technical_state || "待复核"}`
      : intraday.status === "failed" ? "盘中30m：抓取失败"
        : intraday.status === "review" ? "盘中30m：待复核" : "盘中30m：未生成";
    cell.append(intradayFreshness);
  }
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
  disclaimer.textContent = "技术面仅辅助观察，不参与当前可执行筛选或买入建议。";
  card.append(disclaimer);

  if (technical.status === "missing") {
    const empty = document.createElement("p");
    empty.className = "technical-empty";
    empty.textContent = "未生成技术面报告。生成后会按技术指标的实际数据截止日自动显示。";
    card.append(empty);
    els.detailBody.append(card);
    renderIntradayTechnicalDetail(item);
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
    renderIntradayTechnicalDetail(item);
    return;
  }

  const summary = document.createElement("dl");
  summary.className = "technical-summary";
  const rows = [
    ["技术状态", technical.state || "待复核"],
    ["分析模式", "收盘日线"],
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
  renderIntradayTechnicalDetail(item);
}

function renderIntradayTechnicalDetail(item) {
  if (item?.market !== "A股") return;
  const intraday = intradayTechnicalForItem(item);
  const card = document.createElement("section");
  card.className = "card technical-detail intraday-technical-detail";
  const title = document.createElement("h3");
  title.textContent = "盘中30分钟辅助观察";
  card.append(title);

  const disclaimer = document.createElement("p");
  disclaimer.className = "technical-disclaimer intraday-disclaimer";
  disclaimer.textContent = "这是独立的30分钟K线节奏层，只辅助观察盘中位置和量价，不改变主报告判断、当前可执行状态或粗颗粒度筛选。";
  card.append(disclaimer);

  if (intraday.status === "missing") {
    const empty = document.createElement("p");
    empty.className = "technical-empty";
    empty.textContent = "尚未生成30分钟盘中快照。日线主报告不受影响。";
    card.append(empty);
    els.detailBody.append(card);
    return;
  }
  if (intraday.status === "failed") {
    const empty = document.createElement("p");
    empty.className = "technical-empty";
    empty.textContent = `30分钟盘中数据抓取失败：${intraday.error || "未知错误"}。日线主报告不受影响。`;
    card.append(empty);
    els.detailBody.append(card);
    return;
  }

  const latest = intraday.latest || {};
  const trend = intraday.trend || {};
  const momentum = intraday.momentum || {};
  const volatility = intraday.volatility || {};
  const session = intraday.intraday || {};
  const summary = document.createElement("dl");
  summary.className = "technical-summary";
  const rows = [
    ["盘中状态", intraday.status === "ready" ? intraday.technical_state || "待复核" : "待复核"],
    ["最新K线", intraday.bar_timestamp || "待复核"],
    ["最新价", latest.close != null ? `${latest.close} ${latest.currency || ""}`.trim() : "待复核"],
    ["VWAP", session.vwap != null ? String(session.vwap) : "数据不足"],
    ["相对量能", session.relative_volume != null ? `${session.relative_volume}x` : "数据不足"],
    ["开盘区间", session.opening_range_low != null && session.opening_range_high != null
      ? `${session.opening_range_low}-${session.opening_range_high}` : "数据不足"],
    ["EMA9 / 20 / 60", [trend.ema9, trend.ema20, trend.ema60].map((value) => value == null ? "-" : value).join(" / ")],
    ["RSI14 / ATR14", `${momentum.rsi14 ?? "-"} / ${volatility.atr14 ?? "-"}`],
    ["数据质量", intraday.confidence || "待复核"],
  ];
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  card.append(summary);

  if (intraday.technical_reason) {
    const reason = document.createElement("p");
    reason.className = "technical-empty";
    reason.textContent = intraday.technical_reason;
    card.append(reason);
  }
  const grid = document.createElement("div");
  grid.className = "technical-light-grid";
  for (const dimension of ["EMA趋势", "动量", "波动", "盘中量价"]) {
    const light = intradayLight(intraday, dimension);
    const itemNode = document.createElement("div");
    itemNode.className = `technical-light-card intraday-light-card ${intradayTone(intraday)}`;
    const label = document.createElement("span");
    label.textContent = dimension;
    const signal = document.createElement("strong");
    signal.className = light?.light === "绿" ? "green" : light?.light === "黄" ? "yellow" : light?.light === "红" ? "red" : "";
    signal.textContent = light?.light || "待复核";
    itemNode.append(label, signal);
    const meaning = document.createElement("p");
    meaning.textContent = light?.meaning || "未提供说明";
    itemNode.append(meaning);
    grid.append(itemNode);
  }
  card.append(grid);
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
  const tierRank = { A: 4, B: 3, C: 2, D: 1 };
  const sortedItems = [...items].sort((left, right) => {
    const tierDelta = (tierRank[String(right.source_tier || "").toUpperCase()] || 0)
      - (tierRank[String(left.source_tier || "").toUpperCase()] || 0);
    if (tierDelta) return tierDelta;
    const inclusionDelta = Number(right.included !== false) - Number(left.included !== false);
    if (inclusionDelta) return inclusionDelta;
    const rightTime = Date.parse(right.published_at || "") || 0;
    const leftTime = Date.parse(left.published_at || "") || 0;
    if (rightTime !== leftTime) return rightTime - leftTime;
    return String(left.title || "").localeCompare(String(right.title || ""), "zh");
  });
  for (const item of sortedItems) {
    const scoreEligible = item.score_eligible !== false;
    const included = item.included !== false && scoreEligible;
    const row = document.createElement("article");
    row.className = `sentiment-news-item ${included ? "included" : "filtered"}`;
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
    inclusion.className = `sentiment-news-tag ${included ? "included" : "filtered"}`;
    inclusion.textContent = !scoreEligible
      ? "仅辅助"
      : item.included === false
      ? "相关性不足"
      : "已纳入评分";
    header.append(inclusion);
    row.append(header);

    const meta = document.createElement("div");
    meta.className = "sentiment-news-meta";
    const dateText = item.published_at ? String(item.published_at).replace("T", " ").slice(0, 16) : "日期未知";
    meta.textContent = `${dateText} · ${item.publisher || "未知来源"} · 来源${item.source_tier || "?"} ${item.source_tier_label || "待复核"} · ${item.event_type || "一般新闻"}`;
    row.append(meta);

    if (item.summary) {
      const summary = document.createElement("p");
      summary.className = "sentiment-news-summary";
      summary.textContent = item.summary;
      row.append(summary);
    }

    const metrics = document.createElement("div");
    metrics.className = "sentiment-news-metrics";
    metrics.textContent = !scoreEligible
      ? `${item.filter_reason || "来源等级不进入评分"} · 核验状态：${item.verification_status || "待复核"}`
      : item.included === false
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
    note.textContent = "该公司当前没有可识别的 investment-checklist 独立报告；这不会改变基本面主报告的结论。";
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
  gateTitle.textContent = `${checklist.total_gates || 6}项检查`;
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
    empty.textContent = "报告未提供可结构化的检查表，请打开原报告复核。";
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
  } else if (state.sentimentStatus?.status === "partial") {
    const skipped = (state.sentimentStatus.skipped_articles || [])
      .filter((entry) => entry.ticker === item.ticker);
    if (skipped.length) {
      const warning = document.createElement("p");
      warning.className = "sentiment-warning-note sentiment-partial-note";
      warning.textContent = `本次更新部分成功：该股有${skipped.length}条新闻在重试后仍失败并跳过，其余成功结果已写入。`;
      card.append(warning);
    }
  }
  const summary = document.createElement("dl");
  summary.className = "kv-grid sentiment-summary";
  const industry = record.industry_sentiment || record.industry_detail;
  const market = state.sentimentSnapshot?.market_sentiment?.[item.market];
  const combined = record.combined_sentiment;
  const rows = [
    ["综合情绪（三层）", `${sentimentScoreText(sentimentDisplayScore(combined))} · ${sentimentDisplayState(combined)}`],
    ["个股情绪（含辅助AI）", `${sentimentScoreText(sentimentDisplayScore(record.news_sentiment))} · ${sentimentDisplayState(record.news_sentiment)}`],
    ["个股正式来源", `${sentimentScoreText(record.news_sentiment?.formal_score_0_100)} · ${record.news_sentiment?.formal_status || "待复核"}`],
    ["行业情绪", `${sentimentScoreText(sentimentDisplayScore(industry))} · ${sentimentDisplayState(industry)}`],
    ["市场情绪", `${sentimentScoreText(sentimentDisplayScore(market))} · ${sentimentDisplayState(market)}`],
    ["新闻池", `正式 ${record.news_sentiment?.score_article_count || 0} · AI分析 ${record.news_sentiment?.context_only_article_count || 0} · 辅助总量 ${record.news_sentiment?.auxiliary_article_count || 0}`],
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
  note.textContent = "综合情绪由个股60% + 行业25% + A股市场15%组成；C/D新闻仅按降权上下文进入，缺失层不会放大其他层权重。行业权威来源可为A级，但仍按行业传导系数处理。";
  card.append(note);
  els.detailBody.append(card);

  els.detailBody.append(renderNewsList("个股新闻 · 全部抓取结果", record.news_sentiment, {
    emptyText: record.news_sentiment?.state || "暂无个股新闻",
  }));
  els.detailBody.append(renderNewsList("行业/相关新闻 · AI分析与辅助线索", record.industry_detail, {
    emptyText: industry?.state || "暂无行业新闻",
  }));
}

function opportunityCandidateForItem(item) {
  if (item?.market !== "A股") return null;
  const manual = item?.manual_execution_review;
  if (manual?.status === "ready" && manual?.source === "human_review") {
    const tier = manual.opportunity_tier;
    if (!['current', 'near'].includes(tier)) return null;
    return {
      item,
      manual,
      scan: null,
      union: {},
      models: [],
      quote: state.quotes.get(item.ticker),
      judgment: primaryJudgmentForItem(item),
      staleModels: [],
      relevantModels: [],
      priority: tier === "current" ? 100 : 90,
      tier,
      label: tier === "current" ? "人工复核 · 当前机会" : "人工复核 · 临近机会",
      tone: tier === "near" ? "notice" : "opportunity",
    };
  }
  return null;
}

function renderOpportunityCard(candidate) {
  const { item, manual, scan, models, relevantModels, judgment, quote } = candidate;
  const card = document.createElement("article");
  card.className = `attention-card attention-${candidate.tone}`;

  const head = document.createElement("div");
  head.className = "attention-card-head";
  const identity = document.createElement("div");
  identity.className = "attention-card-identity";
  const company = document.createElement("strong");
  company.className = "attention-company";
  company.textContent = item.company;
  const code = document.createElement("span");
  code.className = "attention-code";
  code.textContent = `${item.market} · ${item.ticker || "无代码"}`;
  identity.append(company, code);
  const badge = document.createElement("span");
  badge.className = "attention-badge";
  badge.textContent = candidate.label;
  head.append(identity, badge);
  card.append(head);

  const facts = document.createElement("div");
  facts.className = "attention-card-facts";
  const judgmentFact = document.createElement("span");
  judgmentFact.textContent = `报告视角：${judgment?.label || item.action || "待复核"}`;
  const currentPriceFact = document.createElement("span");
  currentPriceFact.textContent = `当前现价：${formatPrice(quote)}`;
  facts.append(judgmentFact, currentPriceFact);
  const scanQuote = scan?.input_context?.current_quote || scan?.input_snapshot?.current_quote;
  if (scanQuote?.price != null) {
    const scanPriceFact = document.createElement("span");
    scanPriceFact.textContent = `模型输入价：${formatPrice(scanQuote)}`;
    facts.append(scanPriceFact);
  }
  card.append(facts);

  const focus = document.createElement("p");
  focus.className = "attention-card-focus";
  focus.textContent = manual
    ? `${manual.reviewer || "人工复核"} · ${manual.reviewed_at?.slice(0, 10) || "日期待复核"} · 分组 ${manual.category}`
    : models.map(([model, result]) => `${model}：${result.assessment?.opportunity_state || "待复核"}`).join(" · ");
  card.append(focus);

  const whyNow = manual?.opportunity_summary || relevantModels
    .map(([, result]) => result.assessment?.why_now)
    .filter(Boolean)
    .join(" ");
  if (whyNow) {
    const why = document.createElement("p");
    why.className = "attention-card-why";
    why.textContent = `为什么是现在：${whyNow}`;
    card.append(why);
  }

  const explanation = document.createElement("p");
  explanation.className = "attention-card-reason";
  explanation.textContent = manual?.detail || relevantModels
    .map(([, result]) => result.assessment?.opportunity_summary)
    .filter(Boolean)
    .join(" ") || "机会摘要待复核。";
  card.append(explanation);

  const flags = document.createElement("div");
  flags.className = "attention-card-flags";
  for (const [model, result] of models) {
    if (!result.assessment?.confidence) continue;
    const confidence = document.createElement("span");
    confidence.textContent = `${model} · ${result.assessment.confidence}`;
    flags.append(confidence);
  }
  if (candidate.staleModels.length) {
    const stale = document.createElement("span");
    stale.textContent = `沿用 ${candidate.staleModels.length} 份同报告旧结果`;
    flags.append(stale);
  }
  if (flags.childElementCount) card.append(flags);

  const foot = document.createElement("div");
  foot.className = "attention-card-foot";
  const open = document.createElement("button");
  open.type = "button";
  open.className = "btn ghost attention-open";
  open.textContent = manual ? "查看个股详情" : "启动深度复核";
  open.addEventListener("click", (event) => {
    event.stopPropagation();
    if (manual) openDetail(item);
    else startDeepReview(item, open);
  });
  foot.append(open);
  card.append(foot);
  return card;
}

function appendOpportunityCards(grid, candidates) {
  for (const candidate of candidates) grid.append(renderOpportunityCard(candidate));
}

function renderOpportunityGroup(candidates, title, note) {
  const group = document.createElement("section");
  group.className = "attention-group";
  const head = document.createElement("div");
  head.className = "attention-group-head";
  const heading = document.createElement("h3");
  heading.textContent = `${title} · ${candidates.length}`;
  const description = document.createElement("p");
  description.textContent = note;
  head.append(heading, description);
  const grid = document.createElement("div");
  grid.className = "attention-group-grid";
  appendOpportunityCards(grid, candidates);
  group.append(head, grid);
  return group;
}

function renderAttentionPanel() {
  if (!els.attentionPanel || !els.attentionList || state.view === "tracking") {
    if (els.attentionPanel) els.attentionPanel.hidden = true;
    return;
  }

  const aShares = state.decisions.filter((item) => item.market === "A股");
  const manualReviews = aShares.filter((item) => item.manual_execution_review?.status === "ready");
  const candidates = aShares
    .map(opportunityCandidateForItem)
    .filter(Boolean)
    .sort((a, b) => b.priority - a.priority || a.item.company.localeCompare(b.item.company, "zh"));
  const currentCandidates = candidates.filter((candidate) => candidate.tier === "current");
  const nearCandidates = candidates.filter((candidate) => candidate.tier === "near");

  els.attentionPanel.hidden = false;
  const fullManualCoverage = manualReviews.length === aShares.length && aShares.length > 0;
  const metaText = `人工机会 ${currentCandidates.length} · 临近 ${nearCandidates.length} · 有效人工复核 ${manualReviews.length}/${aShares.length}`;
  els.attentionMeta.textContent = metaText;
  els.attentionMeta.dataset.status = fullManualCoverage ? "ready" : "partial";
  if (els.attentionToggleMeta) {
    els.attentionToggleMeta.textContent = `有效人工复核 ${manualReviews.length}/${aShares.length} · 人工机会 ${currentCandidates.length} · 临近 ${nearCandidates.length}`;
    els.attentionToggleMeta.dataset.status = fullManualCoverage ? "ready" : "partial";
  }
  if (els.attentionToggleState) els.attentionToggleState.textContent = els.attentionPanel.open ? "收起" : "展开";
  els.attentionList.replaceChildren();

  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.className = "attention-empty";
    empty.textContent = manualReviews.length
      ? "有效人工复核中没有进入当前或临近机会的股票。"
      : "当前没有有效人工复核记录，机会面板暂停生成。";
    els.attentionList.append(empty);
    return;
  }

  if (currentCandidates.length) {
    els.attentionList.append(renderOpportunityGroup(
      currentCandidates,
      "人工机会",
      "逐股人工核对主报告、最新财报与价格后保留；是否行动仍由你判断。",
    ));
  } else {
    const emptyCurrent = document.createElement("p");
    emptyCurrent.className = "attention-empty attention-current-empty";
    emptyCurrent.textContent = "当前没有被人工复核保留为机会的股票。";
    els.attentionList.append(emptyCurrent);
  }

  if (nearCandidates.length) {
    const near = document.createElement("details");
    near.className = "attention-near";
    const summary = document.createElement("summary");
    summary.textContent = `临近机会 · ${nearCandidates.length}（仍缺一个决定性条件，点击展开）`;
    const grid = document.createElement("div");
    grid.className = "attention-group-grid attention-near-grid";
    near.addEventListener("toggle", () => {
      if (near.open && !near.dataset.rendered) {
        appendOpportunityCards(grid, nearCandidates);
        near.dataset.rendered = "true";
      }
    });
    near.append(summary, grid);
    els.attentionList.append(near);
  }
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
  const aShareVisible = visible.filter((item) => item.market === "A股");
  let nextCandidateCount = 0;
  const referenceCounts = {};
  const counts = aShareVisible.reduce((acc, item) => {
    const advice = buyAdviceForItem(item, state.quotes.get(item.ticker));
    const execution = currentExecutionState(item, state.quotes.get(item.ticker), advice.key);
    const key = execution.key;
    if (execution.nextTradingDayCandidate) nextCandidateCount += 1;
    acc[key] = (acc[key] || 0) + 1;
    const reference = referenceExecutionState(item, state.quotes.get(item.ticker), advice.key);
    referenceCounts[reference.key] = (referenceCounts[reference.key] || 0) + 1;
    return acc;
  }, {});
  const manualReviewCount = aShareVisible.filter(
    (item) => item.validity_state !== "ready" || item.manual_execution_review?.status !== "ready",
  ).length;
  const sentimentReadyCount = aShareVisible.filter(
    (item) => sentimentForItem(item)?.combined_sentiment?.status === "ok",
  ).length;
  const metrics = [
    ["当前个股", visible.length],
    ["A股", aShareVisible.length],
    ["港股", visible.filter((i) => i.market === "港股").length],
    ["A股情绪可用", `${sentimentReadyCount}/${aShareVisible.length}`],
    ["当前可买/小仓", (counts.actionable || 0) + (counts.trial || 0)],
    ["下个交易日候选", nextCandidateCount],
    ["价格已到待验证", counts.validation || 0],
    ["等待价格/事件", (counts.wait_price || 0) + (counts.wait_event || 0)],
    ["行情/时段暂停", counts.paused || 0],
    ["待人工复核", manualReviewCount],
    ["参考可分批/小仓", (referenceCounts.actionable || 0) + (referenceCounts.trial || 0)],
    ["参考待验证", referenceCounts.validation || 0],
    ["参考等待价格/条件", (referenceCounts.wait_price || 0) + (referenceCounts.wait_event || 0)],
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
    mountInlineDetail(selectedItem());
    if (els.loadMoreRows) els.loadMoreRows.hidden = true;
    els.status.textContent = `显示 ${visible.length} / ${state.decisions.filter((item) => trackingForItem(item)).length} · 持仓跟踪`;
    if (els.emptyState) els.emptyState.hidden = visible.length > 0;
    if (state.focusIndex >= visible.length) state.focusIndex = visible.length - 1;
    return;
  }
  setTableHeader([
    "公司",
    "市场 / 代码",
    "情绪",
    "主报告判断",
    "现价",
    "当前状态 / 非实时参考",
    "技术面（辅助）",
    "技术价 / 基本面交叉",
  ]);

  const rendered = visible.slice(0, state.page * ROW_PAGE_SIZE);
  rendered.forEach((item, index) => {
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
    actionTd.append(
      renderPrimaryJudgment(item, { compact: true })
      || renderPriceActionTable(item, quote, { compact: true }),
    );
    tr.append(actionTd);

    const change = formatChange(quote);
    const quoteTd = document.createElement("td");
    quoteTd.className = "quote-block";
    quoteTd.innerHTML = `
      <div class="quote-price">${formatPrice(quote)}</div>
      <div class="quote-change ${change.className}">${change.text}${quote?.source ? " · 同源快照" : ""}</div>
    `;
    tr.append(quoteTd);

    const adviceTd = document.createElement("td");
    adviceTd.className = "buy-advice-cell";
    adviceTd.append(renderExecutionState(item, quote, { compact: true }));
    tr.append(adviceTd);

    tr.append(renderTechnicalCell(item));
    tr.append(renderTechnicalCrossCell(item));

    tr.addEventListener("click", () => openDetail(item, { scrollRow: false }));
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter") openDetail(item, { scrollRow: false });
    });
    els.rows.append(tr);
  });

  mountInlineDetail(selectedItem());

  const remaining = Math.max(0, visible.length - rendered.length);
  if (els.loadMoreRows) {
    els.loadMoreRows.hidden = remaining === 0;
    els.loadMoreRows.textContent = remaining ? `加载更多（剩余 ${remaining} 条）` : "已显示全部";
  }
  els.status.textContent = `显示 ${rendered.length} / ${visible.length} · 排序：${els.sortSelect.selectedOptions[0]?.text || state.sort}`;
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

  const manage = document.createElement("div");
  manage.className = "tracking-manage-row";
  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "btn danger";
  removeButton.textContent = "删除本机跟踪记录";
  removeButton.title = "仅从当前浏览器隐藏，源数据不会被删除";
  removeButton.addEventListener("click", () => hideTrackingForCurrentBrowser(item));
  const manageNote = document.createElement("span");
  manageNote.className = "source-note";
  manageNote.textContent = "静态看板不能直接修改 VPS 源文件；此操作只隐藏当前浏览器记录。";
  manage.append(removeButton, manageNote);
  appendTrackingDetailCard("跟踪记录管理", manage);

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

function mountInlineDetail(item) {
  if (!item || !els.rows || !els.detailPanel) return false;
  const key = itemKey(item);
  const row = Array.from(els.rows.querySelectorAll("tr[data-key]")).find((node) => node.dataset.key === key);
  if (!row) return false;

  const existing = Array.from(els.rows.querySelectorAll("tr.detail-inline-row"))
    .find((node) => node.dataset.detailFor === key);
  if (existing) {
    const existingCell = existing.querySelector("td");
    if (existingCell && els.detailPanel.parentElement !== existingCell) existingCell.append(els.detailPanel);
    if (row.nextElementSibling !== existing) row.insertAdjacentElement("afterend", existing);
    return true;
  }

  const detailRow = document.createElement("tr");
  detailRow.className = "detail-inline-row";
  detailRow.dataset.detailFor = key;
  const cell = document.createElement("td");
  cell.colSpan = Math.max(1, els.decisionHead.querySelectorAll("th").length);
  cell.append(els.detailPanel);
  detailRow.append(cell);
  row.insertAdjacentElement("afterend", detailRow);
  return true;
}

function renderDetail() {
  const item = selectedItem();
  if (!item) {
    document.body.classList.remove("drawer-open");
    els.detailPanel.hidden = true;
    return;
  }
  if (!mountInlineDetail(item)) {
    document.body.classList.remove("drawer-open");
    els.detailPanel.hidden = true;
    return;
  }
  document.body.classList.add("drawer-open");
  els.detailPanel.hidden = false;
  els.detailTitle.textContent = item.company;
  const quote = state.quotes.get(item.ticker);
  const change = formatChange(quote);
  els.detailKicker.textContent = `${item.market || "未识别"} · ${item.ticker || "无代码"}`;
  const priceRows = reportPriceRows(item);
  const historicalReference = priceRows[0]?.source === "historical_price_reference";
  const tableBrief = priceRows.length
    ? `${priceRows.length} 档${historicalReference ? "历史价格参照" : "报告价格"}`
    : "未提取价格表";
  const fallbackAdvice = buyAdviceForItem(item, quote);
  const execution = currentExecutionState(item, quote, fallbackAdvice.key);
  const adviceBrief = execution.label;
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
  const deepReviewTab = document.querySelector(".deep-review-tab");
  const isAShare = item.market === "A股";
  if (deepReviewTab) {
    deepReviewTab.hidden = !isAShare || !isAdminOrigin();
    if ((!isAShare || !isAdminOrigin()) && state.detailTab === "deep-review") state.detailTab = "overview";
  }
  const hasChecklist = Boolean(checklistForItem(item));
  if (checklistTab) {
    checklistTab.hidden = !hasChecklist;
    if (!hasChecklist && state.detailTab === "checklist") state.detailTab = "overview";
  }
  document.querySelectorAll(".detail-tabs .tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === state.detailTab);
  });

  const detailNeeded = ["overview", "history"].includes(state.detailTab);
  if (detailNeeded && !detailLoaded(item)) {
    const loading = document.createElement("div");
    loading.className = "card detail-loading-card";
    const error = state.detailErrors.get(itemKey(item));
    loading.innerHTML = `<h3>${error ? "详细研报加载失败" : "正在加载完整研报上下文"}</h3><p class="source-note">${error || "首屏只加载决策所需字段；历史研报和估值内容在打开详情后读取。"}</p>`;
    if (error) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn ghost";
      retry.textContent = "重新加载详细研报";
      retry.addEventListener("click", () => {
        state.detailErrors.delete(itemKey(item));
        loadDecisionDetail(item)
          .then(() => renderDetail())
          .catch(() => renderDetail());
        renderDetail();
      });
      loading.append(retry);
    }
    els.detailBody.append(loading);
    return;
  }

  if (state.detailTab === "tracking") {
    renderTrackingDetail(item, tracking);
    return;
  }

  if (state.detailTab === "overview") {
    const primaryJudgment = renderPrimaryJudgment(item, { compact: false });
    if (primaryJudgment) {
      const primaryCard = document.createElement("div");
      primaryCard.className = "card primary-judgment-card";
      primaryCard.append(primaryJudgment);
      els.detailBody.append(primaryCard);

      const auxiliaryCard = document.createElement("div");
      auxiliaryCard.className = "card primary-judgment-aux-card";
      auxiliaryCard.innerHTML = "<h3>当前状态 / 非实时参考</h3>";
      auxiliaryCard.append(renderExecutionState(item, quote, { compact: false }));
      els.detailBody.append(auxiliaryCard);
    }

    const adviceCard = document.createElement("div");
    adviceCard.className = "card";
    const advice = fallbackAdvice;
    adviceCard.innerHTML = `<h3>旧报告兼容归类</h3>`;
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
    if (!primaryJudgment) els.detailBody.append(adviceCard);

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
      [primaryJudgment ? "原契约粗标签" : "粗粒度标签", item.action || "-"],
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
    tip.innerHTML = primaryJudgment
      ? `<h3>筛选依据</h3><p class="source-note">主报告判断始终保留原文；已完成的逐股人工复核优先决定“当前可执行状态”，并覆盖旧的机械价格归类。未完成人工复核时，才按报告价格档与经营前提推导。Checklist 硬性否决不得进入可买列表；技术面和情绪面保持独立辅助展示。</p>`
      : `<h3>筛选依据</h3><p class="source-note">尚无双模型主报告判断的非 A 股，暂按旧报告结论兼容归类；完整基本面上下文请打开主报告。</p>`;
    els.detailBody.append(tip);
    return;
  }

  if (state.detailTab === "technical") {
    renderTechnicalDetail(item);
    return;
  }

  if (state.detailTab === "deep-review") {
    renderDeepReviewDetail(item);
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
  if (!row) return;
  if (!wrap || wrap.scrollHeight <= wrap.clientHeight) {
    row.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    return;
  }
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

function revealDetailPanel() {
  const detailRow = els.detailPanel?.closest("tr.detail-inline-row");
  if (!detailRow || els.detailPanel.hidden) return;
  const rect = detailRow.getBoundingClientRect();
  const topGuard = 82;
  const bottomGuard = Math.min(window.innerHeight - 48, 720);
  if (rect.top < topGuard || rect.top > bottomGuard) {
    detailRow.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }
}

function openDetail(item, { scrollRow = true, updateUrl = true } = {}) {
  if (!item) return;
  state.selectedKey = itemKey(item);
  const visible = filteredDecisions();
  state.focusIndex = ensureItemPage(item, visible);
  if (updateUrl) updateHash(item);
  renderRows();
  renderDetail();
  loadDecisionDetail(item)
    .then(() => {
      if (state.selectedKey === itemKey(item)) {
        renderRows();
        renderDetail();
      }
    })
    .catch(() => {
      if (state.selectedKey === itemKey(item)) renderDetail();
    });
  if (els.detailBody) els.detailBody.scrollTop = 0;
  if (scrollRow) {
    const row = Array.from(els.rows.querySelectorAll("tr[data-key]")).find((node) => node.dataset.key === state.selectedKey);
    revealTableRow(row);
  }
  revealDetailPanel();
}

function closeDetail() {
  state.selectedKey = null;
  state.focusIndex = -1;
  updateHash(null);
  renderRows();
  renderDetail();
}

function renderAll() {
  renderIndexCards();
  renderAnnualReportDates();
  renderAutomationStatus();
  renderAttentionPanel();
  renderRows();
  renderDetail();
}

function setView(view) {
  state.view = view === "tracking" ? "tracking" : "decision";
  state.focusIndex = -1;
  resetRowPage();
  if (state.view === "tracking") {
    state.detailTab = "tracking";
  } else if (state.detailTab === "tracking") {
    state.detailTab = "valuation";
  }
  els.viewTabs?.querySelectorAll(".chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.view === state.view);
  });
  if (els.actionChips) els.actionChips.hidden = state.view === "tracking";
  if (els.referenceActionChips) els.referenceActionChips.hidden = state.view === "tracking";
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
    resetRowPage();
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
    resetRowPage();
    renderRows();
  });
  els.clearFilters.addEventListener("click", () => {
    state.market = "all";
    state.action = "all";
    state.referenceAction = "all";
    state.trackingFilter = "all";
    state.sort = "execution";
    resetRowPage();
    els.companyFilter.value = "";
    els.sortSelect.value = "execution";
    els.marketChips.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.market === "all");
    });
    els.actionChips.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.action === "all");
    });
    els.referenceActionChips?.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.referenceAction === "all");
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
    resetRowPage();
    els.marketChips.querySelectorAll(".chip").forEach((node) => {
      node.classList.toggle("active", node === chip);
    });
    renderRows();
  });
  els.actionChips.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    state.action = chip.dataset.action;
    resetRowPage();
    els.actionChips.querySelectorAll(".chip").forEach((node) => {
      node.classList.toggle("active", node === chip);
    });
    renderRows();
  });
  els.referenceActionChips?.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    state.referenceAction = chip.dataset.referenceAction;
    resetRowPage();
    els.referenceActionChips.querySelectorAll(".chip").forEach((node) => {
      node.classList.toggle("active", node === chip);
    });
    renderRows();
  });
  els.trackingFilterRow?.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    state.trackingFilter = chip.dataset.trackingFilter || "all";
    resetRowPage();
    els.trackingFilterRow.querySelectorAll(".chip").forEach((node) => {
      node.classList.toggle("active", node === chip);
    });
    renderRows();
  });
  els.restoreTracking?.addEventListener("click", restoreHiddenTracking);
  els.loadMoreRows?.addEventListener("click", () => {
    state.page += 1;
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
  els.refreshQuotes.addEventListener("click", () => refreshQuotes());
  els.attentionPanel?.addEventListener("toggle", () => {
    if (els.attentionToggleState) els.attentionToggleState.textContent = els.attentionPanel.open ? "收起" : "展开";
  });
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
  const statusResponse = await fetch("./data/sentiment_status.json", { cache: "no-cache" });
  state.sentimentStatus = statusResponse.ok
    ? await statusResponse.json()
    : {status: "unknown"};
  const response = await fetch("./data/sentiment.json", { cache: "no-cache" });
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

async function loadIntradayTechnicalSnapshot() {
  const response = await fetch("./data/intraday_technical.json", { cache: "no-cache" });
  if (!response.ok) {
    state.intradayTechnical = new Map();
    return;
  }
  const snapshot = await response.json();
  state.intradayTechnical = new Map(
    (snapshot.companies || [])
      .filter((item) => item?.ticker && item.market === "A股")
      .map((item) => [item.ticker, item]),
  );
}

async function loadAnnualReportDates() {
  const response = await fetch("./data/annual_report_dates.json", { cache: "no-cache" });
  if (!response.ok) throw new Error("annual report dates missing");
  state.annualReportDates = await response.json();
  renderAnnualReportDates();
}

async function loadAutomationStatus() {
  const response = await fetch("./data/automation_status.json", { cache: "no-cache" });
  if (!response.ok) throw new Error("automation status missing");
  state.automationStatus = await response.json();
  renderAutomationStatus();
}

async function loadDashboard() {
  setLiveStatus("idle", "加载决策数据…");
  const board = await fetchDecisionBoard();
  state.decisions = board.decisions || [];
  state.generationId = board.generation_id || null;
  state.page = 1;
  state.hiddenTrackingKeys = loadHiddenTrackingKeys();
  updateTrackingControls();

  // Paint the list as soon as the primary board is available.  The auxiliary
  // snapshots are independent and should not block the first useful view.
  performance.mark("dashboard-list-ready");
  setLiveStatus("idle", "列表已载入，补充行情和辅助数据…");
  renderAll();

  const [intradayResult, sentimentResult, deepReviewsResult, snapshotQuotesResult, annualDatesResult, automationStatusResult] =
    await Promise.allSettled([
      loadIntradayTechnicalSnapshot(),
      loadSentimentSnapshot(),
      loadDeepReviews(),
      loadSnapshotQuotes(),
      loadAnnualReportDates(),
      loadAutomationStatus(),
    ]);

  if (intradayResult.status === "rejected") {
    console.warn("intraday technical snapshot failed", intradayResult.reason);
    state.intradayTechnical = new Map();
  }
  if (sentimentResult.status === "rejected") {
    const error = sentimentResult.reason;
    state.sentimentError = error;
    state.sentimentStatus = {status: "error", error: error.message};
    state.sentimentSnapshot = null;
    state.sentiments = new Map();
    updateSentimentAlert();
  }
  if (deepReviewsResult.status === "rejected") {
    console.warn("deep reviews are unavailable", deepReviewsResult.reason);
  }
  if (snapshotQuotesResult.status === "fulfilled" && snapshotQuotesResult.value > 0) {
    setLiveStatus("snapshot", `行情快照 · ${snapshotQuotesResult.value} 只 · ${new Date().toLocaleTimeString()}`);
  }
  if (annualDatesResult.status === "rejected") {
    console.warn("annual report dates snapshot failed", annualDatesResult.reason);
    state.annualReportDates = null;
  }
  if (automationStatusResult.status === "rejected") {
    console.warn("automation status snapshot failed", automationStatusResult.reason);
    state.automationStatus = null;
  }

  performance.mark("dashboard-data-ready");
  renderAll();
  applyHashRoute();
  await refreshQuotes({ silent: true });
  startQuoteTimers();
}

bindEvents();
loadDashboard().catch((error) => {
  els.status.textContent = `加载失败：${error.message}`;
  setLiveStatus("error", "加载失败");
});
