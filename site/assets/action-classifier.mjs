function quoteCurrencyForMarket(market) {
  if (market === "港股") return "HKD";
  if (market === "美股") return "USD";
  if (market === "A股") return "CNY";
  return null;
}

export function parseReportPriceBand(row, market) {
  const text = String(row?.price_range || "").replace(/,/g, "").trim();
  if (!text || /(?:PE|PB|PS|倍|x\b|%)/i.test(text)) return null;

  let currency = null;
  if (/(?:HK\$|HKD|港元)/i.test(text)) currency = "HKD";
  else if (/(?:US\$|USD|美元)/i.test(text)) currency = "USD";
  else if (/(?:₩|KRW|韩元)/i.test(text)) currency = "KRW";
  else if (/(?:CNY|人民币|元)/i.test(text)) currency = "CNY";
  else if (/\$/.test(text)) currency = quoteCurrencyForMarket(market) || "USD";
  else currency = quoteCurrencyForMarket(market);
  if (!currency) return null;

  const operator = text.match(
    /^\s*(不高于|不超过|不低于|低于|高于|以下|以上|≤|>=|<=|≥|<|>)/,
  )?.[1] || "";
  const ceilingOperators = new Set(["不高于", "不超过", "低于", "以下", "≤", "<=", "<"]);
  const floorOperators = new Set(["不低于", "高于", "以上", "≥", ">=", ">"]);
  const range = text.match(
    /(?:HK\$|US\$|₩|\$)?\s*(\d+(?:\.\d+)?)\s*[-—–~至到]\s*(\d+(?:\.\d+)?)/,
  );
  if (range) {
    const a = Number(range[1]);
    const b = Number(range[2]);
    if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
    const min = Math.min(a, b);
    const max = Math.max(a, b);
    // In report ladders, ">39.6 至 42.9" means one bounded interval.
    // The leading operator controls boundary inclusion, not an open-ended band.
    return { min, max, mode: "range", currency };
  }

  const number = text.match(/(?:HK\$|US\$|₩|\$)?\s*(\d+(?:\.\d+)?)/);
  if (!number) return null;
  const value = Number(number[1]);
  if (!Number.isFinite(value)) return null;
  if (ceilingOperators.has(operator) || /以下|以内/.test(text)) {
    return { min: null, max: value, mode: "ceiling", currency };
  }
  if (floorOperators.has(operator) || /以上/.test(text)) {
    return { min: value, max: null, mode: "floor", currency };
  }
  return { min: value, max: value, mode: "point", currency };
}

export function isHardThesisReject(text) {
  return /生意质量\s*(?:很)?差|论文(?:已|已经)?破裂|永久性损伤|不再跟踪|排除(?:出|于).{0,8}(?:观察池|股票池)|无法形成.{0,8}可投|财务造假|欺诈/.test(
    String(text || ""),
  );
}

export function currentActionKind(row) {
  const action = `${row?.profile || ""} ${row?.action || ""}`.trim();
  if (!action) return "unknown";

  if (
    isHardThesisReject(action)
    || /减仓|卖出|清仓|退出|止盈|降低仓位|降低持仓|降低暴露|锁定利润/.test(action)
  ) return "no";

  const hasTrial = /观察仓|小仓|轻仓|少量|小比例|试探|试错/.test(action);
  const conditionalTrial = /(?:等待|等信号|确认后|验证后|兑现后|若[^，。；]{0,20})[^，。；]{0,18}(?:观察仓|小仓|轻仓|试探|试错)/.test(
    action,
  );
  if (hasTrial && !conditionalTrial) return "trial";

  if (
    /空仓.{0,16}(?:等待|不追|观望|观察|不买|不新增|不新开仓)|新资金.{0,16}(?:等待|不追|观望|观察|不买|不新增)/.test(
      action,
    )
  ) return "watch";
  if (/持有/.test(action) && !/空仓|新资金|未持有/.test(action)) return "hold";
  if (
    /回避|不买|不参与|不建议买入|不宜买入|不适合.{0,12}买入|只能押注|暂不买入|先不买入|不激活买入|不因.{0,24}买入|不.{0,12}(?:建议加仓|适合买入|急于买|追价)|观望|等待|不追|暂停|无(?:明显)?安全边际|未到买点|合理偏贵|明显偏贵|需(?:要)?[^，。；]{0,16}(?:验证|兑现)|等(?:待)?估值消化|预期落空|风险收益比一般|估值无优势|溢价.{0,10}充分反映|非好信号/.test(
      action,
    )
  ) return "watch";
  if (hasTrial) return "watch";
  if (/持有/.test(action)) return "hold";
  if (/观察|关注/.test(action)) return "watch";
  if (
    /买入|买点|建仓|加仓|增持|配置|介入|重仓|重注|可参与|建立.{0,8}仓位|按计划分批|赔率明显占优|安全边际充分|低估区间/.test(
      action,
    )
  ) return "buy";
  return "unknown";
}

