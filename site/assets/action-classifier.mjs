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
