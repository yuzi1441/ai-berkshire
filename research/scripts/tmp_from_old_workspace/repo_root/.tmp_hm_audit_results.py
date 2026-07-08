import json, pathlib, subprocess, sys
results = [
 {'id':5,'label':'总股本 / 总市值 · 内容','reported_value':8.96,'unit':'亿','fetched_value':8.96225431,'fetched_source':'腾讯行情 sz002270 总股本','fetched_value2':8.96225431,'fetched_source2':'financial_rigor 市值验算输入'},
 {'id':17,'label':'2025 经营现金流 · 东方财富结构化数据','reported_value':6.04,'unit':'亿元','fetched_value':6.0403144289999995,'fetched_source':'东方财富 cashflow_em.csv 2025年报 NETCASH_OPERATE','fetched_value2':6.040314429,'fetched_source2':'2025年报公告镜像'},
 {'id':20,'label':'2026Q1 营业收入 · 年报/季报公告镜像','reported_value':5.30,'unit':'亿元','fetched_value':5.3027178647,'fetched_source':'东方财富 profit_em.csv 2026一季报 TOTAL_OPERATE_INCOME','fetched_value2':5.3027178647,'fetched_source2':'2026Q1公告镜像'},
 {'id':22,'label':'2026Q1 归母净利润 · 年报/季报公告镜像','reported_value':1.63,'unit':'亿元','fetched_value':1.6302654807,'fetched_source':'东方财富 profit_em.csv 2026一季报 PARENT_NETPROFIT','fetched_value2':1.6302654807,'fetched_source2':'2026Q1公告镜像'},
 {'id':24,'label':'2026Q1 经营现金流 · 年报/季报公告镜像','reported_value':0.92,'unit':'亿元','fetched_value':0.9236776455,'fetched_source':'东方财富 cashflow_em.csv 2026一季报 NETCASH_OPERATE','fetched_value2':0.9236776455,'fetched_source2':'2026Q1公告镜像'},
 {'id':34,'label':'2022A · 归母净利','reported_value':3.59,'unit':'亿元','fetched_value':3.5944480174,'fetched_source':'东方财富 profit_em.csv 2022年报 PARENT_NETPROFIT','fetched_value2':3.5944480174,'fetched_source2':'financial_summary_em.json'},
 {'id':42,'label':'2023A · 扣非归母净利','reported_value':5.02,'unit':'亿元','fetched_value':5.0247346631,'fetched_source':'东方财富 profit_em.csv 2023年报 DEDUCT_PARENT_NETPROFIT','fetched_value2':5.0247346631,'fetched_source2':'financial_summary_em.json'},
 {'id':48,'label':'2024A · 归母净利','reported_value':6.14,'unit':'亿元','fetched_value':6.1429872987,'fetched_source':'东方财富 profit_em.csv 2024年报 PARENT_NETPROFIT','fetched_value2':6.1429872987,'fetched_source2':'2025年报比较期公告镜像'},
 {'id':47,'label':'2024A · 毛利率','reported_value':48.80,'unit':'%','fetched_value':48.8020781943,'fetched_source':'东方财富 profit_em.csv 计算 (收入-成本)/收入','fetched_value2':48.8020781943,'fetched_source2':'financial_summary_em.json'},
 {'id':70,'label':'电力设备 · 占比','reported_value':86.63,'unit':'%','fetched_value':86.63,'fetched_source':'2025年报营业收入构成表','fetched_value2':86.63,'fetched_source2':'新浪公告HTML镜像'},
 {'id':73,'label':'数控设备 · 占比','reported_value':10.07,'unit':'%','fetched_value':10.07,'fetched_source':'2025年报营业收入构成表','fetched_value2':10.07,'fetched_source2':'新浪公告HTML镜像'},
 {'id':82,'label':'产品结构 · 当前状态','reported_value':2025.00,'unit':'','fetched_value':2025.00,'fetched_source':'语义误抽：表述年份，报告原文核对','fetched_value2':2025.00,'fetched_source2':'报告读回'},
 {'id':94,'label':'估值过高导致收益率不足 · 领先指标','reported_value':25.00,'unit':'x','fetched_value':25.38,'fetched_source':'腾讯行情 PE TTM 25.38x；报告文字约25x','fetched_value2':25.14,'fetched_source2':'financial_rigor 以2025 EPS验算'},
 {'id':95,'label':'员工持股/股权激励带来短期费用压力 · 领先指标','reported_value':2026.00,'unit':'','fetched_value':2026.00,'fetched_source':'语义误抽：2026Q1年份，报告原文核对','fetched_value2':2026.00,'fetched_source2':'2026Q1公告镜像'},
 {'id':106,'label':'华明装备 · 收盘价','reported_value':19.86,'unit':'元','fetched_value':19.86,'fetched_source':'腾讯行情 sz002270 20260706161454','fetched_value2':19.86,'fetched_source2':'financial_rigor 验算输入'},
 {'id':117,'label':'国电南瑞 · PB','reported_value':3.74,'unit':'','fetched_value':3.74,'fetched_source':'腾讯行情 sh600406','fetched_value2':3.74,'fetched_source2':'peer_quotes_tencent.json'},
 {'id':122,'label':'中国西电 · 收盘价','reported_value':14.02,'unit':'元','fetched_value':14.02,'fetched_source':'腾讯行情 sh601179','fetched_value2':14.02,'fetched_source2':'peer_quotes_tencent.json'},
 {'id':125,'label':'中国西电 · PB','reported_value':3.11,'unit':'','fetched_value':3.11,'fetched_source':'腾讯行情 sh601179','fetched_value2':3.11,'fetched_source2':'peer_quotes_tencent.json'},
 {'id':128,'label':'许继电气 · PE TTM','reported_value':20.08,'unit':'','fetched_value':20.08,'fetched_source':'腾讯行情 sz000400','fetched_value2':20.08,'fetched_source2':'peer_quotes_tencent.json'},
 {'id':134,'label':'乐观 · 较 19.86 元涨跌幅','reported_value':83.00,'unit':'%','fetched_value':83.0,'fetched_source':'financial_rigor three_scenario.txt','fetched_value2':83.0,'fetched_source2':'Decimal工具输出'},
 {'id':139,'label':'中性 · 较 19.86 元涨跌幅','reported_value':16.50,'unit':'%','fetched_value':16.5,'fetched_source':'financial_rigor three_scenario.txt','fetched_value2':16.5,'fetched_source2':'Decimal工具输出'},
 {'id':140,'label':'悲观 · EPS 年增速','reported_value':2.00,'unit':'%','fetched_value':2.00,'fetched_source':'financial_rigor three_scenario 输入参数','fetched_value2':2.00,'fetched_source2':'three_scenario.txt'},
 {'id':155,'label':'想加仓者 · 建议','reported_value':15.00,'unit':'元','fetched_value':15.00,'fetched_source':'报告行动区间原文：15—18元','fetched_value2':15.00,'fetched_source2':'报告读回'},
 {'id':157,'label':'重新研究触发点 · 建议','reported_value':800.00,'unit':'kV','fetched_value':800.00,'fetched_source':'语义误抽：±800kV 特高压项目触发点','fetched_value2':800.00,'fetched_source2':'2025年报管理层讨论'}
]
path=pathlib.Path('reports/华明装备/sources/audit_results.json')
path.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(path)