export function fallbackActionKind(item) {
  const action = String(item?.action || "").trim();
  const recommendation = `${item?.recommendation || ""} ${item?.conclusion_summary || ""} ${item?.valuation_heading || ""}`;
  if (action === "买入") return "buy";
  if (action === "分批买入") {
    return /观察仓|小仓|轻仓|少量|小比例|试探|试错|3\s*[-–—~至]\s*5\s*%/.test(
      recommendation,
    )
      ? "trial"
      : "buy";
  }
  if (action === "持有") return "hold";
  if (action === "减仓/卖出") return "no";
  if (action === "观察") {
    if (isHardThesisReject(recommendation)) return "no";
    if (/性价比极高|赔率明显占优|安全边际充分/.test(recommendation)) return "buy";
    return "watch";
  }
  if (/性价比极高/.test(recommendation)) return "buy";
  if (/估值有吸引力|具有吸引力/.test(recommendation)) return "trial";
  return currentActionKind({ action: recommendation });
}

export function primaryJudgmentForItem(item) {
  const judgment = item?.primary_judgment;
  if (!judgment || judgment.enabled !== true) return null;
  if (!judgment.label || !judgment.empty_position_action || !judgment.trigger_condition) return null;
  return judgment;
}

export function judgmentFilterKey(item, fallbackKind = "unknown") {
  const judgment = primaryJudgmentForItem(item);
  if (judgment) return judgment.label;
  return {
    buy: "可分批买入",
    trial: "小仓验证",
    watch: "等待验证",
    hold: "持有但不加仓",
    no: "回避/卖出",
    unknown: "待人工复核",
  }[fallbackKind] || "待人工复核";
}

function executionRank(key) {
  return {
    actionable: 80,
    trial: 70,
    validation: 60,
    wait_price: 45,
    wait_event: 35,
    hold: 25,
    no: 15,
    review: 0,
  }[key] ?? 0;
}

function executionResult(key, label, detail, extra = {}) {
  return {
    key,
    label,
    detail,
    actionable: key === "actionable" || key === "trial",
    rank: executionRank(key),
    ...extra,
  };
}

function legacyExecutionState(fallbackKind) {
  return {
    buy: executionResult("actionable", "当前可分批", "非 A 股沿用主报告动作"),
    trial: executionResult("trial", "当前可小仓", "非 A 股沿用主报告动作"),
    hold: executionResult("hold", "持有但不新买", "非 A 股沿用主报告动作"),
    watch: executionResult("wait_event", "等待报告条件", "非 A 股沿用主报告动作"),
    no: executionResult("no", "回避/不买", "非 A 股沿用主报告动作"),
    unknown: executionResult("review", "待人工复核", "主报告尚未形成可执行判断"),
  }[fallbackKind] || executionResult("review", "待人工复核", "主报告尚未形成可执行判断");
}

function comparableExecutionRules(policy, quote) {
  const currency = String(quote?.currency || "");
  return (Array.isArray(policy?.price_rules) ? policy.price_rules : [])
    .filter((rule) => Number.isFinite(Number(rule?.ceiling)) && rule?.currency === currency)
    .sort((a, b) => Number(a.ceiling) - Number(b.ceiling));
}

function matchedExecutionRule(rules, price) {
  return rules.find((rule) => price <= Number(rule.ceiling) + 1e-9) || null;
}

