# Old System vs Semantic Compiler Diff Audit

> Counts are derived from Pass-2 adversarial findings and require senior review; the old system was comparison-only, never compiler input.

## Summary

- target/fair value mistaken for entry: 25
- review zone mistaken for entry: 2
- holder/empty-position confusion: 31
- lost prerequisite: 0
- lost AND/OR: 7
- lost AT_LEAST_N: 4
- hard-block mistakes: 0
- action price / valuation confusion: 0
- basically aligned: 3
- ambiguous / cannot determine: 53

## Per Company

| Ticker | Company | Classification |
|---|---|---|
| 000333.SZ | 美的集团 | target/fair value mistaken for entry |
| 000400.SZ | 许继电气 | target/fair value mistaken for entry, holder/empty-position confusion, lost AND/OR |
| 000408.SZ | 藏格矿业 | target/fair value mistaken for entry, holder/empty-position confusion, lost AND/OR |
| 000568.SZ | 泸州老窖 | ambiguous / cannot determine |
| 000651.SZ | 格力电器 | ambiguous / cannot determine |
| 000657.SZ | 中钨高新 | target/fair value mistaken for entry, holder/empty-position confusion |
| 000682.SZ | 东方电子 | holder/empty-position confusion |
| 000858.SZ | 五粮液 | ambiguous / cannot determine |
| 000933.SZ | 神火股份 | target/fair value mistaken for entry, holder/empty-position confusion |
| 000988.SZ | hgtech | target/fair value mistaken for entry, holder/empty-position confusion |
| 002027.SZ | 分众传媒 | target/fair value mistaken for entry, holder/empty-position confusion |
| 002028.SZ | 思源电气 | target/fair value mistaken for entry, review zone mistaken for entry, holder/empty-position confusion |
| 002049.SZ | 紫光国微 | target/fair value mistaken for entry, holder/empty-position confusion |
| 002050.SZ | 浙江三花智能控制股份有限公司 | target/fair value mistaken for entry, holder/empty-position confusion |
| 002142.SZ | 宁波银行 | target/fair value mistaken for entry, holder/empty-position confusion |
| 002155.SZ | 湖南黄金 | ambiguous / cannot determine |
| 002179.SZ | 中航光电科技股份有限公司 | target/fair value mistaken for entry, holder/empty-position confusion, lost AT_LEAST_N |
| 002202.SZ | Goldwind | target/fair value mistaken for entry, holder/empty-position confusion |
| 002226.SZ | 江南化工 | ambiguous / cannot determine |
| 002246.SZ | 北化股份 | ambiguous / cannot determine |
| 002270.SZ | 华明装备 | ambiguous / cannot determine |
| 002272.SZ | chuanrun | ambiguous / cannot determine |
| 002352.SZ | 顺丰控股股份有限公司 | lost AND/OR |
| 002353.SZ | Jereh | ambiguous / cannot determine |
| 002415.SZ | 海康威视 | ambiguous / cannot determine |
| 002463.SZ | 沪电股份 | ambiguous / cannot determine |
| 002594.SZ | BYD | ambiguous / cannot determine |
| 002597.SZ | 金禾实业 | ambiguous / cannot determine |
| 002600.SZ | 领益智造 | ambiguous / cannot determine |
| 002683.SZ | guangdong-hongda | ambiguous / cannot determine |
| 002837.SZ | 英维克 | ambiguous / cannot determine |
| 002916.SZ | 深南电路 | ambiguous / cannot determine |
| 003816.SZ | 中国广核 | ambiguous / cannot determine |
| 300124.SZ | 汇川技术 | ambiguous / cannot determine |
| 300274.SZ | 阳光电源 | ambiguous / cannot determine |
| 300760.SZ | 迈瑞医疗 | ambiguous / cannot determine |
| 301308.SZ | 江波龙 | ambiguous / cannot determine |
| 301666.SZ | DapuStor | target/fair value mistaken for entry, holder/empty-position confusion |
| 600000.SH | 浦发银行 | ambiguous / cannot determine |
| 600031.SH | 三一重工 | ambiguous / cannot determine |
| 600036.SH | 招商银行 | ambiguous / cannot determine |
| 600089.SH | 特变电工 | ambiguous / cannot determine |
| 600141.SH | 兴发集团 | ambiguous / cannot determine |
| 600161.SH | 天坛生物 | ambiguous / cannot determine |
| 600167.SH | 联美量子股份有限公司 | ambiguous / cannot determine |
| 600176.SH | 中国巨石股份有限公司 | ambiguous / cannot determine |
| 600183.SH | 生益科技 | ambiguous / cannot determine |
| 600276.SH | 恒瑞医疗 | ambiguous / cannot determine |
| 600309.SH | 万华化学 | target/fair value mistaken for entry, holder/empty-position confusion |
| 600312.SH | 平高电气 | ambiguous / cannot determine |
| 600372.SH | 中航机载 | ambiguous / cannot determine |
| 600406.SH | 国电南瑞 | target/fair value mistaken for entry, holder/empty-position confusion, lost AT_LEAST_N |
| 600420.SH | 国药现代 | ambiguous / cannot determine |
| 600426.SH | 山东华鲁恒升化工股份有限公司 | basically aligned |
| 600519.SH | 茅台 | target/fair value mistaken for entry, holder/empty-position confusion |
| 600549.SH | 厦门钨业 | target/fair value mistaken for entry, holder/empty-position confusion |
| 600795.SH | guodian-power | ambiguous / cannot determine |
| 600809.SH | 汾酒 | ambiguous / cannot determine |
| 600887.SH | 伊利股份 | holder/empty-position confusion |
| 600900.SH | 长江电力 | ambiguous / cannot determine |
| 600941.SH | 中国移动有限公司 | target/fair value mistaken for entry |
| 601020.SH | 华钰矿业 | ambiguous / cannot determine |
| 601038.SH | 一拖股份 | ambiguous / cannot determine |
| 601088.SH | 中国神华 | holder/empty-position confusion, lost AND/OR |
| 601126.SH | 四方股份 | holder/empty-position confusion, lost AND/OR |
| 601127.SH | 赛力斯 | holder/empty-position confusion |
| 601138.SH | 工业富联 | holder/empty-position confusion, lost AT_LEAST_N |
| 601156.SH | 东方航空物流股份有限公司 | basically aligned |
| 601179.SH | 中国西电 | review zone mistaken for entry, holder/empty-position confusion |
| 601318.SH | 中国平安 | lost AND/OR |
| 601398.SH | 工商银行 | ambiguous / cannot determine |
| 601717.SH | 中创智领 | ambiguous / cannot determine |
| 601727.SH | 上海电气 | target/fair value mistaken for entry, holder/empty-position confusion |
| 601899.SH | 紫金矿业 | basically aligned |
| 601919.SH | 中远海控 | holder/empty-position confusion |
| 601975.SH | 招商局南京油运股份有限公司 | lost AND/OR |
| 603005.SH | jingfang-keji | ambiguous / cannot determine |
| 603129.SH | chunfeng-dongli | target/fair value mistaken for entry, holder/empty-position confusion |
| 603228.SH | 景旺电子 | target/fair value mistaken for entry, holder/empty-position confusion |
| 603288.SH | 海天味业 | ambiguous / cannot determine |
| 603298.SH | 杭叉集团 | ambiguous / cannot determine |
| 603606.SH | 东方电缆 | target/fair value mistaken for entry, holder/empty-position confusion, lost AT_LEAST_N |
| 603659.SH | 璞泰来 | ambiguous / cannot determine |
| 603993.SH | CMOC | ambiguous / cannot determine |
| 605117.SH | deye | ambiguous / cannot determine |
| 605499.SH | 东鹏饮料（集团）股份有限公司 | target/fair value mistaken for entry |
| 688008.SH | montage-tech | ambiguous / cannot determine |
| 688017.SH | leaderdrive | ambiguous / cannot determine |
| 688235.SH | 百济神州 | holder/empty-position confusion |
| 688271.SH | 联影医疗 | ambiguous / cannot determine |
| 688361.SH | skyverse-tech | ambiguous / cannot determine |
| 688676.SH | 金盘科技 | ambiguous / cannot determine |
| 688825.SH | 长鑫存储 | target/fair value mistaken for entry, holder/empty-position confusion |
