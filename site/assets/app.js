import {
  currentExecutionState,
  currentActionKind,
  fallbackActionKind,
  humanReviewExecutionState,
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
  opportunityScans: new Map(),
  opportunityScansGeneratedAt: null,
  opportunityScanStatus: null,
  opportunityScanModels: [],
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
  fundamentalReviewSnapshot: null,
  fundamentalReviews: new Map(),
  selectedKey: null,
  generationId: null,
  view: "decision",
  market: "all",
  action: "all",
  referenceAction: "all",
  humanReviewAction: "all",
  fundamentalReviewFilter: "all",
  trackingFilter: "all",
  hiddenTrackingKeys: new Set(),
  sort: "execution",
  detailTab: "technical",
  quoteMode: "idle", // snapshot | idle | error
  quoteUpdatedAt: null,
  quoteSnapshotMeta: null,
  liveTimer: null,
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
  advancedFilters: document.querySelector("#advanced-filters"),
  referenceActionChips: document.querySelector("#reference-action-chips"),
  humanReviewChips: document.querySelector("#human-review-chips"),
  viewTabs: document.querySelector("#view-tabs"),
  fundamentalReviewFilterRow: document.querySelector("#fundamental-review-filter-row"),
  fundamentalReviewPartitions: document.querySelector("#fundamental-review-partitions"),
  fundamentalReviewCount: document.querySelector("#fundamental-review-count"),
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
  liveStatus: document.querySelector("#live-status"),
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
  sortField: document.querySelector("#sort-field"),
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

function updateFundamentalReviewControls() {
  if (els.fundamentalReviewCount) {
    els.fundamentalReviewCount.textContent = String(state.fundamentalReviews.size);
  }
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

function attentionTimestamp(timestamp) {
  const date = new Date(timestamp || "");
  if (!Number.isFinite(date.getTime())) return "时间未知";
  return date.toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function timestampMillis(value) {
  const millis = new Date(value || "").getTime();
  return Number.isFinite(millis) ? millis : null;
}

function manualReviewIsFreshForScan(item) {
  const manual = item?.manual_execution_review;
  if (!manual || manual.status !== "ready") return false;
  const scan = opportunityScanForItem(item);
  const scanAt = timestampMillis(scan?.generated_at || state.opportunityScansGeneratedAt);
  const reviewAt = timestampMillis(manual.reviewed_at);
  // If either side has no timestamp, retain the existing manual-review
  // behavior. Once both are known, the newest evidence wins.
  return scanAt === null || reviewAt === null || reviewAt >= scanAt;
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
  wrap.append(eyebrow, label, emptyAction);
  if (!compact) {
    const trigger = document.createElement("p");
    trigger.className = "primary-judgment-trigger";
    trigger.textContent = `触发条件：${judgment.trigger_condition}`;
    const summary = document.createElement("p");
    summary.className = "primary-judgment-summary";
    summary.textContent = judgment.summary;
    wrap.append(trigger, summary);
  }

  if (judgment.human_reviewed === true) {
    const reviewed = document.createElement("p");
    reviewed.className = "primary-judgment-consensus";
    reviewed.textContent = "已人工核对主报告原文 · 主报告结论优先于模型标签分歧";
    wrap.append(reviewed);
  }

  if (judgment.report_field_conflict) {
    const conflict = document.createElement("p");
    conflict.className = "primary-judgment-conflict";
    conflict.textContent = compact
      ? "字段冲突：已按主报告正文处理，详情可查看说明。"
      : `字段冲突：${judgment.conflict_note || "粗粒度字段与报告正文不一致"}`;
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
  label.textContent = `当前执行分区：${execution.label}`;
  const detail = document.createElement("p");
  detail.textContent = execution.detail;
  wrap.append(label, detail);
  if (execution.rule?.price_range) {
    const priceBand = document.createElement("p");
    priceBand.className = "primary-judgment-aux-note";
    priceBand.textContent = `当前价格对应报告区间：${execution.rule.price_range}`;
    wrap.append(priceBand);
  }
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
    consensus.textContent = "主报告细分口径存在分歧；当前状态采用更保守的安全交集。";
    wrap.append(consensus);
  }
  if (
    execution.manualReviewCaveat
    && (execution.manualReviewState !== "ready" || execution.manualReviewKey !== execution.key)
  ) {
    const reviewNote = document.createElement("p");
    reviewNote.className = "primary-judgment-aux-note manual-review-caveat";
    reviewNote.textContent = execution.manualReviewCaveat;
    wrap.append(reviewNote);
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
    note.textContent = "当前执行分区由主报告动作许可、价格档/经营前提与最新同源行情生成；人工复核只作提示，Checklist 不参与自动分区，技术面与情绪面仅作辅助。";
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

function humanReviewForItem(item, quote) {
  return humanReviewExecutionState(item, quote, reportPriceRows(item, { historicalFallback: false }));
}

function humanReviewPlanForItem(item) {
  const plan = item?.human_review_plan;
  return plan && Array.isArray(plan.tasks) ? plan : null;
}

function humanReviewTaskSourceLabel(task) {
  const source = task?.source_field;
  return {
    empty_position_action: "空仓行动",
    holder_action: "持仓行动",
    trigger_condition: "触发条件",
  }[source] || "主报告判断";
}

function humanReviewTaskDateText(task) {
  if (task?.date_status === "event_trigger") return "复核时间：事件触发后复核";
  if (task?.date_status === "price_only") return "复核时间：随行情判断";
  if (task?.date_status === "source_mismatch") return "复核时间：日期待核对（官方来源不一致）";
  const details = Array.isArray(task?.calendar_date_details) ? task.calendar_date_details : [];
  const dates = details.map((detail) => {
    const period = detail.period_label || detail.period_key || "财报";
    const actual = detail.actual_date ? `实际披露 ${detail.actual_date}` : "";
    const scheduled = detail.scheduled_date && detail.scheduled_date !== detail.actual_date
      ? `预约 ${detail.scheduled_date}`
      : detail.scheduled_date
        ? `实际/预约 ${detail.scheduled_date}`
        : "";
    const fallback = detail.effective_date ? `披露 ${detail.effective_date}` : "日期待公布";
    const verification = detail.actual_verification || detail.scheduled_verification;
    const verificationText = verification === "cross_checked"
      ? "东财+巨潮核验"
      : verification === "single_source"
        ? "单一官方来源"
        : "";
    const dateBody = [actual, scheduled].filter(Boolean).join("；") || fallback;
    return `${period}：${dateBody}${verificationText ? `（${verificationText}）` : ""}`;
  });
  const dateText = dates.length ? ` · ${dates.join("；")}` : "";
  return `复核时间：${task?.schedule_label || "财报披露后"} · ${task?.status_label || "待确认"}${dateText}`;
}

function humanReviewTaskCompactDateText(task) {
  const dateStatus = task?.date_status;
  if (dateStatus === "event_trigger" || dateStatus === "price_only") {
    return task?.status_label || "事件触发后复核";
  }
  if (dateStatus === "source_mismatch") return "日期待核对";
  if (dateStatus === "unannounced") return "日期待公布";

  const details = Array.isArray(task?.calendar_date_details) ? task.calendar_date_details : [];
  const targetDate = task?.next_review_date || details[0]?.effective_date || details[0]?.scheduled_date;
  const target = details.find((detail) => detail.effective_date === targetDate)
    || details.find((detail) => detail.scheduled_date === targetDate)
    || details[0];
  const period = target?.period_label || "财报";
  const date = targetDate || "日期待公布";
  return `${period} · ${date} · ${task?.status_label || "待确认"}`;
}

function renderHumanReviewPlan(item, { compact = false } = {}) {
  const plan = humanReviewPlanForItem(item);
  const wrap = document.createElement("div");
  wrap.className = `human-review-plan ${compact ? "human-review-plan-compact" : ""}`;
  if (!plan || plan.status !== "ready") {
    const note = document.createElement("p");
    note.className = "human-review-note";
    note.textContent = plan?.message || "暂无可用的人工复核事项";
    wrap.append(note);
    return wrap;
  }
  const tasks = plan.tasks || [];
  if (!tasks.length) {
    const note = document.createElement("p");
    note.className = "human-review-note";
    note.textContent = "暂无固定时间事项；价格条件仍随行情判断，事件条件见主报告";
    wrap.append(note);
    return wrap;
  }
  // The detail drawer is the place for every locked condition.  Table rows
  // deliberately stay short so the decision page remains a usable scan.
  const visibleTasks = tasks;
  for (const task of visibleTasks) {
    const taskWrap = document.createElement("div");
    taskWrap.className = `human-review-task human-review-task-${task.date_status || "unknown"}`;
    const heading = document.createElement("strong");
    heading.textContent = `${task.scope_label || "复核事项"} · ${task.title || "主报告条件"}`;
    taskWrap.append(heading);
    const content = document.createElement("p");
    content.textContent = task.content || "主报告未提供具体复核内容";
    taskWrap.append(content);
    if (task.metrics?.length) {
      const metrics = document.createElement("p");
      metrics.className = "human-review-note";
      metrics.textContent = `关注指标：${task.metrics.join("、")}`;
      taskWrap.append(metrics);
    }
    const schedule = document.createElement("p");
    schedule.className = "human-review-note";
    schedule.textContent = humanReviewTaskDateText(task);
    taskWrap.append(schedule);
    if (!compact) {
      const source = document.createElement("p");
      source.className = "human-review-note";
      source.textContent = `来源：${humanReviewTaskSourceLabel(task)}${task.evidence?.[0]?.line_start ? ` · 主报告第 ${task.evidence[0].line_start} 行起` : ""}`;
      taskWrap.append(source);
    }
    wrap.append(taskWrap);
  }
  return wrap;
}

function renderHumanReviewState(item, quote) {
  const result = humanReviewForItem(item, quote);
  const wrap = document.createElement("div");
  wrap.className = `human-review-state human-review-state-${result.key}`;
  const label = document.createElement("strong");
  label.textContent = result.label;
  const detail = document.createElement("p");
  detail.textContent = result.detail;
  wrap.append(label, detail);
  if (result.judgment?.label) {
    const judgment = document.createElement("p");
    judgment.className = "human-review-note";
    judgment.textContent = `主报告判断：${result.judgment.label}`;
    wrap.append(judgment);
  }
  const freshness = result.freshness;
  if (freshness?.timestamp) {
    const snapshot = document.createElement("p");
    snapshot.className = "human-review-note";
    snapshot.textContent = `行情快照：${attentionTimestamp(freshness.timestamp)}${freshness.state === "fresh" ? " · 新鲜" : " · 已过期"}`;
    wrap.append(snapshot);
  }
  const plan = humanReviewPlanForItem(item);
  const planMeta = document.createElement("p");
  planMeta.className = "human-review-note";
  if (plan?.status === "ready" && plan.task_count) {
    const next = plan.tasks?.[0];
    planMeta.textContent = `固定复核 ${plan.task_count} 项${plan.due_count ? ` · ${plan.due_count} 项已到期待确认` : ""}${next ? ` · 最近：${next.title} · ${next.status_label || "待确认"}${next.next_review_date ? ` · ${next.next_review_date}` : ""}` : ""}`;
  } else if (plan?.status === "ready") {
    planMeta.textContent = "固定复核：暂无事项，价格条件随行情判断";
  } else {
    planMeta.textContent = "固定复核：人工主报告计划不可用";
  }
  wrap.append(planMeta);
  return wrap;
}

function renderHumanReviewMainCell(item, quote) {
  const result = humanReviewForItem(item, quote);
  const wrap = document.createElement("div");
  wrap.className = `human-review-main human-review-main-${result.key}`;

  const header = document.createElement("div");
  header.className = "human-review-main-header";
  const label = document.createElement("strong");
  label.className = "human-review-main-label";
  label.textContent = result.label;
  header.append(label);
  wrap.append(header);

  const detail = document.createElement("p");
  detail.className = "human-review-main-detail";
  detail.textContent = result.detail;
  wrap.append(detail);

  if (result.judgment?.label) {
    const judgment = document.createElement("p");
    judgment.className = "human-review-main-muted";
    judgment.textContent = `主报告：${result.judgment.label}`;
    wrap.append(judgment);
  }

  const freshness = result.freshness;
  const snapshot = document.createElement("p");
  snapshot.className = "human-review-main-muted";
  if (freshness?.timestamp) {
    snapshot.textContent = `行情 ${attentionTimestamp(freshness.timestamp)} · ${freshness.state === "fresh" ? "新鲜" : "已过期"}`;
  } else {
    snapshot.textContent = "行情快照：缺失";
  }
  wrap.append(snapshot);

  return wrap;
}

function renderExecutionMainCell(item, quote) {
  const fallback = buyAdviceForItem(item, quote);
  const execution = currentExecutionState(item, quote, fallback.key);
  const wrap = document.createElement("div");
  wrap.className = `execution-main execution-main-${execution.key}`;
  const label = document.createElement("strong");
  label.textContent = `当前：${execution.label}`;
  wrap.append(label);
  const detail = document.createElement("p");
  if (execution.key === "paused" && execution.referenceExecution) {
    detail.textContent = `最近参考：${execution.referenceExecution.label} · 下个交易日重新核对`;
  } else {
    detail.textContent = execution.detail;
  }
  wrap.append(detail);
  if (execution.rule?.price_range) {
    const rule = document.createElement("span");
    rule.className = "execution-main-rule";
    rule.textContent = `报告价格带 ${execution.rule.price_range}`;
    wrap.append(rule);
  }
  return wrap;
}

function renderIdentityCell(item) {
  const cell = document.createElement("td");
  cell.className = "company-cell company-identity-cell";
  const companyName = document.createElement("div");
  companyName.className = "company-name";
  companyName.textContent = item.company;
  const marketLine = document.createElement("div");
  marketLine.className = "company-identity-meta";
  const marketBadge = document.createElement("span");
  marketBadge.className = `market-badge ${marketBadgeClass(item.market)}`;
  marketBadge.textContent = item.market || "未识别";
  const tickerCode = document.createElement("span");
  tickerCode.className = "ticker-code";
  tickerCode.textContent = item.ticker || "无代码";
  marketLine.append(marketBadge, tickerCode);
  const sentiment = sentimentForItem(item)?.combined_sentiment;
  const sentimentLine = document.createElement("span");
  sentimentLine.className = `company-sentiment ${sentimentTone(sentiment?.score_0_100)}`;
  sentimentLine.textContent = `情绪 ${sentimentScoreText(sentimentDisplayScore(sentiment))} · ${sentimentDisplayState(sentiment)}`;
  cell.append(companyName, marketLine, sentimentLine);
  return cell;
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

const fundamentalReviewStatusMeta = {
  redline: { label: "红线已触发", tone: "redline", rank: 80 },
  stale_rules: { label: "规则已失效", tone: "stale", rank: 70 },
  attention: { label: "需要关注", tone: "attention", rank: 60 },
  evidence_ready: { label: "已有数据 · 待判定", tone: "gap", rank: 55 },
  data_gap: { label: "存在数据缺口", tone: "gap", rank: 50 },
  waiting_evidence: { label: "等待新证据", tone: "waiting", rank: 40 },
  error: { label: "复核失败", tone: "stale", rank: 35 },
  historical_review: { label: "上一轮日常复核", tone: "historical", rank: 32 },
  improving: { label: "改善条件命中", tone: "improving", rank: 30 },
  no_rules: { label: "暂无经营规则", tone: "waiting", rank: 20 },
  clear: { label: "暂无确认红线", tone: "clear", rank: 10 },
};

const manualReviewStatusMeta = {
  active: { label: "人工规则有效", tone: "manual-active" },
  stale: { label: "待人工更新", tone: "stale" },
  no_rules: { label: "暂无人工规则", tone: "waiting" },
};

function fundamentalReviewForItem(item) {
  return state.fundamentalReviews.get(item?.ticker) || null;
}

function modelReviewForItem(item) {
  return fundamentalReviewForItem(item);
}

function manualReviewMeta(review) {
  const status = review?.manual?.status
    || (review?.rule_state === "stale" ? "stale" : (review?.rules?.length ? "active" : "no_rules"));
  return { status, ...(manualReviewStatusMeta[status] || manualReviewStatusMeta.no_rules) };
}

function routineReviewMeta(review) {
  const status = review?.routine?.status
    || (review?.rule_state === "stale" ? "stale_rules" : (review?.summary?.status || "waiting_evidence"));
  return { status, ...(fundamentalReviewStatusMeta[status] || fundamentalReviewStatusMeta.waiting_evidence) };
}

// Kept as the review-view sorting/filtering accessor.  This is intentionally
// the daily evidence layer, not the human rule authority.
function fundamentalReviewMeta(review) {
  return routineReviewMeta(review);
}

// A review screen needs one clear home for each stock.  Manual-rule staleness
// takes priority over any saved daily result, so historical data is never
// mistaken for a still-valid rule outcome.
function fundamentalReviewPartitionKey(review) {
  if (!review || review.rule_state === "stale") return "stale_rules";
  const layerStatuses = [review.daily?.current?.status, review.deep?.current?.status, review.summary?.status];
  if (layerStatuses.includes("redline")) return "redline";
  if (layerStatuses.includes("attention")) return "attention";
  const now = Date.now();
  const dailyDue = new Date(review.daily?.due_at || 0).getTime();
  const deepDue = new Date(review.deep?.due_at || 0).getTime();
  if (Number.isFinite(dailyDue) && dailyDue <= now) return "daily_due";
  if (Number.isFinite(deepDue) && deepDue <= now) return "deep_due";
  if (layerStatuses.some((status) => ["data_gap", "waiting_evidence", "error"].includes(status))) return "data_gap";
  return "clear";
}

const fundamentalReviewPartitions = [
  ["redline", "红线已触发", "锁定负向条件已有当前证据支持；需要打开详情核对原文。", "redline"],
  ["attention", "需要关注", "持仓验证或条件未满足，尚不改变主报告判断。", "attention"],
  ["daily_due", "日常待复核", "日常层每三天到期；由你手动启动 DeepSeek。", "attention"],
  ["deep_due", "深度待复核", "深度层每三十天到期；由你选择模型和推理档位。", "attention"],
  ["data_gap", "数据不足", "当前证据不完整，不能用主报告历史基线补写结论。", "historical"],
  ["stale_rules", "规则失效", "主报告已更新，等待人工重新锁定规则。", "stale"],
  ["clear", "暂无预警", "暂无确认红线或到期任务。", "improving"],
];

function modelReviewTaskStatus(task) {
  if ((task?.status || task?.truth_state) === "unknown" && task?.disclosure_state === "not_disclosed") {
    return "官方未披露";
  }
  return ({
    verified: "已验证", not_triggered: "未触发", triggered: "有触发", data_insufficient: "数据不足",
    met: "条件满足", not_met: "条件未满足", unknown: "证据未闭合", not_due: "尚未到期",
  })[task?.status || task?.truth_state] || "未完成";
}

function modelReviewEvidenceLabel(task) {
  return task?.evidence_quality === "current" ? "当前证据" : task?.evidence_quality === "historical" ? "仅主报告/历史" : "无证据";
}

function modelReviewPartitionRank(review) {
  return ({ redline: 7, stale_rules: 6, attention: 5, daily_due: 4, deep_due: 3, data_gap: 2, clear: 1 })[fundamentalReviewPartitionKey(review)] || 0;
}

function setFundamentalReviewFilter(filter) {
  state.fundamentalReviewFilter = filter || "all";
  resetRowPage();
  els.fundamentalReviewFilterRow?.querySelectorAll(".chip").forEach((node) => {
    node.classList.toggle("active", node.dataset.fundamentalReviewFilter === state.fundamentalReviewFilter);
  });
  renderAll();
}

function renderFundamentalReviewPartitions() {
  const root = els.fundamentalReviewPartitions;
  if (!root) return;
  root.hidden = state.view !== "review";
  root.replaceChildren();
  if (state.view !== "review") return;

  const reviews = state.decisions
    .filter((item) => item.market === "A股")
    .map((item) => fundamentalReviewForItem(item));
  const counts = reviews.reduce((total, review) => {
    const key = fundamentalReviewPartitionKey(review);
    total[key] = (total[key] || 0) + 1;
    return total;
  }, {});

  const head = document.createElement("div");
  head.className = "fundamental-review-partitions-head";
  const copy = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "REPORT REVIEW QUEUE";
  const title = document.createElement("h2");
  title.textContent = "主报告复核队列";
  const note = document.createElement("p");
  note.textContent = "日常层由 DeepSeek 手动复核；深度层由你每次指定模型和推理档位。两层均只核对锁定规则，不改变买入前决策。";
  copy.append(eyebrow, title, note);
  const total = document.createElement("span");
  total.className = "fundamental-review-partitions-total";
  total.textContent = `${reviews.length} 只 A 股`;
  head.append(copy, total);
  root.append(head);

  const grid = document.createElement("div");
  grid.className = "fundamental-review-partition-grid";
  for (const [key, titleText, detail, tone] of fundamentalReviewPartitions) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `fundamental-review-partition partition-${tone}${state.fundamentalReviewFilter === key ? " active" : ""}`;
    card.setAttribute("aria-pressed", String(state.fundamentalReviewFilter === key));
    const count = document.createElement("strong");
    count.textContent = String(counts[key] || 0);
    const label = document.createElement("span");
    label.textContent = titleText;
    const explanation = document.createElement("small");
    explanation.textContent = detail;
    card.append(count, label, explanation);
    card.addEventListener("click", () => setFundamentalReviewFilter(key));
    grid.append(card);
  }
  root.append(grid);
}

function fundamentalReviewRules(review, group = null) {
  return (review?.rules || []).filter((rule) => !group || (rule.semantic_group || rule.group) === group);
}

function activeReviewResultRules(review, effect) {
  return fundamentalReviewRules(review).filter((rule) => rule?.result?.review_effect === effect);
}

function reviewScheduleLabel(rule) {
  const period = (rule?.periods || []).join(" / ");
  const labels = {
    filing: "对应财报披露后",
    recurring_filing: "每期财报披露后",
    event: "事件触发后",
    price: "价格分区处理",
  };
  return [period, labels[rule?.schedule_type] || "待人工安排"].filter(Boolean).join(" · ");
}

function reviewTruthLabel(result) {
  return {
    met: "条件满足",
    not_met: "条件未满足",
    unknown: "数据不足",
    not_due: "尚未到期",
  }[result?.truth_state] || "尚未核验";
}

function shortReviewDate(value) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(date);
}

function appendReviewBadge(parent, review) {
  const meta = routineReviewMeta(review);
  const badge = document.createElement("span");
  badge.className = `fundamental-review-badge fundamental-review-badge-${meta.tone}`;
  badge.textContent = meta.label;
  parent.append(badge);
  return badge;
}

function appendManualReviewBadge(parent, review) {
  const meta = manualReviewMeta(review);
  const badge = document.createElement("span");
  badge.className = `fundamental-review-badge fundamental-review-badge-${meta.tone}`;
  badge.textContent = meta.label;
  parent.append(badge);
  return badge;
}

function conciseRuleCondition(rule) {
  const text = String(rule?.condition || "主报告未给出具体条件");
  return text.length > 92 ? `${text.slice(0, 92)}…` : text;
}

function reviewGapLabels(review) {
  const mapping = {
    current_price: "当前价格",
    current_value: "当前值",
    comparison: "对比期",
    official_source: "官方来源",
    event_confirmation: "事件确认",
  };
  const requirements = review?.summary?.missing_requirements || [];
  return [...new Set(requirements.map((value) => mapping[value] || value))];
}

function filteredDecisions() {
  const phrase = els.companyFilter.value.trim().toLocaleLowerCase();
  // Advice / execution states are expensive to compute; cache one value per
  // item for this pass so the sort comparator does not recompute them O(n log n) times.
  const adviceCache = new Map();
  const executionCache = new Map();
  const referenceCache = new Map();
  const humanReviewCache = new Map();
  const adviceFor = (item) => {
    const key = itemKey(item);
    if (!adviceCache.has(key)) adviceCache.set(key, buyAdviceForItem(item, state.quotes.get(item.ticker)));
    return adviceCache.get(key);
  };
  const executionFor = (item) => {
    const key = itemKey(item);
    if (!executionCache.has(key)) {
      executionCache.set(key, currentExecutionState(item, state.quotes.get(item.ticker), adviceFor(item).key));
    }
    return executionCache.get(key);
  };
  const referenceFor = (item) => {
    const key = itemKey(item);
    if (!referenceCache.has(key)) {
      referenceCache.set(key, referenceExecutionState(item, state.quotes.get(item.ticker), adviceFor(item).key));
    }
    return referenceCache.get(key);
  };
  const humanReviewFor = (item) => {
    const key = itemKey(item);
    if (!humanReviewCache.has(key)) {
      humanReviewCache.set(key, humanReviewForItem(item, state.quotes.get(item.ticker)));
    }
    return humanReviewCache.get(key);
  };
  let list = state.decisions.filter((item) => {
    const marketMatch = state.view === "review"
      ? item.market === "A股"
      : (state.market === "all" || item.market === state.market);
    const tracking = trackingForItem(item);
    const advice = adviceFor(item);
    const adviceMatch = state.action === "all"
      || executionFor(item).key === state.action;
    const referenceMatch = state.referenceAction === "all" || referenceFor(item).key === state.referenceAction;
    const humanReviewMatch = state.humanReviewAction === "all"
      || humanReviewFor(item).key === state.humanReviewAction;
    const fundamentalReview = modelReviewForItem(item);
    const fundamentalReviewMatch = state.view !== "review"
      || state.fundamentalReviewFilter === "all"
      || fundamentalReviewPartitionKey(fundamentalReview) === state.fundamentalReviewFilter;
    const trackingMatch = state.view !== "tracking"
      || (tracking && (
        state.trackingFilter === "all"
        || (state.trackingFilter === "alert" && trackingAlertLevel(tracking) !== "none")
        || (state.trackingFilter === "review" && trackingNeedsReview(tracking))
      ));
    const searchable = `${item.company} ${item.ticker || ""} ${item.title || ""}`.toLocaleLowerCase();
    return marketMatch
      && (state.view === "decision" ? adviceMatch : true)
      && (state.view === "decision" ? referenceMatch : true)
      && (state.view === "decision" ? humanReviewMatch : true)
      && fundamentalReviewMatch
      && trackingMatch
      && (!phrase || searchable.includes(phrase));
  });

  list = [...list].sort((a, b) => {
    if (state.view === "review") {
      const rankDelta = modelReviewPartitionRank(modelReviewForItem(b)) - modelReviewPartitionRank(modelReviewForItem(a));
      if (rankDelta) return rankDelta;
      return a.company.localeCompare(b.company, "zh");
    }
    if (state.view === "tracking") {
      const aa = trackingForItem(a);
      const bb = trackingForItem(b);
      const alertRank = { critical: 3, warning: 2, none: 1 };
      const alertDelta = (alertRank[trackingAlertLevel(bb)] || 0) - (alertRank[trackingAlertLevel(aa)] || 0);
      if (alertDelta) return alertDelta;
      return String(aa?.next_review_date || "9999-12-31").localeCompare(String(bb?.next_review_date || "9999-12-31"));
    }
    if (state.sort === "execution") {
      const aa = executionFor(a);
      const bb = executionFor(b);
      const d = (bb.rank || 0) - (aa.rank || 0);
      if (d) return d;
      return a.company.localeCompare(b.company, "zh");
    }
    if (state.sort === "reference") {
      const aa = referenceFor(a);
      const bb = referenceFor(b);
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
      const aa = adviceFor(a);
      const bb = adviceFor(b);
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
  if (els.liveStatus) {
    els.liveStatus.dataset.mode = mode;
    els.liveStatus.title = text;
  }
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
    els.indexBandMeta.textContent = `${records.length}/${A_SHARE_INDEX_WATCH.length} 个指数 · ${state.quoteUpdatedAt ? quoteSnapshotStatusText() : "时间待复核"}`;
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
  const generatedAt = payload?.generated_at;
  if (!generatedAt || !Number.isFinite(new Date(generatedAt).getTime())) {
    throw new Error("snapshot timestamp invalid");
  }
  if (!Array.isArray(payload.quotes)) throw new Error("snapshot quotes invalid");

  const nextQuotes = new Map();
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
    nextQuotes.set(quote.ticker, {
      ...quote,
      price,
      previous_close: previous,
      change_pct: changePct,
      source: quote.source || "snapshot",
      snapshot_generated_at: generatedAt,
    });
    count += 1;
  }
  if (!count) throw new Error("snapshot contains no valid quotes");

  const nextIndices = new Map();
  for (const index of payload.indices || []) {
    if (!index?.ticker || !Number.isFinite(Number(index.price))) continue;
    const previous = Number(index.previous_close);
    const price = Number(index.price);
    const changePct = Number.isFinite(Number(index.change_pct))
      ? Number(index.change_pct)
      : Number.isFinite(previous) && previous > 0
        ? ((price - previous) / previous) * 100
        : null;
    nextIndices.set(index.index_id || index.ticker, {
      ...index,
      price,
      previous_close: previous,
      change_pct: changePct,
      source: index.source || "snapshot",
      snapshot_generated_at: generatedAt,
    });
  }

  // Replace the complete snapshot only after validating it. This prevents a
  // partial provider response from silently mixing new and old prices.
  state.quotes = nextQuotes;
  state.indices = nextIndices;
  state.quoteUpdatedAt = generatedAt;
  state.quoteSnapshotMeta = {
    generatedAt,
    source: payload.quotes.find((quote) => quote?.source)?.source || "snapshot",
    marketStatus: payload.market_status || "unknown",
    requestedMarkets: Array.isArray(payload.requested_markets) ? payload.requested_markets : [],
    trackedCount: Number(payload.tracked_count) || count,
    quoteCount: count,
    indexCount: nextIndices.size,
  };
  renderIndexCards();
  return count;
}

function quoteSnapshotAgeMinutes(timestamp, now = new Date()) {
  const observed = new Date(timestamp || "");
  const current = now instanceof Date ? now : new Date(now);
  if (!Number.isFinite(observed.getTime()) || !Number.isFinite(current.getTime())) return null;
  return Math.max(0, (current.getTime() - observed.getTime()) / 60_000);
}

function quoteSnapshotAgeText(timestamp) {
  const age = quoteSnapshotAgeMinutes(timestamp);
  if (age === null) return "时间未知";
  if (age < 1) return "刚刚";
  if (age < 60) return `约${Math.max(1, Math.round(age))}分钟前`;
  if (age < 1440) return `约${Math.floor(age / 60)}小时前`;
  return `约${Math.floor(age / 1440)}天前`;
}

function quoteSnapshotStatusText() {
  if (!state.quoteUpdatedAt) return "行情快照未加载";
  const count = state.quoteSnapshotMeta?.quoteCount || state.quotes.size;
  const age = quoteSnapshotAgeMinutes(state.quoteUpdatedAt);
  const freshness = age !== null && age > 10 ? "行情陈旧" : "行情快照";
  const timestamp = new Date(state.quoteUpdatedAt).toLocaleString();
  return `${freshness} · ${count}只 · ${quoteSnapshotAgeText(state.quoteUpdatedAt)} · ${timestamp}`;
}

async function refreshQuotes({ silent = false } = {}) {
  try {
    const snapCount = await loadSnapshotQuotes();
    setLiveStatus("snapshot", quoteSnapshotStatusText());
    renderAll();
    if (!silent) showToast(`已加载行情快照 ${snapCount} 只`);
  } catch (error) {
    const previous = state.quoteUpdatedAt
      ? `；保留上次成功快照（${quoteSnapshotStatusText()}）`
      : "；暂无可用旧快照";
    setLiveStatus("error", `行情加载失败 · ${error.message}${previous}`);
    if (!silent) showToast("行情刷新失败");
  }
}

function startQuoteTimers() {
  clearInterval(state.liveTimer);
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

function safeExternalHref(url) {
  const value = String(url || "").trim();
  return /^https?:\/\//i.test(value) ? value : "";
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

function opportunityScanForItem(item) {
  if (item?.market !== "A股") return { status: "missing" };
  return state.opportunityScans.get(item?.ticker) || { status: "missing" };
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

function renderTechnicalCell(item, { includeCross = false } = {}) {
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
  if (includeCross) {
    const hasFundamentalPlan = !/未提取|无法核验/.test(String(technical.fundamental_entry_plan || ""));
    const combined = compactTechnicalZone(technical.combined_candidate_zone);
    const cross = document.createElement("span");
    cross.className = "technical-cross-brief";
    if (technical.status !== "ready") {
      cross.textContent = "技术价 / 基本面交叉：待复核";
    } else if (!technical.combined_candidate_zone || !hasFundamentalPlan || technical.valid_buy_candidate === "暂不能判断") {
      cross.textContent = `技术价 ${compactTechnicalZone(technical.observation_zone)} · 交叉待复核`;
    } else if (/无交集/.test(combined)) {
      cross.textContent = `技术价 ${compactTechnicalZone(technical.observation_zone)} · 无交集`;
    } else {
      cross.textContent = `基本面交叉 ${combined}`;
    }
    cell.append(cross);
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
    const lightLabel = document.createElement("span");
    lightLabel.textContent = `${label}期`;
    const signal = document.createElement("strong");
    signal.className = light?.light === "绿" ? "green" : light?.light === "黄" ? "yellow" : "red";
    signal.textContent = light?.light || "待复核";
    itemNode.append(lightLabel, signal);
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
    const href = safeExternalHref(item.url);
    const titleNode = href ? document.createElement("a") : document.createElement("strong");
    titleNode.textContent = item.title || "无标题新闻";
    if (href) {
      titleNode.href = href;
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
    warning.textContent = "已识别硬性否决信号：请你结合完整 Checklist 自行复核；它不会自动改写当前价格分区或主研报动作。";
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
  footer.textContent = "Checklist 保留为独立买入前参考，由你自行复核；不参与当前价格分区，也不覆盖基本面主研报、技术面或情绪面的独立结论。";
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
  const manual = manualReviewIsFreshForScan(item) ? item?.manual_execution_review : null;
  if (manual?.status === "ready" && manual?.source === "human_review") {
    const tier = manual.opportunity_tier;
    if (['current', 'near'].includes(tier)) {
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
    // A manual review older than the latest Flash scan must not suppress the
    // new daily result. Only a review completed after that scan overrides it.
  }
  const scan = opportunityScanForItem(item);
  const union = scan?.union || {};
  const quote = state.quotes.get(item.ticker);
  const judgment = primaryJudgmentForItem(item);
  const allModels = Object.entries(scan.models || {})
    .filter(([, result]) => result && ["ready", "stale"].includes(result.status));
  // A failed refresh may retain stale results for audit, but stale output must
  // never promote a stock into today's opportunity panel.
  const models = allModels.filter(([, result]) => result.status === "ready");
  const normalizeState = (value) => ({
    "机会": "当前机会",
    "条件机会": "临近机会",
    "暂不构成机会": "暂不构成当前机会",
  })[value] || value;
  const currentModels = models.filter(([, result]) => normalizeState(result.assessment?.opportunity_state) === "当前机会");
  const nearModels = models.filter(([, result]) => normalizeState(result.assessment?.opportunity_state) === "临近机会");
  const tier = currentModels.length ? "current" : nearModels.length ? "near" : null;
  if (!tier) return null;
  const confidenceScore = models.reduce((score, [, result]) => {
    const confidence = result.assessment?.confidence;
    return score + (confidence === "high" ? 2 : confidence === "medium" ? 1 : 0);
  }, 0);
  const staleModels = allModels.filter(([, result]) => result.status === "stale");
  const priority = (tier === "current" ? 20 : 10) + confidenceScore;
  return {
    item,
    scan,
    union,
    models,
    quote,
    judgment,
    staleModels,
    relevantModels: tier === "current" ? currentModels : nearModels,
    priority,
    tier,
    label: tier === "current" ? "当前机会" : "临近机会",
    tone: tier === "near" ? "notice" : "opportunity",
  };
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
  open.textContent = "查看个股详情";
  open.addEventListener("click", (event) => {
    event.stopPropagation();
    openDetail(item);
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
  if (!els.attentionPanel || !els.attentionList || state.view !== "decision") {
    if (els.attentionPanel) els.attentionPanel.hidden = true;
    return;
  }

  const aShares = state.decisions.filter((item) => item.market === "A股");
  const manualReviews = aShares.filter((item) => manualReviewIsFreshForScan(item));
  const scans = aShares.map((item) => opportunityScanForItem(item));
  const modelResults = scans.flatMap((scan) => Object.values(scan?.models || {}));
  const readyModelResults = modelResults.filter((result) => result?.status === "ready");
  const candidates = aShares
    .map(opportunityCandidateForItem)
    .filter(Boolean)
    .sort((a, b) => b.priority - a.priority || a.item.company.localeCompare(b.item.company, "zh"));
  const currentCandidates = candidates.filter((candidate) => candidate.tier === "current");
  const nearCandidates = candidates.filter((candidate) => candidate.tier === "near");

  els.attentionPanel.hidden = false;
  const scanStatus = state.opportunityScanStatus;
  const freshness = state.opportunityScansGeneratedAt
    ? ` · 快照 ${attentionTimestamp(state.opportunityScansGeneratedAt)}`
    : "";
  const failure = ["error", "partial"].includes(scanStatus?.status) && !readyModelResults.length;
  const failureNote = failure
    ? ` · 本次失败，沿用${scanStatus.last_success_scan_generated_at ? `${attentionTimestamp(scanStatus.last_success_scan_generated_at)}的` : "上次成功的"}结果`
    : "";
  const expectedModelResults = aShares.length * Math.max(1, state.opportunityScanModels.length);
  const fullManualCoverage = manualReviews.length === aShares.length && aShares.length > 0
    && manualReviews.every((item) => ["current", "near"].includes(item.manual_execution_review?.opportunity_tier));
  const metaText = fullManualCoverage
    ? `人工确认 ${currentCandidates.length} · 临近 ${nearCandidates.length} · ${manualReviews.length}/${aShares.length}`
    : `每日扫描当前 ${currentCandidates.length} · 临近 ${nearCandidates.length} · Flash ${readyModelResults.length}/${expectedModelResults}${freshness}${failureNote}`;
  els.attentionMeta.textContent = metaText;
  els.attentionMeta.dataset.status = fullManualCoverage ? "ready" : (failure ? "error" : (scanStatus?.status || "ready"));
  if (els.attentionToggleMeta) {
    els.attentionToggleMeta.textContent = fullManualCoverage
      ? `人工确认 ${manualReviews.length} 只 · 当前 ${currentCandidates.length} · 临近 ${nearCandidates.length}`
      : failure
      ? `本次扫描失败 · 沿用上次成功结果 · ${candidates.length} 项候选`
      : `每日扫描 · 当前 ${currentCandidates.length} · 临近 ${nearCandidates.length}${freshness}`;
    els.attentionToggleMeta.dataset.status = fullManualCoverage ? "ready" : (failure ? "error" : (scanStatus?.status || "ready"));
  }
  if (els.attentionToggleState) els.attentionToggleState.textContent = els.attentionPanel.open ? "收起" : "展开";
  els.attentionList.replaceChildren();

  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.className = "attention-empty";
    empty.textContent = failure
      ? "本次收盘后机会扫描失败，当前继续沿用上次成功结果。"
      : readyModelResults.length ? "当前每日扫描没有筛出值得立即决策的机会。" : "每日机会扫描结果尚未加载，暂不生成机会面板。";
    els.attentionList.append(empty);
    return;
  }

  if (currentCandidates.length) {
    els.attentionList.append(renderOpportunityGroup(
      currentCandidates,
      fullManualCoverage ? "人工机会" : "当前机会",
      fullManualCoverage ? "周末人工确认结果优先；是否行动仍由你判断。" : "每日 Flash 扫描已说明为什么是现在；是否行动仍由你判断。",
    ));
  } else {
    const emptyCurrent = document.createElement("p");
    emptyCurrent.className = "attention-empty attention-current-empty";
    emptyCurrent.textContent = "当前没有满足“为什么是现在”的机会。";
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
  if (state.view === "review") {
    const reviews = visible.map(fundamentalReviewForItem).filter(Boolean);
    const counts = reviews.reduce((acc, review) => {
      const routineStatus = routineReviewMeta(review).status;
      const manualStatus = manualReviewMeta(review).status;
      acc[routineStatus] = (acc[routineStatus] || 0) + 1;
      acc[`manual_${manualStatus}`] = (acc[`manual_${manualStatus}`] || 0) + 1;
      return acc;
    }, {});
    const metrics = [
      ["人工规则覆盖", reviews.length],
      ["人工规则有效", counts.manual_active || 0],
      ["待人工更新", counts.manual_stale || 0],
      ["日常红线", counts.redline || 0],
      ["日常关注", counts.attention || 0],
      ["日常改善", counts.improving || 0],
      ["上一轮日常复核", counts.historical_review || 0],
      ["日常数据不足", (counts.data_gap || 0) + (counts.evidence_ready || 0)],
      ["日常等待证据", counts.waiting_evidence || 0],
      ["日常复核失败", counts.error || 0],
      ["下次增量探测", shortReviewDate(state.fundamentalReviewSnapshot?.next_check_at)],
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
  const metrics = [
    ["当前个股", visible.length],
    ["A股研究", aShareVisible.length],
    ["当前可买/小仓", (counts.actionable || 0) + (counts.trial || 0)],
    ["下个交易日候选", nextCandidateCount],
    ["价格已到待验证", counts.validation || 0],
    ["待人工复核", manualReviewCount],
    ["行情/时段暂停", counts.paused || 0],
    ["最近参考可买/小仓", (referenceCounts.actionable || 0) + (referenceCounts.trial || 0)],
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
  els.decisionTable.classList.toggle("fundamental-review-table", state.view === "review");
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
    const companyName = document.createElement("div");
    companyName.className = "company-name";
    companyName.textContent = item.company;
    const companyMeta = document.createElement("div");
    companyMeta.className = "company-meta";
    companyMeta.textContent = `${item.market || "未识别"} · ${item.ticker || "无代码"}`;
    companyTd.append(companyName, companyMeta);
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

function appendFundamentalRuleList(cell, rules, emptyText) {
  if (!rules.length) {
    const empty = document.createElement("p");
    empty.className = "fundamental-review-empty";
    empty.textContent = emptyText;
    cell.append(empty);
    return;
  }
  const list = document.createElement("div");
  list.className = "fundamental-review-rule-list";
  for (const rule of rules.slice(0, 2)) {
    const item = document.createElement("div");
    item.className = `fundamental-review-rule-brief fundamental-review-rule-${rule.group || "holder"}`;
    const condition = document.createElement("strong");
    condition.textContent = conciseRuleCondition(rule);
    const meta = document.createElement("span");
    meta.textContent = `${reviewTruthLabel(rule.result)} · ${reviewScheduleLabel(rule)}`;
    item.append(condition, meta);
    list.append(item);
  }
  if (rules.length > 2) {
    const more = document.createElement("span");
    more.className = "fundamental-review-more";
    more.textContent = `另有 ${rules.length - 2} 项，点开查看`;
    list.append(more);
  }
  cell.append(list);
}

function renderManualReviewCell(review) {
  const cell = document.createElement("td");
  cell.className = "fundamental-review-layer-cell manual-review-cell";
  cell.dataset.label = "人工锁定规则";
  if (!review) {
    cell.textContent = "人工规则快照未生成";
    return cell;
  }
  const manual = review.manual || {};
  appendManualReviewBadge(cell, review);
  const source = document.createElement("p");
  source.className = "fundamental-review-meta";
  source.textContent = manual.source || "人工主报告裁决与锁定规则";
  const count = document.createElement("p");
  count.className = "fundamental-review-meta muted";
  count.textContent = `${manual.rule_count ?? review.rules?.length ?? 0} 条锁定规则 · ${manual.reviewable_rule_count ?? 0} 条可日常核验`;
  const reviewed = document.createElement("p");
  reviewed.className = "fundamental-review-meta muted";
  reviewed.textContent = `人工确认：${shortReviewDate(manual.reviewed_at || review.main_report?.reviewed_at)}`;
  const audit = document.createElement("p");
  audit.className = "fundamental-review-meta muted";
  audit.textContent = `${manual.audit_candidate_count ?? review.audit_candidates?.length ?? 0} 条 ZCode 审计候选未启用`;
  cell.append(source, count, reviewed, audit);
  const direct = manual.codex_direct;
  if (direct) {
    const current = document.createElement("p");
    current.className = "fundamental-review-meta routine-review-warning";
    current.textContent = `今日 Codex 直接复核：${direct.label || direct.status} · ${direct.evidence_count ?? 0} 份证据`;
    cell.append(current);
  }
  return cell;
}

function renderRoutineReviewCell(review) {
  const cell = document.createElement("td");
  cell.className = "fundamental-review-layer-cell routine-review-cell";
  cell.dataset.label = "日常证据复核";
  if (!review) {
    cell.textContent = "日常复核快照未生成";
    return cell;
  }
  const routine = review.routine || {};
  appendReviewBadge(cell, review);
  const reviewer = document.createElement("p");
  reviewer.className = "fundamental-review-meta";
  reviewer.textContent = routine.reviewer || "DeepSeek 日常核验";
  const evidence = document.createElement("p");
  evidence.className = "fundamental-review-meta muted";
  const isHistorical = routineReviewMeta(review).status === "historical_review";
  evidence.textContent = isHistorical
    ? `保存的本地证据 ${routine.current_evidence_count ?? 0} 份 · 非实时结果`
    : `新证据 ${routine.current_evidence_count ?? review.current_evidence_count ?? 0} 份 · 最近 ${routine.latest_evidence_date || review.latest_evidence_date || "未记录"}`;
  const next = document.createElement("p");
  next.className = "fundamental-review-meta muted";
  next.textContent = `上次 ${shortReviewDate(routine.generated_at || review.generated_at)} · 下次 ${shortReviewDate(review.next_check_at || state.fundamentalReviewSnapshot?.next_check_at)}`;
  const zcodeCount = (review.evidence_documents || [])
    .filter((document) => document.source_role === "zcode_current_evidence_extract").length;
  const legacyTasks = routine.legacy_daily?.tasks || [];
  if (legacyTasks.length) {
    const historical = document.createElement("p");
    historical.className = "fundamental-review-meta routine-review-history";
    const taskLabels = { entry: "买入前提", holder: "持仓验证", risk: "原始风险任务" };
    const statusLabels = { verified: "已验证", not_triggered: "未触发", triggered: "有触发", data_insufficient: "数据不足" };
    historical.textContent = `历史任务：${legacyTasks.map((task) => `${taskLabels[task.task_id] || task.task_id} ${statusLabels[task.status] || task.status}`).join(" · ")}`;
    cell.append(reviewer, evidence, next, historical);
  } else if (routineReviewMeta(review).status === "error") {
    const failed = document.createElement("p");
    failed.className = "fundamental-review-meta routine-review-warning";
    failed.textContent = zcodeCount
      ? `本次日常复核未完成；保留 ${zcodeCount} 条 ZCode 事实，未继承旧结论。`
      : "本次日常复核未完成；不会用主报告旧内容代替当前结论。";
    cell.append(reviewer, evidence, next, failed);
  } else {
    cell.append(reviewer, evidence, next);
  }
  const strict = routine.strict_incremental;
  if (isHistorical && strict?.status && strict.status !== "waiting_evidence") {
    const strictNote = document.createElement("p");
    strictNote.className = "fundamental-review-meta routine-review-warning";
    strictNote.textContent = `严格增量核验：${strict.label || strict.status}；不覆盖历史任务。`;
    cell.append(strictNote);
  }
  return cell;
}

function reportReviewAlert(review) {
  if (!review) {
    return {
      label: "复核快照缺失",
      detail: "尚未加载 ZCode 与 DeepSeek 的对照快照。",
      tone: "gap",
    };
  }
  const partition = fundamentalReviewPartitionKey(review);
  const meta = fundamentalReviewPartitions.find(([key]) => key === partition);
  const currentTasks = (packet) => (packet?.tasks || []).filter((task) => task.evidence_quality === "current");
  const zcode = currentTasks(review.zcode);
  const deepseek = currentTasks(review.deepseek);
  const taskText = (tasks) => tasks.map((task) => `${task.scope_label} ${modelReviewTaskStatus(task)}`).join(" · ");
  const detail = partition === "conflict"
    ? `ZCode：${taskText(zcode) || "无"}；DeepSeek：${taskText(deepseek) || "无"}`
    : partition === "both_insufficient"
      ? "双方保存结果没有引用主报告之后的有效材料，旧结论仅供对照。"
      : `ZCode：${taskText(zcode) || "历史/不足"}；DeepSeek：${taskText(deepseek) || "历史/不足"}`;
  return { label: meta?.[1] || "复核待核对", detail, tone: meta?.[3] || "gap" };
}

function renderReportReviewAlertCell(review, { compact = false, fundamentalReview = null } = {}) {
  const cell = document.createElement("td");
  cell.className = `report-review-alert-cell ${compact ? "report-review-alert-compact" : ""}`;
  cell.dataset.label = compact ? "报告复核摘要" : "对照分区";
  const direct = fundamentalReview?.manual?.codex_direct || review?.manual?.codex_direct;
  if (compact && direct) {
    const directLabel = document.createElement("strong");
    directLabel.className = `report-review-direct-label report-review-direct-${direct.status || "unknown"}`;
    directLabel.textContent = `Codex 直接复核 · 红线 ${direct.redline_count ?? 0} · 关注 ${direct.warning_count ?? 0}`;
    const directDetail = document.createElement("p");
    directDetail.className = "report-review-direct-detail";
    directDetail.textContent = direct.label || direct.status || "尚未保存结论";
    cell.append(directLabel, directDetail);
  }
  const alert = reportReviewAlert(review);
  const label = document.createElement("strong");
  label.className = `report-review-alert-label report-review-alert-${alert.tone}`;
  label.textContent = compact ? `ZCode × DeepSeek · ${alert.label}` : alert.label;
  const detail = document.createElement("p");
  detail.textContent = alert.detail;
  cell.append(label, detail);
  return cell;
}

function renderReviewQueueStatusCell(review) {
  const cell = document.createElement("td");
  cell.className = "fundamental-review-queue-cell";
  cell.dataset.label = "复核分区";
  const key = fundamentalReviewPartitionKey(review);
  const meta = fundamentalReviewPartitions.find(([partition]) => partition === key);
  const badge = document.createElement("strong");
  badge.className = `fundamental-review-badge fundamental-review-badge-${meta?.[3] || "waiting"}`;
  badge.textContent = meta?.[1] || "等待复核";
  cell.append(badge);
  return cell;
}

function layerReviewLabel(run) {
  return fundamentalReviewStatusMeta[run?.status]?.label || run?.label || "尚未复核";
}

function renderReviewLayerCell(review, layer, label) {
  const cell = document.createElement("td");
  cell.className = "fundamental-review-queue-cell review-layer-queue-cell";
  cell.dataset.label = label;
  const run = review?.[layer]?.current;
  if (!run) {
    cell.textContent = "尚未保存复核结果";
    return cell;
  }
  const heading = document.createElement("strong");
  heading.textContent = layerReviewLabel(run);
  const model = document.createElement("p");
  model.className = "fundamental-review-meta";
  model.textContent = run.model || run.reviewer || "复核者未记录";
  const facts = document.createElement("p");
  facts.className = "fundamental-review-meta muted";
  facts.textContent = `${shortReviewDate(run.generated_at)} · 当前证据 ${run.current_evidence_count ?? 0} 份`;
  const note = document.createElement("p");
  note.className = "fundamental-review-meta muted";
  note.textContent = run.migrated_seed ? "迁移记录，保留原始证据状态" : (run.variant ? `推理档位：${run.variant}` : "当前层结果");
  cell.append(heading, model, facts, note);
  return cell;
}

function renderReviewScheduleCell(review) {
  const cell = document.createElement("td");
  cell.className = "fundamental-review-queue-cell review-schedule-cell";
  cell.dataset.label = "下次到期";
  for (const [layer, label] of [["daily", "日常"], ["deep", "深度"]]) {
    const row = document.createElement("p");
    row.className = "fundamental-review-meta";
    row.textContent = `${label}：${shortReviewDate(review?.[layer]?.due_at)}`;
    cell.append(row);
  }
  const comparison = review?.layer_comparison;
  if (comparison?.label) {
    const note = document.createElement("p");
    note.className = "fundamental-review-meta muted";
    note.textContent = comparison.label;
    cell.append(note);
  }
  return cell;
}

function renderModelReviewCell(packet, label) {
  const cell = document.createElement("td");
  cell.className = "fundamental-review-queue-cell model-review-queue-cell";
  cell.dataset.label = label;
  const source = document.createElement("strong");
  source.textContent = `${packet?.model || label} · ${shortReviewDate(packet?.generated_at)}`;
  const timing = document.createElement("p");
  timing.className = "fundamental-review-meta muted";
  const tasks = packet?.tasks || [];
  timing.textContent = tasks.length
    ? tasks.map((task) => `${task.scope_label} ${modelReviewTaskStatus(task)}（${modelReviewEvidenceLabel(task)}）`).join(" · ")
    : "未保存该模型的复核任务";
  cell.append(source, timing);
  return cell;
}

function renderCodexDirectReviewCell(review) {
  const cell = document.createElement("td");
  cell.className = "fundamental-review-queue-cell codex-direct-review-cell";
  cell.dataset.label = "Codex 直接复核";
  const direct = review?.manual?.codex_direct;
  if (!direct) {
    cell.textContent = "未归档 Codex 直接复核";
    return cell;
  }
  const source = document.createElement("strong");
  source.textContent = `Codex 直接复核 · ${shortReviewDate(direct.reviewed_at)}`;
  const verdict = document.createElement("p");
  verdict.className = "fundamental-review-meta";
  verdict.textContent = direct.label || direct.status || "未保存结论";
  const evidence = document.createElement("p");
  evidence.className = "fundamental-review-meta muted";
  evidence.textContent = `${direct.evidence_count ?? 0} 份当前证据 · 红线 ${direct.redline_count ?? 0} · 关注 ${direct.warning_count ?? 0}`;
  cell.append(source, verdict, evidence);
  return cell;
}

function renderFundamentalReviewRows(visible) {
  setTableHeader(["公司 / 代码", "当前状态", "日常复核", "深度复核", "下次到期"]);
  const rendered = visible.slice(0, state.page * ROW_PAGE_SIZE);
  rendered.forEach((item, index) => {
    const review = modelReviewForItem(item);
    const tr = document.createElement("tr");
    const key = itemKey(item);
    if (key === state.selectedKey) tr.classList.add("active");
    tr.dataset.key = key;
    tr.dataset.index = String(index);
    tr.tabIndex = 0;
    tr.append(renderIdentityCell(item));

    tr.append(
      renderReviewQueueStatusCell(review),
      renderReviewLayerCell(review, "daily", "日常复核"),
      renderReviewLayerCell(review, "deep", "深度复核"),
      renderReviewScheduleCell(review),
    );

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
  els.status.textContent = `显示 ${rendered.length} / ${visible.length} · 日常与深度复核分层展示`;
  if (els.emptyState) els.emptyState.hidden = visible.length > 0;
  if (state.focusIndex >= visible.length) state.focusIndex = visible.length - 1;
}

function renderRows() {
  const visible = filteredDecisions();
  renderSummary(visible);
  els.rows.replaceChildren();
  if (state.view === "review") {
    renderFundamentalReviewRows(visible);
    return;
  }
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
    "公司 / 代码",
    "主报告判断",
    "人工价格分区",
    "现价",
    "当前状态",
    "技术面（辅助）",
  ]);

  const rendered = visible.slice(0, state.page * ROW_PAGE_SIZE);
  rendered.forEach((item, index) => {
    const tr = document.createElement("tr");
    const key = itemKey(item);
    if (key === state.selectedKey) tr.classList.add("active");
    tr.dataset.key = key;
    tr.dataset.index = String(index);
    tr.tabIndex = 0;

    tr.append(renderIdentityCell(item));

    const quote = state.quotes.get(item.ticker);
    const actionTd = document.createElement("td");
    actionTd.className = "conclusion-cell";
    actionTd.append(
      renderPrimaryJudgment(item, { compact: true })
      || renderPriceActionTable(item, quote, { compact: true }),
    );
    tr.append(actionTd);

    const humanReviewTd = document.createElement("td");
    humanReviewTd.className = "human-review-cell";
    humanReviewTd.append(renderHumanReviewMainCell(item, quote));
    tr.append(humanReviewTd);

    const change = formatChange(quote);
    const quoteTd = document.createElement("td");
    quoteTd.className = "quote-block";
    const quotePrice = document.createElement("div");
    quotePrice.className = "quote-price";
    quotePrice.textContent = formatPrice(quote);
    const quoteChange = document.createElement("div");
    quoteChange.className = `quote-change ${change.className}`;
    quoteChange.textContent = `${change.text}${quote?.source ? " · 同源快照" : ""}`;
    quoteTd.append(quotePrice, quoteChange);
    tr.append(quoteTd);

    const adviceTd = document.createElement("td");
    adviceTd.className = "execution-main-cell";
    adviceTd.append(renderExecutionMainCell(item, quote));
    tr.append(adviceTd);

    tr.append(renderTechnicalCell(item, { includeCross: true }));

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

const fundamentalReviewGroupMeta = {
  redline: { label: "风险红线", tone: "redline" },
  holder: { label: "持仓验证", tone: "attention" },
  improvement: { label: "改善 / 升级条件", tone: "improving" },
  entry: { label: "买入前提", tone: "waiting" },
};

function renderFundamentalReviewRule(rule) {
  const article = document.createElement("article");
  const groupMeta = fundamentalReviewGroupMeta[rule.semantic_group || rule.group] || fundamentalReviewGroupMeta.holder;
  article.className = `fundamental-review-rule-card fundamental-review-rule-card-${groupMeta.tone}`;
  const head = document.createElement("div");
  head.className = "fundamental-review-rule-head";
  const group = document.createElement("span");
  group.className = `fundamental-review-mini-badge fundamental-review-mini-badge-${groupMeta.tone}`;
  group.textContent = groupMeta.label;
  const truth = document.createElement("span");
  truth.className = "fundamental-review-rule-truth";
  truth.textContent = `日常：${reviewTruthLabel(rule.result)}`;
  head.append(group, truth);
  const condition = document.createElement("p");
  condition.className = "fundamental-review-rule-condition";
  condition.textContent = rule.condition || "主报告未给出具体条件";
  const meta = document.createElement("dl");
  meta.className = "fundamental-review-rule-meta";
  const rows = [
    ["指标", (rule.metrics || []).join("、") || "事件 / 定性条件"],
    ["关系", (rule.semantic_relation || rule.relation) === "any_of" ? "任一满足" : "全部满足（保守核验）"],
    ["阈值", [rule.operator, rule.threshold].filter(Boolean).join(" ") || "按主报告原文"],
    ["复核时间", reviewScheduleLabel(rule)],
  ];
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    meta.append(dt, dd);
  }
  article.append(head, condition, meta);

  if (rule.result) {
    const result = document.createElement("div");
    result.className = "fundamental-review-result";
    const value = document.createElement("strong");
    value.textContent = `日常当前值：${rule.result.current_value || "未取得"}`;
    const comparison = document.createElement("p");
    comparison.textContent = rule.result.comparison || "尚无可完成条件判断的当前对比";
    result.append(value, comparison);
    if (rule.result.missing_codes?.length) {
      const missing = document.createElement("p");
      missing.className = "fundamental-review-missing";
      missing.textContent = `缺口码：${rule.result.missing_codes.join("、")}`;
      result.append(missing);
    }
    article.append(result);
  }

  const sourceLines = rule.source_lines || [];
  if (sourceLines.length) {
    const source = document.createElement("details");
    source.className = "fundamental-review-source";
    const summary = document.createElement("summary");
    summary.textContent = "查看主报告锁定依据";
    source.append(summary);
    for (const row of sourceLines.slice(0, 3)) {
      const quote = document.createElement("p");
      const range = row.line_start ? `L${row.line_start}${row.line_end && row.line_end !== row.line_start ? `–L${row.line_end}` : ""} · ` : "";
      quote.textContent = `${range}${row.quote || row.supports || "已记录原文位置"}`;
      source.append(quote);
    }
    article.append(source);
  }
  return article;
}

function appendFundamentalReviewSection(title, note, rules) {
  const card = document.createElement("section");
  card.className = "card fundamental-review-detail-section";
  const heading = document.createElement("div");
  heading.className = "fundamental-review-section-head";
  const h3 = document.createElement("h3");
  h3.textContent = `${title} · ${rules.length}`;
  const p = document.createElement("p");
  p.textContent = note;
  heading.append(h3, p);
  card.append(heading);
  if (!rules.length) {
    const empty = document.createElement("p");
    empty.className = "source-note";
    empty.textContent = "主报告没有锁定这一类条件。";
    card.append(empty);
  } else {
    const grid = document.createElement("div");
    grid.className = "fundamental-review-detail-grid";
    for (const rule of rules) grid.append(renderFundamentalReviewRule(rule));
    card.append(grid);
  }
  els.detailBody.append(card);
}

function appendReviewFacts(parent, rows) {
  const facts = document.createElement("div");
  facts.className = "fundamental-review-overview-facts";
  for (const [label, value] of rows) {
    const fact = document.createElement("div");
    const span = document.createElement("span");
    span.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    fact.append(span, strong);
    facts.append(fact);
  }
  parent.append(facts);
}

function renderFundamentalReviewDetail(item) {
  const reviewLayer = fundamentalReviewForItem(item);
  if (!reviewLayer) {
    const empty = document.createElement("div");
    empty.className = "card";
    empty.innerHTML = "<h3>报告复核快照未生成</h3><p class=\"source-note\">当前没有找到该股票的人工锁定规则与复核记录。</p>";
    els.detailBody.append(empty);
    return;
  }
  const overview = document.createElement("section");
  overview.className = "card fundamental-review-overview-card";
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "LOCKED RULES · TWO REVIEW LAYERS";
  const title = document.createElement("h3");
  title.textContent = "主报告规则与复核结果";
  const policy = document.createElement("p");
  policy.className = "fundamental-review-policy";
  policy.textContent = "人工锁定规则决定核对什么；日常层与深度层只核验新证据，不改写主报告判断、红线或人工价格分区。";
  overview.append(eyebrow, title, policy);
  appendReviewFacts(overview, [
    ["规则版本", `主报告哈希 ${(reviewLayer.main_report?.canonical_sha256 || "").slice(0, 12) || "未记录"}`],
    ["人工确认", shortReviewDate(reviewLayer.manual?.reviewed_at || reviewLayer.main_report?.reviewed_at)],
    ["锁定规则", `${reviewLayer.manual?.rule_count ?? reviewLayer.rules?.length ?? 0} 条`],
    ["当前分区", fundamentalReviewStatusMeta[fundamentalReviewPartitionKey(reviewLayer)]?.label || "等待复核"],
  ]);
  els.detailBody.append(overview);

  const renderLayerCard = (layer, titleText, policyText) => {
    const layerInfo = reviewLayer[layer] || {};
    const run = layerInfo.current;
    const card = document.createElement("section");
    card.className = "card model-review-detail-card";
    const title = document.createElement("h3");
    title.textContent = titleText;
    const note = document.createElement("p");
    note.className = "fundamental-review-policy";
    note.textContent = policyText;
    card.append(title, note);
    if (!run) {
      const empty = document.createElement("p");
      empty.className = "source-note";
      empty.textContent = "尚未保存该层的复核结果。";
      card.append(empty);
      return card;
    }
    appendReviewFacts(card, [
      ["复核者", run.model || run.reviewer || "未记录"],
      ["复核时间", shortReviewDate(run.generated_at)],
      ["结果", layerReviewLabel(run)],
      ["当前证据", `${run.current_evidence_count ?? 0} 份 · ${run.evidence_state === "current" ? "当前" : "历史/不足"}`],
      ["下次到期", shortReviewDate(layerInfo.due_at || run.due_at)],
    ]);
    if (run.variant) {
      const variant = document.createElement("p");
      variant.className = "source-note";
      variant.textContent = `推理档位：${run.variant}`;
      card.append(variant);
    }
    if (run.migrated_seed) {
      const seed = document.createElement("p");
      seed.className = "source-note";
      seed.textContent = "这是迁移的既有结果，保留其原始复核者和证据状态；新的本层运行会原子替换它。";
      card.append(seed);
    }
    const tasks = run.tasks || [];
    if (tasks.length) {
      const list = document.createElement("div");
      list.className = "model-review-task-list";
      for (const task of tasks) {
        const taskCard = document.createElement("article");
        taskCard.className = "model-review-task";
        const heading = document.createElement("strong");
        heading.textContent = `${task.scope_label || task.group || "复核事项"} · ${modelReviewTaskStatus(task)}`;
        const conclusion = document.createElement("p");
        conclusion.textContent = task.conclusion || task.rule_content || "未保存文字结论。";
        taskCard.append(heading, conclusion);
        if (task.missing_codes?.length) {
          const gap = document.createElement("small");
          gap.textContent = `数据缺口：${task.missing_codes.join("、")}`;
          taskCard.append(gap);
        }
        list.append(taskCard);
      }
      card.append(list);
    }
    const history = layerInfo.history || [];
    if (history.length) {
      const historyNote = document.createElement("p");
      historyNote.className = "source-note";
      historyNote.textContent = `历史记录 ${history.length} 条：${history.map((row) => `${row.model || row.reviewer || "未记录"}（${shortReviewDate(row.generated_at)}）`).join("；")}`;
      card.append(historyNote);
    }
    return card;
  };
  els.detailBody.append(
    renderLayerCard("daily", "日常复核", "由你手动运行固定 DeepSeek；默认每三天到期。当前迁移记录不会伪装成新的 DeepSeek 结果。"),
    renderLayerCard("deep", "深度复核", "由你手动指定较强模型与推理档位；默认每三十天到期，不固定某一模型。"),
  );
  const comparisonCard = document.createElement("section");
  comparisonCard.className = "card fundamental-review-overview-card";
  const comparisonTitle = document.createElement("h3");
  comparisonTitle.textContent = "两层一致性";
  const comparisonNote = document.createElement("p");
  comparisonNote.className = "fundamental-review-policy";
  comparisonNote.textContent = reviewLayer.layer_comparison?.label || "尚无可比较的两层结果。";
  comparisonCard.append(comparisonTitle, comparisonNote);
  els.detailBody.append(comparisonCard);

  const redlines = fundamentalReviewRules(reviewLayer, "redline").filter((rule) => rule.schedule_type !== "price");
  const due = fundamentalReviewRules(reviewLayer).filter((rule) => rule.reviewable && rule.schedule_type !== "price");
  const improvements = fundamentalReviewRules(reviewLayer, "improvement").filter((rule) => rule.schedule_type !== "price");
  appendFundamentalReviewSection("锁定风险红线", "只有当前证据支持负向条件时，才会进入红线分区。", redlines);
  appendFundamentalReviewSection("待核验事项", "财报、经营和事件条件按原报告核验；价格条件仍由人工价格分区处理。", due);
  appendFundamentalReviewSection("改善与升级条件", "正向条件单独显示，不能和红线混为同一个“触发”。", improvements);
  return;

  // 保留旧版复核详情实现以便回溯；当前实现已经在上方返回。
  if (false) {
  const comparison = modelReviewForItem(item);
  const strictReview = fundamentalReviewForItem(item);
  const codexDirect = strictReview?.manual?.codex_direct;
  if (codexDirect) {
    const directCard = document.createElement("section");
    directCard.className = "card fundamental-review-overview-card codex-direct-review-card";
    const eyebrow = document.createElement("p");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = "CODEX DIRECT EVIDENCE REVIEW";
    const title = document.createElement("h3");
    title.textContent = "Codex 直接复核（当前证据）";
    const verdict = document.createElement("p");
    verdict.className = "fundamental-review-policy";
    verdict.textContent = codexDirect.label || codexDirect.status || "未保存结论";
    directCard.append(eyebrow, title, verdict);
    appendReviewFacts(directCard, [
      ["复核时间", shortReviewDate(codexDirect.reviewed_at)],
      ["当前证据", `${codexDirect.evidence_count ?? 0} 份`],
      ["红线 / 关注", `${codexDirect.redline_count ?? 0} / ${codexDirect.warning_count ?? 0}`],
      ["下一证据", codexDirect.next_evidence || "未记录"],
    ]);
    if (codexDirect.data_gaps?.length) {
      const gaps = document.createElement("p");
      gaps.className = "source-note";
      gaps.textContent = `数据缺口：${codexDirect.data_gaps.join("；")}`;
      directCard.append(gaps);
    }
    const boundary = document.createElement("p");
    boundary.className = "fundamental-review-policy";
    boundary.textContent = codexDirect.source_statement || codexDirect.decision_boundary || "只核对主报告之后的证据；不改写人工锁定规则。";
    directCard.append(boundary);
    els.detailBody.append(directCard);
  }
  const comparisonCard = document.createElement("section");
  comparisonCard.className = "card fundamental-review-overview-card";
  const comparisonEyebrow = document.createElement("p");
  comparisonEyebrow.className = "eyebrow";
  comparisonEyebrow.textContent = "SAVED MODEL REVIEW COMPARISON";
  const comparisonTitle = document.createElement("h3");
  comparisonTitle.textContent = "ZCode 与 DeepSeek 模型交叉对照";
  const comparisonNote = document.createElement("p");
  comparisonNote.className = "fundamental-review-policy";
  comparisonNote.textContent = "两边都保留各自的规则文本和结果。只有引用主报告之后的本地或官方材料，才标为当前证据；这不会自动改变主报告判断或人工价格分区。";
  const priceContext = strictReview?.price_context || strictReview?.routine?.strict_incremental?.price_context;
  const priceNote = document.createElement("p");
  priceNote.className = "source-note";
  if (priceContext?.price !== null && priceContext?.price !== undefined) {
    const timing = priceContext.snapshot_generated_at ? shortReviewDate(priceContext.snapshot_generated_at) : "时间未记录";
    const freshness = priceContext.status === "fresh" ? "新鲜" : "已过期";
    priceNote.textContent = `复核行情上下文：${priceContext.price} ${priceContext.currency || ""} · ${timing} · ${freshness}。仅作价格背景，不参与经营结论。`;
  } else {
    priceNote.textContent = "复核行情上下文：快照缺失；不会以搜索摘要或推测补充价格。";
  }
  const comparisonAlert = reportReviewAlert(comparison);
  const comparisonStatus = document.createElement("p");
  comparisonStatus.className = `report-review-alert-label report-review-alert-${comparisonAlert.tone}`;
  comparisonStatus.textContent = `${comparisonAlert.label}：${comparisonAlert.detail}`;
  comparisonCard.append(comparisonEyebrow, comparisonTitle, comparisonStatus, comparisonNote, priceNote);
  els.detailBody.append(comparisonCard);

  const statusClass = (task) => task?.evidence_quality === "current" ? "model-review-current" : "model-review-historical";
  for (const [label, packet] of [["ZCode 独立复核", comparison.zcode], ["DeepSeek 复核", comparison.deepseek]]) {
    const card = document.createElement("section");
    card.className = "card model-review-detail-card";
    const heading = document.createElement("h3");
    heading.textContent = label;
    const meta = document.createElement("p");
    meta.className = "source-note";
    meta.textContent = `${packet?.model || "模型未记录"} · ${shortReviewDate(packet?.generated_at)} · ${packet?.scope || "未记录复核范围"}`;
    card.append(heading, meta);
    const taskList = document.createElement("div");
    taskList.className = "model-review-task-list";
    for (const task of packet?.tasks || []) {
      const taskCard = document.createElement("article");
      taskCard.className = `model-review-task ${statusClass(task)}`;
      const taskHeading = document.createElement("strong");
      taskHeading.textContent = `${task.scope_label} · ${modelReviewTaskStatus(task)} · ${modelReviewEvidenceLabel(task)}`;
      const rule = document.createElement("p");
      rule.textContent = task.rule_content || "未保留独立规则文本。";
      const conclusion = document.createElement("p");
      conclusion.className = "model-review-conclusion";
      conclusion.textContent = task.conclusion || "该模型未保存文字结论。";
      taskCard.append(taskHeading, rule, conclusion);
      for (const line of task.evidence_lines || []) {
        const quote = document.createElement("blockquote");
        quote.textContent = `${line.line_ref || "原文"} · ${line.exact_quote || "未保留引文"}`;
        taskCard.append(quote);
      }
      if (task.missing_codes?.length) {
        const gap = document.createElement("small");
        gap.textContent = `数据缺口：${task.missing_codes.join("、")}`;
        taskCard.append(gap);
      }
      taskList.append(taskCard);
    }
    if (!packet?.tasks?.length) {
      const empty = document.createElement("p");
      empty.className = "source-note";
      empty.textContent = "没有保存该模型的任务结果。";
      taskList.append(empty);
    }
    card.append(taskList);
    els.detailBody.append(card);
  }
  return;

  const review = fundamentalReviewForItem(item);
  if (!review) {
    const empty = document.createElement("div");
    empty.className = "card";
    empty.innerHTML = "<h3>复核快照未生成</h3><p class=\"source-note\">先运行本地增量复核构建，再刷新看板。</p>";
    els.detailBody.append(empty);
    return;
  }
  const overview = document.createElement("section");
  overview.className = "card fundamental-review-overview-card";
  const copy = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "TWO-LAYER REPORT REVIEW";
  const title = document.createElement("h3");
  title.textContent = "人工规则与日常证据复核分开显示";
  copy.append(eyebrow, title);
  const layers = document.createElement("div");
  layers.className = "fundamental-review-layer-grid";

  const manual = review.manual || {};
  const direct = manual.codex_direct || null;
  const manualCard = document.createElement("article");
  manualCard.className = "fundamental-review-layer-card manual-review-card";
  const manualTop = document.createElement("div");
  manualTop.className = "fundamental-review-overview-top";
  const manualTitle = document.createElement("h4");
  manualTitle.textContent = "人工锁定规则";
  manualTop.append(manualTitle);
  appendManualReviewBadge(manualTop, review);
  appendReviewFacts(manualCard, [
    ["规则版本", `v2 · ${(review.main_report?.canonical_sha256 || "").slice(0, 12) || "无哈希"}`],
    ["人工确认", shortReviewDate(manual.reviewed_at || review.main_report?.reviewed_at)],
    ["锁定规则", `${manual.rule_count ?? review.rules?.length ?? 0} 条`],
    ["审计候选", `${manual.audit_candidate_count ?? review.audit_candidates?.length ?? 0} 条未启用`],
    ["今日 Codex 直接复核", direct ? `${direct.label || direct.status} · ${direct.evidence_count ?? 0} 份证据` : "尚未归档"],
  ]);
  const manualNote = document.createElement("p");
  manualNote.className = "fundamental-review-policy";
  manualNote.textContent = direct
    ? `Codex 只核对主报告之后的证据：${direct.source_statement || "未调用模型"}。它不改写人工锁定规则，价格条件仍由买入前页面的人工价格分区处理。`
    : "只有人工确认的主报告规则在这里生效；价格条件仍由买入前页面的人工价格分区处理。";
  manualCard.prepend(manualTop);
  manualCard.append(manualNote);

  const routine = review.routine || {};
  const routineCard = document.createElement("article");
  routineCard.className = "fundamental-review-layer-card routine-review-card";
  const routineTop = document.createElement("div");
  routineTop.className = "fundamental-review-overview-top";
  const routineTitle = document.createElement("h4");
  routineTitle.textContent = "日常证据复核";
  routineTop.append(routineTitle);
  appendReviewBadge(routineTop, review);
  appendReviewFacts(routineCard, [
    ["核验模型", routine.reviewer || "DeepSeek 日常核验"],
    ["本次结果", routine.label || review.summary?.label || "尚未产生"],
    ["主报告后新证据", `${routine.current_evidence_count ?? review.current_evidence_count ?? 0} 份 · 最近 ${routine.latest_evidence_date || review.latest_evidence_date || "未记录"}`],
    ["检查安排", `上次 ${shortReviewDate(routine.generated_at || review.generated_at)} · 下次 ${shortReviewDate(review.next_check_at)}`],
  ]);
  const routineNote = document.createElement("p");
  routineNote.className = "fundamental-review-policy";
  routineNote.textContent = routineReviewMeta(review).status === "error"
    ? "本次日常复核未完成，不以已有主报告或旧模型状态补写结论。"
    : "只核验主报告之后的新证据；它不会改写人工规则、阈值、主报告判断或价格分区。";
  routineCard.prepend(routineTop);
  routineCard.append(routineNote);
  layers.append(manualCard, routineCard);
  const policy = document.createElement("p");
  policy.className = "fundamental-review-policy";
  policy.textContent = "人工层决定“核对什么”；日常层回答“最新证据是否满足”。两层结论不会互相覆盖。";
  overview.append(copy, layers, policy);
  els.detailBody.append(overview);

  const historicalTasks = review.routine?.legacy_daily?.tasks || [];
  if (historicalTasks.length) {
    const historicalCard = document.createElement("section");
    historicalCard.className = "card fundamental-review-history-card";
    const historicalTitle = document.createElement("h3");
    historicalTitle.textContent = "上一轮 DeepSeek 日常复核（历史数据）";
    const historicalNote = document.createElement("p");
    historicalNote.className = "source-note";
    historicalNote.textContent = review.routine.legacy_daily.caveat || "这是已保存的日常复核原始任务，不会改写人工锁定规则。";
    historicalCard.append(historicalTitle, historicalNote);
    const taskLabels = { entry: "买入前提", holder: "持仓验证", risk: "原始风险 / 条件任务" };
    const statusLabels = { verified: "原模型：已验证", not_triggered: "原模型：未触发", triggered: "原模型：有触发", data_insufficient: "原模型：数据不足" };
    const taskList = document.createElement("div");
    taskList.className = "fundamental-review-history-list";
    for (const task of historicalTasks) {
      const taskCard = document.createElement("article");
      const heading = document.createElement("strong");
      heading.textContent = `${taskLabels[task.task_id] || task.task_id} · ${statusLabels[task.status] || task.status}`;
      const meta = document.createElement("small");
      meta.textContent = `${task.evidence_count || 0} 份引用证据${task.missing_codes?.length ? ` · 缺口：${task.missing_codes.join("、")}` : ""}`;
      taskCard.append(heading, meta);
      for (const line of task.evidence_lines || []) {
        const quote = document.createElement("p");
        quote.textContent = `${line.line_ref || "原文"} · ${line.exact_quote || "未保留引文"}`;
        taskCard.append(quote);
      }
      taskList.append(taskCard);
    }
    historicalCard.append(taskList);
    const strict = review.routine?.strict_incremental;
    if (strict?.status && strict.status !== "waiting_evidence") {
      const strictNote = document.createElement("p");
      strictNote.className = "source-note";
      strictNote.textContent = `严格增量核验状态：${strict.label || strict.status}。${strict.message || ""}`;
      historicalCard.append(strictNote);
    }
    els.detailBody.append(historicalCard);
  }

  const reusedZcode = (review.evidence_documents || [])
    .filter((document) => document.source_role === "zcode_current_evidence_extract");
  if (reusedZcode.length) {
    const reusedCard = document.createElement("section");
    reusedCard.className = "card fundamental-review-reused-card";
    const reusedTitle = document.createElement("h3");
    reusedTitle.textContent = "日常层可复用的 ZCode 当前事实";
    const reusedNote = document.createElement("p");
    reusedNote.className = "source-note";
    reusedNote.textContent = "直接复用已有当前值、对比和原文定位；旧 verified / triggered 状态不继承，仍按人工锁定规则重新判定。";
    const reusedList = document.createElement("div");
    reusedList.className = "fundamental-review-reused-list";
    for (const evidenceDocument of reusedZcode) {
      const itemCard = document.createElement("article");
      const task = document.createElement("strong");
      const taskLabels = { entry: "买入前提数据", holder: "经营与持仓数据", risk: "风险核查数据" };
      task.textContent = taskLabels[evidenceDocument.legacy_task_id] || "已有事实提取";
      const summary = document.createElement("p");
      summary.textContent = evidenceDocument.fact_summary || "已保留原文证据，等待按锁定规则映射。";
      const source = document.createElement("small");
      const sourceCount = (evidenceDocument.provenance || []).length;
      source.textContent = `${evidenceDocument.document_date || "日期未记录"} · ${sourceCount} 处原文定位`;
      itemCard.append(task, summary, source);
      reusedList.append(itemCard);
    }
    reusedCard.append(reusedTitle, reusedNote, reusedList);
    els.detailBody.append(reusedCard);
  }

  const redlines = fundamentalReviewRules(review, "redline").filter((rule) => rule.schedule_type !== "price");
  const due = fundamentalReviewRules(review).filter(
    (rule) => rule.reviewable && ["holder", "entry"].includes(rule.semantic_group || rule.group),
  );
  const improvements = fundamentalReviewRules(review, "improvement").filter((rule) => rule.schedule_type !== "price");
  appendFundamentalReviewSection("日常红线 / 风险预警", "人工规则给出条件；只有日常层的当前证据满足负向条件时才显示为红线触发。", redlines);
  appendFundamentalReviewSection("日常待核验事项", "按人工锁定的财报、经营或事件条件核验；价格条件仍由人工价格分区处理。", due);
  appendFundamentalReviewSection("日常改善信号", "正向条件单列，不再与卖出红线共用 triggered。", improvements);

  const gaps = document.createElement("section");
  gaps.className = "card fundamental-review-gap-card";
  const gapTitle = document.createElement("h3");
  gapTitle.textContent = "日常证据缺口与审计边界";
  const gapText = document.createElement("p");
  const gapLabels = reviewGapLabels(review);
  gapText.textContent = gapLabels.length
    ? `当前缺少：${gapLabels.join("、")}。找不到时保留数据不足，不用主报告历史基线冒充当前验证。`
    : "当前没有汇总层面的证据缺口。";
  const audit = document.createElement("p");
  audit.className = "source-note";
  audit.textContent = `${review.audit_candidates?.length || 0} 条 ZCode 审计候选仅用于发现遗漏，尚未人工确认，因此不参与任何当前判断。`;
  gaps.append(gapTitle, gapText, audit);
  els.detailBody.append(gaps);
  }
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
  const detailTabs = document.querySelector(".detail-tabs");
  if (detailTabs) detailTabs.hidden = false;
  const tracking = trackingForItem(item);
  const trackingTab = document.querySelector(".tracking-tab");
  if (trackingTab) {
    trackingTab.hidden = !tracking;
    if (!tracking && state.detailTab === "tracking") state.detailTab = "overview";
  }
  const checklistTab = document.querySelector(".checklist-tab");
  const deepReviewTab = document.querySelector(".deep-review-tab");
  const reportReviewTab = document.querySelector(".report-review-tab");
  const isAShare = item.market === "A股";
  if (reportReviewTab) {
    reportReviewTab.hidden = !isAShare;
    if (!isAShare && state.detailTab === "report-review") state.detailTab = "technical";
  }
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

  if (state.detailTab === "report-review") {
    const review = fundamentalReviewForItem(item);
    const partition = fundamentalReviewStatusMeta[fundamentalReviewPartitionKey(review)]?.label || "等待复核";
    els.detailSub.textContent = `${partition} · 日常 ${shortReviewDate(review?.daily?.current?.generated_at)} · 深度 ${shortReviewDate(review?.deep?.current?.generated_at)}`;
    renderFundamentalReviewDetail(item);
    return;
  }

  const detailNeeded = ["overview", "history"].includes(state.detailTab);
  if (detailNeeded && !detailLoaded(item)) {
    const error = state.detailErrors.get(itemKey(item));
    const loading = document.createElement("div");
    loading.className = "card detail-loading-card";
    const loadingTitle = document.createElement("h3");
    loadingTitle.textContent = error ? "详细研报加载失败" : "正在加载完整研报上下文";
    const loadingNote = document.createElement("p");
    loadingNote.className = "source-note";
    loadingNote.textContent = error || "首屏只加载决策所需字段；历史研报和估值内容在打开详情后读取。";
    loading.append(loadingTitle, loadingNote);
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

      const humanReviewCard = document.createElement("div");
      humanReviewCard.className = "card human-review-card";
      humanReviewCard.innerHTML = "<h3>人工复核分区</h3>";
      humanReviewCard.append(renderHumanReviewState(item, quote));
      const humanReviewPlan = document.createElement("div");
      humanReviewPlan.className = "human-review-plan-detail";
      humanReviewPlan.innerHTML = "<h4>固定复核事项</h4>";
      humanReviewPlan.append(renderHumanReviewPlan(item));
      humanReviewCard.append(humanReviewPlan);
      els.detailBody.append(humanReviewCard);
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
      ? `<h3>筛选依据</h3><p class="source-note">主报告判断始终保留原文；当前执行分区按报告价格档、经营前提和最新同源行情动态计算。人工复核只作为行动提示，不再覆盖价格状态；Checklist 由你自行查看，不参与自动分区，技术面和情绪面保持独立辅助展示。</p>`
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
    const cutoffText = document.createElement("strong");
    cutoffText.textContent = snap.data_cutoff || "待复核";
    const decisionBadge = document.createElement("span");
    decisionBadge.className = `decision ${decisionClass(snap.action)}`;
    decisionBadge.textContent = snap.action || "-";
    head.append(cutoffText, decisionBadge);
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
  renderFundamentalReviewPartitions();
  renderRows();
  renderDetail();
}

function setView(view) {
  state.view = ["tracking", "review"].includes(view) ? view : "decision";
  document.body.classList.toggle("review-view", state.view === "review");
  state.focusIndex = -1;
  resetRowPage();
  if (state.view === "tracking") {
    state.detailTab = "tracking";
  } else if (state.view === "review") {
    state.detailTab = "report-review";
  } else if (["tracking", "report-review"].includes(state.detailTab)) {
    state.detailTab = "technical";
  }
  els.viewTabs?.querySelectorAll(".chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.view === state.view);
  });
  if (els.marketChips) els.marketChips.hidden = state.view === "review";
  if (els.actionChips) els.actionChips.hidden = state.view !== "decision";
  if (els.advancedFilters) {
    els.advancedFilters.hidden = state.view !== "decision";
    if (state.view !== "decision") els.advancedFilters.open = false;
  }
  if (els.referenceActionChips) els.referenceActionChips.hidden = state.view !== "decision";
  if (els.humanReviewChips) els.humanReviewChips.hidden = state.view !== "decision";
  if (els.trackingFilterRow) els.trackingFilterRow.hidden = state.view !== "tracking";
  if (els.fundamentalReviewFilterRow) els.fundamentalReviewFilterRow.hidden = state.view !== "review";
  if (els.sortField) els.sortField.hidden = state.view === "review";
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
    state.humanReviewAction = "all";
    state.fundamentalReviewFilter = "all";
    state.trackingFilter = "all";
    state.sort = "execution";
    resetRowPage();
    els.companyFilter.value = "";
    els.sortSelect.value = "execution";
    if (els.advancedFilters) els.advancedFilters.open = false;
    els.marketChips.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.market === "all");
    });
    els.actionChips.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.action === "all");
    });
    els.referenceActionChips?.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.referenceAction === "all");
    });
    els.humanReviewChips?.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.humanReviewAction === "all");
    });
    els.trackingFilterRow?.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.trackingFilter === "all");
    });
    els.fundamentalReviewFilterRow?.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.fundamentalReviewFilter === "all");
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
  els.humanReviewChips?.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    state.humanReviewAction = chip.dataset.humanReviewAction;
    resetRowPage();
    els.humanReviewChips.querySelectorAll(".chip").forEach((node) => {
      node.classList.toggle("active", node === chip);
    });
    renderRows();
  });
  els.fundamentalReviewFilterRow?.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    setFundamentalReviewFilter(chip.dataset.fundamentalReviewFilter || "all");
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
    } else if (event.key === "Enter" && state.focusIndex >= 0 && !event.target.closest?.("tr[data-key]")) {
      // Rows handle their own Enter activation; avoid double-handling here.
      openDetail(visible[state.focusIndex]);
      state.detailTab = "technical";
      renderDetail();
    } else if (event.key === "o" && selectedItem()) {
      els.detailReport.click();
    }
  });
}

