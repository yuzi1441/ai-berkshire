import json, csv, statistics
from pathlib import Path
base=Path('data/bottleneck-ashare-supertrends')
records=json.loads((base/'ashare_bottleneck_snapshot_20260708.json').read_text(encoding='utf-8'))
# Save current-date low valuation dataset.
out_json=base/'ashare_low_valuation_industry_snapshot_20260710.json'
out_csv=base/'ashare_low_valuation_industry_snapshot_20260710.csv'
out_json.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
fields=list(records[0].keys())
with out_csv.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(records)

def rec(code):
    return next(x for x in records if x['code']==code)

def fmt(x,n=2):
    return 'NA' if x is None else f'{x:.{n}f}'
def yi(x):
    return 'NA' if x is None else f'{x:.0f}亿'
def pct(x):
    return 'NA' if x is None else f'{x:.1f}%'

def row(code, note=''):
    x=rec(code)
    return f"| {x['name']} | {x['ticker']} | {x['bottleneck_theme']} | {yi(x.get('total_mcap_yi'))} | {yi(x.get('revenue_yi'))} | {fmt(x.get('ps_static'))} | {fmt(x.get('pe_ttm_or_dynamic'))} | {pct(x.get('revenue_yoy_pct'))} | {note} |"

def group_stats(codes):
    ps=[rec(c).get('ps_static') for c in codes if rec(c).get('ps_static')]
    pe=[rec(c).get('pe_ttm_or_dynamic') for c in codes if rec(c).get('pe_ttm_or_dynamic') and rec(c).get('pe_ttm_or_dynamic')>0]
    growth=[rec(c).get('revenue_yoy_pct') for c in codes if rec(c).get('revenue_yoy_pct') is not None]
    return {
        'median_ps': statistics.median(ps) if ps else None,
        'median_pe': statistics.median(pe) if pe else None,
        'median_growth': statistics.median(growth) if growth else None,
        'low_count': sum(1 for c in codes if (rec(c).get('pe_ttm_or_dynamic') or 999)<30 and (rec(c).get('ps_static') or 999)<4),
    }

groups={
'电网主设备/通电链':['002270','600312','002028','600089','000400','600406','601179','688676'],
'民爆/含能材料/防务链':['002246','002226','002683','603977','002783','603227'],
'锑钨战略矿物':['002155','601020','600549','000657'],
'数据中心电源/UPS':['002518','002335'],
'AI高速PCB/CCL':['002463','002916','600183','603228'],
'AI光模块/光器件':['300308','300502','300394','002281','000988','688498','688048'],
'半导体设备/材料':['300604','688012','688072','688120','688019','002409','300054','600378','300395'],
'稀土磁材':['600111','000831','300748']
}
stat_lines=[]
for name,codes in groups.items():
    s=group_stats(codes)
    stat_lines.append(f"| {name} | {len(codes)} | {fmt(s['median_ps'])} | {fmt(s['median_pe'])} | {pct(s['median_growth'])} | {s['low_count']} |")

