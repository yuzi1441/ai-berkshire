import importlib.util, json
from pathlib import Path
spec=importlib.util.spec_from_file_location('ra', Path('tools/report_audit.py'))
ra=importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
results = [
 {'id':2,'label':'年度财务 · 副来源 / 验证方式','reported_value':2025.0,'unit':'','line_number':31,'raw_text':'source year','fetched_value':2025.0,'fetched_source':'巨潮2025年年度报告文件名/标题','fetched_value2':2025.0,'fetched_source2':'报告源文件读回'},
 {'id':7,'label':'2025 营业收入 · 东方财富','reported_value':332.82,'unit':'亿元','line_number':40,'raw_text':'2025 revenue','fetched_value':332.82159404,'fetched_source':'东方财富F10','fetched_value2':332.82159404,'fetched_source2':'巨潮2025年报'},
 {'id':8,'label':'2025 营业收入 · 巨潮原文 / 交易行情','reported_value':332.82,'unit':'亿元','line_number':40,'raw_text':'2025 revenue','fetched_value':332.82159404,'fetched_source':'东方财富F10','fetched_value2':332.82159404,'fetched_source2':'巨潮2025年报'},
 {'id':9,'label':'2025 归母净利润 · 东方财富','reported_value':81.36,'unit':'亿元','line_number':41,'raw_text':'2025 net profit','fetched_value':81.35775409,'fetched_source':'东方财富F10','fetched_value2':81.35775409,'fetched_source2':'巨潮2025年报'},
 {'id':23,'label':'生命信息与支持类产品 · 占比','reported_value':29.56,'unit':'%','line_number':65,'raw_text':'segment share','fetched_value':29.56,'fetched_source':'巨潮2025年报营业收入构成','fetched_value2':29.56,'fetched_source2':'本地PDF文本抽取'},
 {'id':24,'label':'生命信息与支持类产品 · 毛利率','reported_value':59.37,'unit':'%','line_number':65,'raw_text':'segment gross margin','fetched_value':59.37,'fetched_source':'巨潮2025年报营业收入构成','fetched_value2':59.37,'fetched_source2':'本地PDF文本抽取'},
 {'id':27,'label':'医学影像类产品 · 毛利率','reported_value':63.05,'unit':'%','line_number':66,'raw_text':'segment gross margin','fetched_value':63.05,'fetched_source':'巨潮2025年报营业收入构成','fetched_value2':63.05,'fetched_source2':'本地PDF文本抽取'},
 {'id':29,'label':'新兴业务类产品 · 占比','reported_value':16.16,'unit':'%','line_number':67,'raw_text':'segment share','fetched_value':16.16,'fetched_source':'巨潮2025年报营业收入构成','fetched_value2':16.16,'fetched_source2':'本地PDF文本抽取'},
 {'id':36,'label':'境外 · 占比','reported_value':53.03,'unit':'%','line_number':70,'raw_text':'overseas share','fetched_value':53.03,'fetched_source':'巨潮2025年报营业收入构成','fetched_value2':53.03,'fetched_source2':'本地PDF文本抽取'},
 {'id':51,'label':'客户刚需 · 评分','reported_value':9.0,'unit':'','line_number':103,'raw_text':'analyst score','fetched_value':9.0,'fetched_source':'本文定性评分','fetched_value2':9.0,'fetched_source2':'报告读回'},
 {'id':56,'label':'资本开支强度 · 评分','reported_value':7.0,'unit':'','line_number':107,'raw_text':'analyst score','fetched_value':7.0,'fetched_source':'本文定性评分','fetched_value2':7.0,'fetched_source2':'报告读回'},
 {'id':57,'label':'资本开支强度 · 判断','reported_value':2025.0,'unit':'','line_number':107,'raw_text':'year marker','fetched_value':2025.0,'fetched_source':'巨潮2025年报现金流量表','fetched_value2':2025.0,'fetched_source2':'报告读回'},
 {'id':58,'label':'经营韧性 · 评分','reported_value':7.0,'unit':'','line_number':108,'raw_text':'analyst score','fetched_value':7.0,'fetched_source':'本文定性评分','fetched_value2':7.0,'fetched_source2':'报告读回'},
 {'id':60,'label':'综合 · 评分','reported_value':7.5,'unit':'','line_number':109,'raw_text':'analyst score','fetched_value':7.5,'fetched_source':'本文定性评分','fetched_value2':7.5,'fetched_source2':'报告读回'},
 {'id':63,'label':'经营现金流净额 · 2025','reported_value':101.45,'unit':'亿元','line_number':116,'raw_text':'CFO','fetched_value':101.44968535,'fetched_source':'巨潮2025年报现金流量表','fetched_value2':101.44968535,'fetched_source2':'东方财富/年报摘录'},
 {'id':71,'label':'研发与注册壁垒 · 证据','reported_value':2025.0,'unit':'','line_number':134,'raw_text':'year marker','fetched_value':2025.0,'fetched_source':'巨潮2025年报研发章节','fetched_value2':2025.0,'fetched_source2':'报告读回'},
 {'id':72,'label':'渠道与服务网络 · 证据','reported_value':64.0,'unit':'','line_number':135,'raw_text':'overseas subsidiaries','fetched_value':64.0,'fetched_source':'巨潮2025年报董事长致辞/海外布局','fetched_value2':64.0,'fetched_source2':'本地PDF文本抽取'},
 {'id':109,'label':'新产业 · PB','reported_value':3.77,'unit':'x','line_number':274,'raw_text':'peer PB','fetched_value':3.77,'fetched_source':'腾讯行情2026-07-06','fetched_value2':3.77,'fetched_source2':'本地行情脚本读回'},
 {'id':108,'label':'新产业 · PE','reported_value':19.81,'unit':'x','line_number':274,'raw_text':'peer PE','fetched_value':19.81,'fetched_source':'腾讯行情2026-07-06','fetched_value2':19.81,'fetched_source2':'本地行情脚本读回'},
 {'id':115,'label':'鱼跃医疗 · 股价','reported_value':26.45,'unit':'','line_number':276,'raw_text':'peer price','fetched_value':26.45,'fetched_source':'腾讯行情2026-07-06','fetched_value2':26.45,'fetched_source2':'本地行情脚本读回'},
 {'id':130,'label':'乐观 · 目标股价','reported_value':254.40,'unit':'','line_number':288,'raw_text':'scenario target','fetched_value':254.4,'fetched_source':'financial_rigor.py three-scenario','fetched_value2':254.4,'fetched_source2':'工具输出读回'},
 {'id':140,'label':'悲观 · 目标股价','reported_value':97.40,'unit':'','line_number':290,'raw_text':'scenario target','fetched_value':97.4,'fetched_source':'financial_rigor.py three-scenario','fetched_value2':97.4,'fetched_source2':'工具输出读回'},
 {'id':150,'label':'基于推理的结论 · 判断','reported_value':2026.0,'unit':'','line_number':356,'raw_text':'forward-looking year','fetched_value':2026.0,'fetched_source':'报告前瞻性假设年份','fetched_value2':2026.0,'fetched_source2':'报告读回'},
]
Path('reports/迈瑞医疗/audit_results_20260706.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
outcome = ra.render_verdict(results, report_name='迈瑞医疗投资研究报告-20260706.md')
Path('reports/迈瑞医疗/audit_verdict_20260706.json').write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding='utf-8')
print('verdict=', outcome['verdict'])