function executionRuleDetail(price, rule) {
  const action = String(rule?.action || "按报告价格档执行");
  return `现价 ${price.toFixed(2)}，已进入 ${rule.price_range} · 报告动作：${action}`;
}

function conditionWaitState(policy, price, rules) {
  const mode = policy?.condition_mode;
  if (!rules.length) {
    if (["event_only", "price_or_event", "price_and_event", "compound"].includes(mode)) {
      return executionResult(
        "wait_event",
        "等待事件/经营验证",
        policy?.event_condition || "报告未给出可由行情自动核对的价格门槛",
        { policy },
      );
    }
    return executionResult("review", "待人工复核", "报告未形成可自动比较的执行条件", { policy });
  }
  const highest = Number(rules[rules.length - 1].ceiling);
  const suffix = mode === "price_or_event"
    ? "，或等待报告列明的经营事件"
    : mode === "price_and_event" || mode === "compound"
      ? "，且后续仍需完成经营验证"
      : "";
  return executionResult(
    "wait_price",
    mode === "price_or_event" ? "等待价格或经营信号" : "等待价格",
    `现价 ${price.toFixed(2)}，高于报告最高可执行价 ${highest.toFixed(2)}${suffix}`,
    { policy, ceiling: highest },
  );
}

export function currentExecutionState(item, quote, fallbackKind = "unknown") {
  const manual = item?.manual_execution_review;
  if (item?.market === "A股" && manual?.status === "ready" && manual?.source === "human_review") {
    const key = String(manual.execution_key || "review");
    const defaults = {
      actionable: ["当前可分批", "人工复核允许小比例分批执行"],
      trial: ["仅激进小仓", "人工复核只允许能承受波动者建立观察仓"],
      validation: ["价格已到，等待验证", "人工复核认为仍有经营或治理条件未通过"],
      wait_price: ["等待价格/下一期财报", "人工复核认为当前赔率不足"],
      wait_event: ["等待事件/经营验证", "人工复核认为经营条件尚未通过"],
      hold: ["持有但不新买", "人工复核只允许已有持仓继续观察"],
      no: ["回避/不买", "人工复核明确不允许当前新增买入"],
      review: ["待人工复核", "人工复核记录不完整"],
    }[key] || ["待人工复核", "人工复核记录无法识别"];
    return executionResult(
      key,
      manual.label || defaults[0],
      manual.detail || defaults[1],
      { manualReview: manual, policy: item?.execution_policy },
    );
  }
  const policy = item?.execution_policy;
  if (!policy || item?.market !== "A股") return legacyExecutionState(fallbackKind);
  const mode = String(policy.condition_mode || "review");
  if (mode === "review" || policy.main_action_kind === "unknown") {
    return executionResult(
      "review",
      "待人工复核",
      "双模型未共同确认当前动作，或报告证据仍不完整",
      { policy },
    );
  }
  if (mode === "no_buy" || policy.main_action_kind === "no") {
    return executionResult("no", "回避/不买", "主报告明确不允许空仓者买入", { policy });
  }
  if (mode === "hold_only" || policy.main_action_kind === "hold") {
    return executionResult("hold", "持有但不新买", "报告动作只适用于已有持仓", { policy });
  }

  const policyRules = Array.isArray(policy.price_rules) ? policy.price_rules : [];
  if (!policyRules.length && ["event_only", "price_or_event", "price_and_event", "compound"].includes(mode)) {
    return executionResult(
      "wait_event",
      "等待事件/经营验证",
      policy.event_condition || "报告未给出可由行情自动核对的价格门槛",
      { policy },
    );
  }

  const price = Number(quote?.price);
  if (!Number.isFinite(price)) {
    return executionResult("review", "行情暂不可比", "没有可用于执行判断的当前价格", { policy });
  }
  const rules = comparableExecutionRules(policy, quote);
  const hasRules = policyRules.length > 0;
  if (hasRules && !rules.length) {
    return executionResult("review", "行情暂不可比", "当前行情币种与报告价格门槛不一致", { policy });
  }

  if (mode === "current_action") {
    const matched = matchedExecutionRule(rules, price);
    if (matched) {
      if (matched.requires_validation) {
        return executionResult(
          "validation",
          "价格已到，等待验证",
          `${executionRuleDetail(price, matched)} · 尚需：${matched.validation_condition || policy.event_condition || "报告列明的经营条件"}`,
          { policy, rule: matched },
        );
      }
      const matchedTrial = matched.action_kind === "trial";
      return executionResult(
        matchedTrial ? "trial" : "actionable",
        matchedTrial ? "当前可小仓" : "当前可分批",
        executionRuleDetail(price, matched),
        { policy, rule: matched },
      );
    }
    const current = policy.current_action || {};
    const reference = Number(current.reference_price);
    if (!Number.isFinite(reference) || current.currency !== quote?.currency) {
      return executionResult(
        "review",
        "缺少可沿用的报告基准价",
        "报告虽允许当时行动，但无法确认现价仍处于同一价格条件",
        { policy },
      );
    }
    if (price > reference + 1e-9) {
      return executionResult(
        "wait_price",
        "等待价格，不追高",
        `现价 ${price.toFixed(2)} 高于报告作出“当前可行动”时的 ${reference.toFixed(2)}，按主报告价格纪律暂停新增买入`,
        { policy, reference },
      );
    }
    const trial = current.action_kind === "trial";
    return executionResult(
      trial ? "trial" : "actionable",
      trial ? "当前可小仓" : "当前可分批",
      `现价 ${price.toFixed(2)} 未高于报告判断基准价 ${reference.toFixed(2)} · ${current.action || "按主报告执行"}`,
      { policy, reference },
    );
  }

  const rule = matchedExecutionRule(rules, price);
  if (!rule) return conditionWaitState(policy, price, rules);
  if (rule.requires_validation || ["price_and_event", "compound"].includes(mode)) {
    return executionResult(
      "validation",
      "价格已到，等待验证",
      `${executionRuleDetail(price, rule)} · 尚需：${rule.validation_condition || policy.event_condition || "报告列明的经营条件"}`,
      { policy, rule },
    );
  }
  const trial = rule.action_kind === "trial";
  return executionResult(
    trial ? "trial" : "actionable",
    trial ? "当前可小仓" : "当前可分批",
    executionRuleDetail(price, rule),
    { policy, rule },
  );
}

