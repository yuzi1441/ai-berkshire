/* 设计方案共用示例数据 —— 提取自 2026-08-29 看板真实快照，仅用于设计预览 */
const DATA = {
  asOf: "示例数据 · 快照 2026-08-29 · 行情 2026-08-20 16:31",
  quote: { session: "非交易时段", fresh: false, ageText: "行情陈旧 · 9天前", canTrade: 0 },
  counts: { total: 229, a: 93, buy: 0, trial: 2, validation: 3, waitPrice: 64, conflict: 2, redline: 1, review: 6, avoid: 12 },
  indices: [
    { n: "上证指数", v: "3903.72", c: 0.24 }, { n: "深证成指", v: "13972.78", c: 0.59 },
    { n: "创业板指", v: "3495.59", c: 0.64 }, { n: "科创50", v: "1652.97", c: -0.87 },
    { n: "沪深300", v: "4592.75", c: 0.09 }, { n: "中证500", v: "7850.40", c: 0.86 },
    { n: "中证1000", v: "7589.78", c: 0.96 }
  ],
  stocks: [
    {
      name: "东鹏饮料", code: "605499.SH", market: "A股", industry: "饮料乳品",
      price: 123.07, chg: 0.26,
      verdict: "可小额分批", vkind: "buy",
      line: "114–127 元进入稳健分批区，可分批而非一次买满；127–140 元仅小额首批。",
      trigger: "东鹏特饮恢复 10%+ 增长、茶饮料高增且销售费用率不升；费用连续两期多增 10pct 即失效。",
      zones: [
        { label: "重点关注", range: "100–114", min: 100, max: 114, kind: "watch" },
        { label: "稳健分批", range: "114–127", min: 114, max: 127, kind: "buy" },
        { label: "小额首批", range: "127–140", min: 127, max: 140, kind: "trial" }
      ],
      manual: "当前可分批", mkind: "actionable",
      due: "中报已披露 · 待确认费用率",
      senti: { score: 40.6, state: "偏负面", c: 46.2, i: 50.0, m: 3.0 },
      tech: { daily: "防守观察", intra: "关注分批区", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-08-10", report: "2026-08-10 研报"
    },
    {
      name: "洛阳钼业", code: "603993.SH", market: "A股", industry: "工业金属",
      price: 18.27, chg: 1.50,
      verdict: "可小仓验证", vkind: "trial",
      line: "报告基准 19.49 元允许先建 3–5% 观察仓并分批；15–17 元安全边际更充分。",
      trigger: "铜价长期低于 10,000 美元、刚果金重大不利政策、利润增速降档即失效。",
      zones: [
        { label: "强加仓", range: "13–15", min: 13, max: 15, kind: "buy" },
        { label: "安全边际", range: "15–17", min: 15, max: 17, kind: "buy" },
        { label: "3–5% 观察仓", range: "≤19.49", min: 17, max: 19.49, kind: "trial" }
      ],
      manual: "等待更低价格", mkind: "wait_price",
      due: "三季报到期待确认：铜价与 KFM 二期",
      senti: { score: 45.1, state: "中性", c: 49.0, i: 68.4, m: 3.0 },
      tech: { daily: "防守观察", intra: "趋势确认", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-08-18", report: "2026-08-18 研报"
    },
    {
      name: "贵州茅台", code: "600519.SH", market: "A股", industry: "白酒",
      price: 1291.50, chg: -1.25,
      verdict: "价格已到 · 待验证", vkind: "validation",
      line: "已进入 1100–1300 元合理偏低区上沿，可分批但一次不打满；情绪显著负面需分辨错杀或基本面。",
      trigger: "连续两季利润负增长、飞天批价跌破出厂价或治理问题即重审。",
      zones: [
        { label: "分批建仓", range: "900–1100", min: 900, max: 1100, kind: "buy" },
        { label: "合理偏低", range: "1100–1300", min: 1100, max: 1300, kind: "buy" },
        { label: "观察不追", range: "1300–1500", min: 1300, max: 1500, kind: "watch" }
      ],
      manual: "价格已到 · 等待验证", mkind: "validation",
      due: "中报到期待确认：Q2 利润与批价",
      senti: { score: 24.4, state: "显著负面", c: 23.0, i: 34.3, m: 3.0 },
      tech: { daily: "防守观察", intra: "防守观察", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-06-27", report: "2026-06-27 研报"
    },
    {
      name: "东方电子", code: "000682.SZ", market: "A股", industry: "电网设备",
      price: 11.63, chg: 0.43,
      verdict: "小仓验证", vkind: "trial",
      line: "12 元附近可观察仓，10–11 元且基本面未坏时性价比更好；不追「AI+电网」情绪。",
      trigger: "连续 2–3 季扣非增速 >15%、现金流改善、毛利率稳定 32%+ 才升级判断。",
      zones: [
        { label: "重点研究", range: "≤10", min: 8, max: 10, kind: "buy" },
        { label: "观察/小仓", range: "10–13", min: 10, max: 13, kind: "trial" },
        { label: "业绩验证", range: "13–18", min: 13, max: 18, kind: "watch" }
      ],
      manual: "价格已到 · 等待验证", mkind: "validation",
      due: "中报待确认：扣非增速与现金流",
      senti: { score: 54.1, state: "中性", c: 61.0, i: 80.1, m: 3.0 },
      tech: { daily: "趋势确认", intra: "防守观察", conf: "高" },
      dual: "双方当前证据一致", dkind: "consensus",
      cutoff: "2026-07-07", report: "2026-07-07 研报"
    },
    {
      name: "恒瑞医药", code: "600276.SH", market: "A股", industry: "化学制药",
      price: 49.50, chg: -6.00,
      verdict: "模型分歧 ⚠", vkind: "conflict",
      line: "55.75 元不追；等待半年报、CRL 整改、价格 43–46 元三项至少满足两项。",
      trigger: "重大临床、安全性或连续海外质量问题即重审。",
      zones: [
        { label: "重点研究", range: "37–40", min: 37, max: 40, kind: "buy" },
        { label: "稳健分批", range: "43–46", min: 43, max: 46, kind: "buy" },
        { label: "小仓试探", range: "47–50", min: 47, max: 50, kind: "trial" }
      ],
      manual: "待人工复核", mkind: "review",
      due: "中报已披露 · 待确认创新药增速",
      senti: { score: 58.9, state: "偏正面", c: 75.4, i: 54.6, m: 3.0 },
      tech: { daily: "防守观察", intra: "防守观察", conf: "高" },
      dual: "双模型结果分歧", dkind: "conflict",
      cutoff: "2026-07-13", report: "2026-07-13 研报"
    },
    {
      name: "比亚迪", code: "002594.SZ", market: "A股", industry: "乘用车",
      price: 90.48, chg: 2.05,
      verdict: "等待验证", vkind: "watch",
      line: "85 元观望偏积极但不建仓；等待利润拐点、75 元以下安全边际或关税明朗。",
      trigger: "A 股低于 75 元更具边际；Q2/Q3 净利转正、海外毛利率 19%+ 可升级。",
      zones: [
        { label: "积极建仓", range: "<70", min: 55, max: 70, kind: "buy" },
        { label: "分批建仓", range: "70–85", min: 70, max: 85, kind: "buy" },
        { label: "观望/持有", range: "85–110", min: 85, max: 110, kind: "watch" },
        { label: "考虑减仓", range: ">130", min: 130, max: 145, kind: "reduce" }
      ],
      manual: "等待更低价格", mkind: "wait_price",
      due: "中报到期待确认：利润拐点",
      senti: { score: 56.6, state: "偏正面", c: 69.0, i: 64.8, m: 3.0 },
      tech: { daily: "防守观察", intra: "趋势确认", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-06-24", report: "2026-06-24 研报"
    },
    {
      name: "一拖股份", code: "601038.SH", market: "A股", industry: "农机",
      price: 12.93, chg: 1.97,
      verdict: "等待价格", vkind: "watch",
      line: "11.69 元不追价，优先等待 9.5 元附近，或财报证明利润中枢上修。",
      trigger: "9.5–10.5 元仅小仓试错；≤9.0 元才有更厚安全边际。",
      zones: [
        { label: "保守分批", range: "≤9.0", min: 8, max: 9, kind: "buy" },
        { label: "稳健买入", range: "9.0–9.5", min: 9, max: 9.5, kind: "buy" },
        { label: "小仓试错", range: "9.5–10.5", min: 9.5, max: 10.5, kind: "trial" }
      ],
      manual: "等待更低价格", mkind: "wait_price",
      due: "各期财报：利润中枢验证",
      senti: { score: 33.5, state: "偏负面", c: 34.2, i: null, m: 3.0 },
      tech: { daily: "防守观察", intra: "数据不足", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-08-10", report: "2026-08-10 研报"
    },
    {
      name: "美的集团", code: "000333.SZ", market: "A股", industry: "白色家电",
      price: 85.38, chg: 0.78,
      verdict: "等待价格", vkind: "watch",
      line: "当前不追；激进型 ≤75.27 元才小仓，稳健型 68–71 元。",
      trigger: "价格进入区间且扣非利润、现金流不继续恶化。",
      zones: [
        { label: "稳健建仓", range: "68–71", min: 66, max: 71, kind: "buy" },
        { label: "激进小仓", range: "≤75.27", min: 71, max: 75.27, kind: "trial" }
      ],
      manual: "等待更低价格", mkind: "wait_price",
      due: "各期财报：扣非与现金流",
      senti: { score: 49.1, state: "中性", c: 61.9, i: 43.6, m: 3.0 },
      tech: { daily: "趋势确认", intra: "防守观察", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-07-13", report: "2026-07-13 研报"
    },
    {
      name: "紫金矿业", code: "601899.SH", market: "A股", industry: "工业金属",
      price: 34.25, chg: 4.55,
      verdict: "等待价格+半年报", vkind: "watch",
      line: "32.55 元安全边际薄，不追；26–30 元且论文未受损才可小仓分批。",
      trigger: "Kamoa 守住 29 万吨、C1 ≤3 美元/磅；矿产品毛利率 <50% 即红线。",
      zones: [
        { label: "保守分批", range: "≤25", min: 22, max: 25, kind: "buy" },
        { label: "稳健观察", range: "≤26", min: 25, max: 26, kind: "watch" },
        { label: "小仓分批", range: "26–30", min: 26, max: 30, kind: "trial" }
      ],
      manual: "等待更低价格", mkind: "wait_price",
      due: "中报已披露 · 待确认 Kamoa 产量",
      senti: { score: 59.8, state: "偏正面", c: 78.0, i: null, m: 3.0 },
      tech: { daily: "关注分批区", intra: "趋势确认", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-08-03", report: "2026-08-03 研报"
    },
    {
      name: "长江电力", code: "600900.SH", market: "A股", industry: "电力",
      price: 28.16, chg: -0.91,
      verdict: "等待价格", vkind: "watch",
      line: "28.42 元不追；25–26 元小仓试建，23–25 元稳健分批。",
      trigger: "估值 >21 倍而盈利分红未改善、单位电量现金贡献下降即重审。",
      zones: [
        { label: "稳健分批", range: "23–25", min: 22, max: 25, kind: "buy" },
        { label: "小仓试建", range: "25–26", min: 25, max: 26, kind: "trial" }
      ],
      manual: "待人工复核", mkind: "review",
      due: "各期财报：量价与抽蓄 IRR",
      senti: { score: 50.2, state: "中性", c: 55.0, i: 78.3, m: 3.0 },
      tech: { daily: "趋势确认", intra: "趋势确认", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-07-07", report: "2026-07-07 研报"
    },
    {
      name: "分众传媒", code: "002027.SZ", market: "A股", industry: "广告营销",
      price: 4.97, chg: -0.20,
      verdict: "报告可分批 · 已否决 ⚠", vkind: "conflict",
      line: "主报告 4.8–5.3 元可小仓分批；但最新买入前 Checklist 触发治理硬性否决。",
      trigger: "治理问题消除并重新通过 Checklist 前不进入买入流程。",
      zones: [
        { label: "保守分批", range: "3.8–4.2", min: 3.8, max: 4.2, kind: "buy" },
        { label: "稳健分批", range: "4.3–4.8", min: 4.3, max: 4.8, kind: "buy" },
        { label: "小仓分批", range: "4.8–5.3", min: 4.8, max: 5.3, kind: "trial" }
      ],
      manual: "Checklist 硬性否决", mkind: "veto",
      due: "人工确认：治理问题是否消除",
      senti: { score: 53.5, state: "中性", c: 80.0, i: 0.0, m: 3.0 },
      tech: { daily: "防守观察", intra: "防守观察", conf: "高" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-08-05", report: "2026-08-05 研报"
    },
    {
      name: "大普微-UW", code: "301666.SZ", market: "A股", industry: "计算机设备",
      price: 418.13, chg: 0.32,
      verdict: "回避/卖出", vkind: "no",
      line: "705 元、约 3,074 亿市值没有安全边际，坚决回避；等 2027 解禁与更多盈利季度。",
      trigger: "估值回到有安全边际区间且连续盈利后重新研究。",
      zones: [],
      manual: "当前不买", mkind: "no",
      due: "2027 解禁窗口",
      senti: { score: 46.4, state: "中性", c: null, i: 72.9, m: 3.0 },
      tech: { daily: "防守观察", intra: "—", conf: "中" },
      dual: "双方证据不足", dkind: "both_insufficient",
      cutoff: "2026-08-12", report: "2026-08-12 研报"
    },
    {
      name: "腾讯控股", code: "00700.HK", market: "港股", industry: "互联网",
      price: null, chg: null,
      verdict: "持有 · 研究浏览", vkind: "hold",
      line: "港股仅供研究浏览，不计入当前可执行。",
      trigger: "—",
      zones: [],
      manual: null, mkind: null,
      due: "季度跟踪",
      senti: { score: null, state: "—", c: null, i: null, m: null },
      tech: { daily: "—", intra: "—", conf: "—" },
      dual: null, dkind: null,
      cutoff: "2026-07-20", report: "2026-07-20 研报"
    }
  ]
};

/* 判断类型 → 颜色语义 */
const VKIND_COLOR = {
  buy: "#2fbf71", trial: "#7cc4ff", validation: "#f0b429",
  watch: "#9aa7b4", hold: "#9aa7b4", no: "#ff6b6b",
  conflict: "#ff8f3f", reduce: "#ff8f3f"
};
/* 人工复核类型 → 颜色 */
const MKIND_COLOR = {
  actionable: "#2fbf71", trial: "#7cc4ff", validation: "#f0b429",
  wait_price: "#9aa7b4", wait_event: "#9aa7b4", hold: "#9aa7b4",
  no: "#ff6b6b", veto: "#ff4d6d", review: "#c792ea"
};
/* 双模型复核 → 标签 */
const DLABEL = {
  consensus: ["双方一致", "#2fbf71"],
  conflict: ["结果分歧", "#ff6b6b"],
  both_insufficient: ["证据不足/历史", "#8b949e"],
  zcode_current: ["仅ZCode有新证", "#7cc4ff"],
  deepseek_current: ["仅DeepSeek新证", "#7cc4ff"]
};
function fmtPct(v) {
  if (v === null || v === undefined) return "—";
  return (v > 0 ? "+" : "") + v.toFixed(2) + "%";
}