async function loadSentimentSnapshot() {
  const statusResponse = await fetch("./data/sentiment_status.json", { cache: "no-store" });
  state.sentimentStatus = statusResponse.ok
    ? await statusResponse.json()
    : {status: "unknown"};
  const response = await fetch("./data/sentiment.json", { cache: "no-store" });
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

async function loadOpportunityScansSnapshot() {
  const response = await fetch("./data/opportunity_scans.json", { cache: "no-store" });
  if (!response.ok) {
    state.opportunityScans = new Map();
    state.opportunityScansGeneratedAt = null;
    state.opportunityScanModels = [];
    return;
  }
  const snapshot = await response.json();
  state.opportunityScansGeneratedAt = snapshot.generated_at || null;
  state.opportunityScanModels = Array.isArray(snapshot.models) ? snapshot.models : [];
  state.opportunityScans = new Map(
    (snapshot.scans || [])
      .filter((item) => item?.ticker && item.market === "A股")
      .map((item) => [item.ticker, item]),
  );
}

async function loadOpportunityScanStatus() {
  const response = await fetch("./data/opportunity_scan_status.json", { cache: "no-store" });
  if (!response.ok) {
    state.opportunityScanStatus = null;
    return;
  }
  state.opportunityScanStatus = await response.json();
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

async function loadFundamentalReviewSnapshot() {
  const response = await fetch("./data/main_report_review.json", { cache: "no-store" });
  if (!response.ok) throw new Error("main report review snapshot missing");
  const snapshot = await response.json();
  state.fundamentalReviewSnapshot = snapshot;
  state.fundamentalReviews = new Map(
    (snapshot.reviews || [])
      .filter((item) => item?.ticker)
      .map((item) => [item.ticker, item]),
  );
  updateFundamentalReviewControls();
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

  const [intradayResult, scansResult, scanStatusResult, sentimentResult, deepReviewsResult, snapshotQuotesResult, annualDatesResult, automationStatusResult, fundamentalReviewResult] =
    await Promise.allSettled([
      loadIntradayTechnicalSnapshot(),
      loadOpportunityScansSnapshot(),
      loadOpportunityScanStatus(),
      loadSentimentSnapshot(),
      loadDeepReviews(),
      loadSnapshotQuotes(),
      loadAnnualReportDates(),
      loadAutomationStatus(),
      loadFundamentalReviewSnapshot(),
    ]);

  if (intradayResult.status === "rejected") {
    console.warn("intraday technical snapshot failed", intradayResult.reason);
    state.intradayTechnical = new Map();
  }
  if (scansResult.status === "rejected") {
    console.warn("opportunity scan snapshot failed", scansResult.reason);
    state.opportunityScans = new Map();
    state.opportunityScansGeneratedAt = null;
    state.opportunityScanModels = [];
  }
  if (scanStatusResult.status === "rejected") {
    console.warn("opportunity scan status failed", scanStatusResult.reason);
    state.opportunityScanStatus = null;
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
    setLiveStatus("snapshot", quoteSnapshotStatusText());
  }
  if (annualDatesResult.status === "rejected") {
    console.warn("annual report dates snapshot failed", annualDatesResult.reason);
    state.annualReportDates = null;
  }
  if (automationStatusResult.status === "rejected") {
    console.warn("automation status snapshot failed", automationStatusResult.reason);
    state.automationStatus = null;
  }
  if (fundamentalReviewResult.status === "rejected") {
    console.warn("main report review snapshot failed", fundamentalReviewResult.reason);
    state.fundamentalReviewSnapshot = null;
    state.fundamentalReviews = new Map();
    updateFundamentalReviewControls();
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