export function executionFilterKey(item, quote, fallbackKind = "unknown") {
  return currentExecutionState(item, quote, fallbackKind).key;
}

export function primaryJudgmentAuxiliary(item, quote) {
  const judgment = primaryJudgmentForItem(item);
  if (!judgment) return null;
  if (judgment.action_kind === "unknown" || judgment.model_consensus === false) {
    return {
      label: "暂停自动价格归类",
      detail: "模型结果待人工复核 · 主报告判断暂不进入可买筛选",
      state: "unavailable",
    };
  }
  const price = Number(quote?.price);
  if (!Number.isFinite(price) || quote?.currency !== judgment.currency) {
    return {
      label: "行情暂不可比",
      detail: "看板辅助推导 · 主报告判断不变",
      state: "unavailable",
    };
  }

  const ceiling = Number(judgment.entry_ceiling);
  const trialMin = Number(judgment.trial_range?.min);
  const trialMax = Number(judgment.trial_range?.max);
  if (!Number.isFinite(ceiling)) {
    return {
      label: "报告未给出可执行价格档",
      detail: "看板辅助推导不可用 · 主报告判断保持不变",
      state: "unavailable",
    };
  }
  if (Number.isFinite(ceiling) && price > ceiling) {
    return {
      label: "尚未进入报告买入区",
      detail: `现价 ${price.toFixed(2)}，高于报告最高候选价 ${ceiling.toFixed(2)} · 看板辅助推导`,
      state: "above_entry",
    };
  }
  if (
    Number.isFinite(trialMin)
    && Number.isFinite(trialMax)
    && price >= trialMin
    && price <= trialMax
  ) {
    return {
      label: "小仓试错区",
      detail: `现价 ${price.toFixed(2)}，进入报告 ${trialMin.toFixed(2)}–${trialMax.toFixed(2)} 区间 · 看板辅助推导`,
      state: "trial",
    };
  }
  return {
    label: "已进入报告价格区",
    detail: `现价 ${price.toFixed(2)} · 请按报告价格行动表复核 · 看板辅助推导`,
    state: "inside_entry",
  };
}