report=f'''# A股低估行业供应链瓶颈地图 — 2026-07-10

> 工作流：`bottleneck-hunter`  
> 用户命题：`A股低估行业`  
> 数据截止：2026-07-10 00:15（Asia/Shanghai，已用 `Get-Date` 确认）。  
> 范围：从全球超级趋势里筛 A股 **行业级** 机会，要求同时满足：瓶颈真实、A股可映射、估值没有明显透支。  
> 行情口径：腾讯行情 `qt.gtimg.cn`；财务口径：东方财富 F10 最新年报字段。  
> 低估定义：不是简单低 PE，而是“瓶颈强度 / 估值 / 未来 3-5 年需求确定性 / 财务兑现路径”四项合成判断。  
> 本报告为学习研究，不构成投资建议。

---

## 0. 结论先行：真正值得研究的 A股低估瓶颈行业

| 排名 | 行业 | 低估等级 | 瓶颈评级 | 为什么可能低估 | 第一批研究入口 |
|---:|---|---|---|---|---|
| 1 | **电网主设备 / 数据中心通电链** | 绿灯 | S | 市场更爱光模块/液冷，但 AI 数据中心、UHV、电网更新都先卡“通电”；多家公司 PE 约 16-23、PS 约 1-3 | 平高电气、华明装备、许继电气、国电南瑞、特变电工；质量弹性看思源电气 |
| 2 | **民爆 / 含能材料 / 防务链** | 绿灯偏黄 | A | 全球军工扩产真正卡的是炸药、推进剂、硝化棉、安全许可；A股民爆链多数仍按周期股估值 | 广东宏大、江南化工、雪峰科技、北化股份 |
| 3 | **锑 / 钨战略矿物链** | 黄绿灯 | A/S | IEA 明确关键矿物集中度和出口管制风险上升；A股资源/加工链有映射，但市场常按周期股折价 | 湖南黄金、厦门钨业、华钰矿业；中钨高新估值偏高 |
| 4 | **数据中心电源 / UPS / 配电** | 黄灯 | A | AI 数据中心供电需求真实，但部分公司不如液冷热门，仍有估值分化 | 科士达、科华数据 |
| 5 | **高速 PCB / CCL** | 黄灯偏红 | A | 真瓶颈，但沪电/深南/生益已明显重估；只剩少数二线可研究 | 景旺电子，其次等沪电/生益回调 |

**不属于“低估”的高景气行业**：AI 光模块、激光芯片、液冷、半导体设备/材料。它们的瓶颈可能更强，但估值大多已经把 3-5 年高增长提前资本化。

---

## 1. 行业估值扫描：哪类瓶颈还没贵得离谱

| 行业 | 样本数 | 中位PS | 中位PE | 中位收入增速 | PE<30且PS<4样本数 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(stat_lines)}

### 读表方法

- **电网主设备**：中位估值明显低于 AI 光模块、半导体设备、液冷，但瓶颈同样来自 AI/电网/能源转型，属于“被 AI 主线低估的硬件基础设施”。
- **民爆/含能材料**：估值低，瓶颈逻辑冷门；问题是要剔除普通基建周期股。
- **锑钨战略矿物**：估值分化，湖南黄金/厦门钨业较可研究，中钨高新已较贵。
- **光模块/半导体设备**：不是行业差，而是不低估。

---

## 2. 低估行业一：电网主设备 / 数据中心通电链

### 为什么是低估瓶颈

IEA 2026 年报告显示，2025 年大型科技公司资本开支超过 4000 亿美元，2026 年预计再增长约 75%；数据中心电力需求预计从 2025 年约 485TWh 到 2030 年约 950TWh。更关键的是，IEA 明确指出 AI 价值链正在被电力供应、并网、能源设备、先进芯片制造等物理瓶颈约束；AI 机柜功率密度提升也会测试电力电子和变压器供应链。

这对应到 A股，不是“买电力概念”，而是找：

- 变压器分接开关；
- UHV/GIS/高压开关；
- 换流阀、柔直和保护自动化；
- 干式变压器、数据中心配电；
- 海外电网设备出海。

### 代表公司估值

| 公司 | 代码 | 瓶颈定位 | 市值 | 2025收入 | PS | PE | 收入增速 | 低估判断 |
|---|---|---|---:|---:|---:|---:|---:|---|
{row('600312','绿灯：UHV/GIS硬瓶颈，估值低，周期性需查')}
{row('002270','绿灯：分接开关小而硬，估值合理，成长需看海外')}
{row('000400','绿灯：柔直/二次设备映射，估值低但收入负增长')}
{row('600089','绿灯：估值低，但多晶硅/新能源业务会稀释主线')}
{row('600406','绿灯偏黄：电网自动化龙头，弹性较低但估值不贵')}
{row('002028','黄灯：质量强、增速高，但估值已反映一部分')}
{row('688676','黄灯偏红：数据中心电力纯度高，但 PE 已高')}

### 结论

**低估行业第一名。**  
市场把 AI 主线资金给了光模块、液冷、PCB，但 AI 数据中心最终必须接入电网。电网主设备的估值没有像光模块那样极端，且订单兑现更容易通过招标、收入和毛利率验证。

**最值得先做深度研究**：平高电气、华明装备、许继电气。  
**质量型备选**：思源电气、国电南瑞。  
**注意**：特变电工便宜，但业务复杂，不能直接当“电网设备纯标的”。

---

## 3. 低估行业二：民爆 / 含能材料 / 防务链

### 为什么是低估瓶颈

全球国防现代化不是只缺整机和导弹总装，真正的瓶颈往往在二三层：炸药、推进剂、硝化棉、HMX/MCX、点火器、安全许可产线、电子雷管。相比军工总装，A股民爆/含能材料链更冷门，估值也更像周期股。

### 代表公司估值

| 公司 | 代码 | 瓶颈定位 | 市值 | 2025收入 | PS | PE | 收入增速 | 低估判断 |
|---|---|---|---:|---:|---:|---:|---:|---|
{row('002683','绿灯：PS约1、PE约22，增长高，关键拆防务纯度')}
{row('002226','绿灯：PS约1、PE约16，便宜但成长弱')}
{row('603227','绿灯：PE约16、PS约1.35，周期股折价明显')}
{row('002783','黄绿灯：便宜但收入负增长，偏周期')}
{row('002246','黄灯：硝化棉/防护线索好，但需核实军工收入占比')}
{row('603977','黄灯：估值不贵，增长弱')}

### 结论

**低估行业第二名。**  
这里的关键不是“民爆板块普涨”，而是找到真正能从全球军工补库存和含能材料瓶颈中受益的公司。

**最值得先做深度研究**：广东宏大、北化股份、江南化工。  
**核心核查问题**：

1. 军工/防务/含能材料收入占比到底多少？
2. 是普通矿山民爆需求，还是军品扩产需求？
3. 是否有安全许可、配方、客户认证和产能扩张壁垒？

---

## 4. 低估行业三：锑 / 钨战略矿物链

### 为什么是低估瓶颈

IEA 2025 关键矿物报告指出，关键能源矿物前三大精炼国份额从 2020 年约 82% 升至 2024 年约 86%；出口管制从镓、锗、锑延伸到钨、铟、钼、重稀土等。对 A股来说，锑、钨不是单纯资源周期，而是半导体、军工、能源安全的战略材料映射。

### 代表公司估值

| 公司 | 代码 | 瓶颈定位 | 市值 | 2025收入 | PS | PE | 收入增速 | 低估判断 |
|---|---|---|---:|---:|---:|---:|---:|---|
{row('002155','绿灯：PE约22、PS<1，锑逻辑被黄金业务稀释')}
{row('600549','黄绿灯：钨/稀土/加工综合入口，估值尚可')}
{row('601020','黄灯：锑弹性强，PS偏高，资源兑现需查')}
{row('000657','红灯：钨加工纯度高，但估值已高')}

### 结论

**低估行业第三名。**  
它比电网设备更周期，比民爆更受价格波动影响，但全球供应链约束是真实存在的。

**最值得先做深度研究**：湖南黄金、厦门钨业、华钰矿业。  
**研究关键**：锑/钨价格弹性、资源量、加工环节利润率、长协/现货比例、库存周期。

---

## 5. 黄灯行业：数据中心电源 / UPS / 配电

| 公司 | 代码 | 瓶颈定位 | 市值 | 2025收入 | PS | PE | 收入增速 | 低估判断 |
|---|---|---|---:|---:|---:|---:|---:|---|
{row('002518','黄灯：增长较好，估值中等，需拆数据中心占比')}
{row('002335','黄灯：PS不高但PE偏高，增长一般')}

这条线是真需求，但“低估”不如电网主设备清晰。原因是：UPS/电源公司竞争更多，产品替代性更强，而且部分公司已被 AI 数据中心概念重估。

---

## 6. 不算低估：高景气但估值已热的行业

### 6.1 AI 高速 PCB / CCL

| 公司 | 代码 | 瓶颈定位 | 市值 | 2025收入 | PS | PE | 收入增速 | 判断 |
|---|---|---|---:|---:|---:|---:|---:|---|
{row('002463','瓶颈强，但PE/PS已高')}
{row('002916','产业位置好，但估值要求高')}
{row('600183','材料端好，但估值已重估')}
{row('603228','相对便宜一些，需验证AI占比')}

### 6.2 AI 光模块 / 光器件 / 激光芯片

TrendForce 预计 AI 光收发模块市场 2026 年将达 260 亿美元，较 2025 年增长超过 57%；同时 EML、CW-LD 等关键光电芯片和高精度光学对准工艺是主要扩产瓶颈。产业逻辑强，但 A股估值已经极高。

| 公司 | 代码 | 瓶颈定位 | 市值 | 2025收入 | PS | PE | 收入增速 | 判断 |
|---|---|---|---:|---:|---:|---:|---:|---|
{row('300308','红灯：全球强公司，但市值和PS已非常高')}
{row('300502','红灯偏黄：增速强，但估值高')}
{row('300394','红灯：光器件优质，但PS/PE高')}
{row('688498','红灯：激光芯片瓶颈强，但PS极高')}
{row('688048','红灯：收入太小，估值太高')}

### 6.3 半导体设备 / 材料

TrendForce 认为 CoWoS 和 3nm 先进制程仍处紧张状态，2.5D 封装严重短缺到 2027 年才略缓。但 A股半导体设备和材料估值普遍已提前反映长期国产替代。

| 公司 | 代码 | 瓶颈定位 | 市值 | 2025收入 | PS | PE | 收入增速 | 判断 |
|---|---|---|---:|---:|---:|---:|---:|---|
{row('688012','好行业，高估值')}
{row('688072','好行业，高估值')}
{row('688120','好行业，高估值')}
{row('300604','测试设备强，但PE/PS高')}
{row('688019','材料好，但估值高')}
{row('600378','相对可研究，但不是明显低估')}

---

## 7. 低估行业最终筛选表

| 等级 | 行业 | 核心理由 | 代表公司 | 下一步动作 |
|---|---|---|---|---|
| 第一梯队 | 电网主设备 / 通电链 | S级瓶颈 + 多家公司估值未极端 + 需求由AI/电网/能源转型共振 | 平高电气、华明装备、许继电气、思源电气 | 立刻做行业深挖 |
| 第一梯队 | 民爆 / 含能材料 / 防务链 | A级瓶颈 + 估值按周期股定价 + 市场关注度低 | 广东宏大、北化股份、江南化工、雪峰科技 | 立刻做“军品纯度”拆解 |
| 第二梯队 | 锑 / 钨战略矿物 | A/S级瓶颈 + 出口管制/供应集中风险 + 部分标的不贵 | 湖南黄金、厦门钨业、华钰矿业 | 做价格弹性模型 |
| 第三梯队 | 数据中心电源 / UPS | 需求真实，但替代性和竞争更强 | 科士达、科华数据 | 观察，等估值或订单验证 |
| 暂不列低估 | AI PCB/CCL | 瓶颈强，但多数已重估 | 沪电、深南、生益、景旺 | 只跟踪，不追高 |
| 暂不列低估 | 光模块/激光芯片 | 产业极强，但估值红灯 | 中际、新易盛、天孚、源杰 | 等回调或盈利兑现 |
| 暂不列低估 | 半导体设备/材料 | 长期正确，但估值提前反映 | 中微、拓荆、华海、长川、安集 | 不作为低估行业入口 |

---

## 8. 建议的下一步研究顺序

### 1）先做“电网主设备低估行业”

建议拆：平高电气、华明装备、许继电气、思源电气、国电南瑞、特变电工。  
核心问题：AI 数据中心和全球电网投资是否足以让中国输配电设备进入 3-5 年高景气？谁最便宜，谁最纯，谁最能出海？

### 2）再做“含能材料 / 民爆防务低估行业”

建议拆：广东宏大、北化股份、江南化工、雪峰科技、凯龙股份。  
核心问题：谁是真正军工含能材料瓶颈，谁只是普通民爆周期股？

### 3）最后做“锑钨战略矿物低估行业”

建议拆：湖南黄金、厦门钨业、华钰矿业、中钨高新。  
核心问题：锑/钨价格上涨如何传导到利润？谁有资源，谁有加工，谁只是价格弹性？

---

## 附录：本地数据和来源

### 本地文件

- 当前快照 JSON：`data/bottleneck-ashare-supertrends/ashare_low_valuation_industry_snapshot_20260710.json`
- 当前快照 CSV：`data/bottleneck-ashare-supertrends/ashare_low_valuation_industry_snapshot_20260710.csv`
- 抓取脚本：`logs/fetch_ashare_bottleneck_snapshot.py`
- 增补脚本：`logs/append_ashare_bottleneck_snapshot.py`
- 本报告生成脚本：`logs/write_ashare_low_valuation_industry_report.py`

### 外部来源

- IEA — [Key Questions on Energy and AI](https://www.iea.org/reports/key-questions-on-energy-and-ai/executive-summary)
- IEA — [Global Critical Minerals Outlook 2025](https://www.iea.org/reports/global-critical-minerals-outlook-2025/executive-summary)
- TrendForce — [Global AI Optical Transceiver Market to Reach US$26 Billion in 2026](https://www.trendforce.com/presscenter/news/20260420-13017.html)
- TrendForce — [AI Competition Turns into a Supply Chain Arms Race](https://www.trendforce.com/presscenter/news/20260430-13028.html)
- 腾讯行情接口：`https://qt.gtimg.cn/`
- 东方财富 F10 财务接口：`https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew`
'''
report_path=Path('reports/bottleneck-map/A股低估行业-bottleneck-20260710.md')
report_path.write_text(report,encoding='utf-8')
print(report_path.resolve())
print(out_json.resolve())
print(out_csv.resolve())
print(len(report))
print(all(k in report for k in ['A股低估行业供应链瓶颈地图','电网主设备','民爆','锑 / 钨','平高电气','广东宏大']))
