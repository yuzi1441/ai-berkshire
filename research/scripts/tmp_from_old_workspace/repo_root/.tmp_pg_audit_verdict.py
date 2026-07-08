import json, subprocess, pathlib
results = [
 {'id':2,'label':'营业总收入 · 2022','reported_value':92.74,'unit':'亿元','fetched_value':92.742760193,'fetched_source':'AkShare/东方财富','fetched_value2':92.742760193,'fetched_source2':'巨潮2022年报'},
 {'id':7,'label':'归母净利润 · 2021','reported_value':0.71,'unit':'亿元','fetched_value':0.7077424,'fetched_source':'AkShare/东方财富','fetched_value2':0.7077424,'fetched_source2':'巨潮2021年报'},
 {'id':9,'label':'归母净利润 · 2023','reported_value':8.16,'unit':'亿元','fetched_value':8.1571432131,'fetched_source':'AkShare/东方财富','fetched_value2':8.1571432131,'fetched_source2':'巨潮2025年报'},
 {'id':8,'label':'归母净利润 · 2022','reported_value':2.12,'unit':'亿元','fetched_value':2.1216609704,'fetched_source':'AkShare/东方财富','fetched_value2':2.1216609704,'fetched_source2':'巨潮2022年报'},
 {'id':23,'label':'经营现金流净额 · 2025','reported_value':8.11,'unit':'亿元','fetched_value':8.1066012791,'fetched_source':'AkShare/东方财富','fetched_value2':8.1066012791,'fetched_source2':'巨潮2025年报'},
 {'id':24,'label':'经营现金流净额 · 2026Q1','reported_value':10.35,'unit':'亿元','fetched_value':10.3477101524,'fetched_source':'AkShare/东方财富绝对值','fetched_value2':10.3477101524,'fetched_source2':'巨潮2026Q1绝对值'},
 {'id':29,'label':'基本 EPS（元） · 2025','reported_value':0.83,'unit':'元','fetched_value':0.8253,'fetched_source':'AkShare/东方财富','fetched_value2':0.8253,'fetched_source2':'巨潮2025年报'},
 {'id':27,'label':'基本 EPS（元） · 2023','reported_value':0.60,'unit':'元','fetched_value':0.6012,'fetched_source':'AkShare/东方财富','fetched_value2':0.6012,'fetched_source2':'巨潮2025年报'},
 {'id':36,'label':'毛利率 · 2026Q1','reported_value':29.42,'unit':'%','fetched_value':29.42187,'fetched_source':'AkShare/东方财富','fetched_value2':29.42187,'fetched_source2':'巨潮2026Q1推算'},
 {'id':51,'label':'资产负债率 · 2023','reported_value':47.97,'unit':'%','fetched_value':47.96709,'fetched_source':'AkShare/东方财富','fetched_value2':47.96709,'fetched_source2':'巨潮2023年报'},
 {'id':58,'label':'高压板块 · 同比收入增速','reported_value':0.64,'unit':'%','fetched_value':0.64,'fetched_source':'巨潮2025年报','fetched_value2':0.64,'fetched_source2':'年报PDF提取'},
 {'id':56,'label':'高压板块 · 占主营收入','reported_value':62.30,'unit':'%','fetched_value':62.27,'fetched_source':'巨潮2025年报分部收入推算','fetched_value2':62.27,'fetched_source2':'Python复算'},
 {'id':57,'label':'高压板块 · 毛利率','reported_value':27.76,'unit':'%','fetched_value':27.76,'fetched_source':'巨潮2025年报','fetched_value2':27.76,'fetched_source2':'年报PDF提取'},
 {'id':60,'label':'配网板块 · 占主营收入','reported_value':26.20,'unit':'%','fetched_value':26.23,'fetched_source':'巨潮2025年报分部收入推算','fetched_value2':26.23,'fetched_source2':'Python复算'},
 {'id':63,'label':'国际板块 · 2025 收入','reported_value':2.58,'unit':'亿元','fetched_value':2.5778512005,'fetched_source':'巨潮2025年报','fetched_value2':2.5778512005,'fetched_source2':'年报PDF提取'},
 {'id':71,'label':'2025 营业收入 · 公司公告/巨潮','reported_value':125.17,'unit':'亿元','fetched_value':125.1693178456,'fetched_source':'巨潮2025年报','fetched_value2':125.1693178456,'fetched_source2':'AkShare/东方财富'},
 {'id':72,'label':'2025 营业收入 · AkShare/东方财富口径','reported_value':125.17,'unit':'亿元','fetched_value':125.1693178456,'fetched_source':'AkShare/东方财富','fetched_value2':125.1693178456,'fetched_source2':'巨潮2025年报'},
 {'id':109,'label':'中国西电 · 总市值','reported_value':718.65,'unit':'亿元','fetched_value':718.65,'fetched_source':'腾讯行情20260706','fetched_value2':718.65,'fetched_source2':'本地原始行情文件'},
 {'id':108,'label':'中国西电 · PB','reported_value':3.11,'unit':'x','fetched_value':3.11,'fetched_source':'腾讯行情20260706','fetched_value2':3.11,'fetched_source2':'本地原始行情文件'},
 {'id':115,'label':'国电南瑞 · PE(TTM)','reported_value':22.36,'unit':'x','fetched_value':22.36,'fetched_source':'腾讯行情20260706','fetched_value2':22.36,'fetched_source2':'本地原始行情文件'},
 {'id':130,'label':'乐观 · 目标 PE','reported_value':22.00,'unit':'x','fetched_value':22.00,'fetched_source':'financial_rigor三情景参数','fetched_value2':22.00,'fetched_source2':'报告模型输入'},
 {'id':140,'label':'悲观 · 目标 PE','reported_value':12.00,'unit':'x','fetched_value':12.00,'fetched_source':'financial_rigor三情景参数','fetched_value2':12.00,'fetched_source2':'报告模型输入'},
 {'id':157,'label':'行情 hq.sinajs.cn/list=sh600312','reported_value':2026.00,'unit':'','fetched_source':'噪声项-URL/日期误抽，跳过'},
 {'id':151,'label':'市值验算 · 结果','reported_value':17.64,'unit':'元','fetched_value':17.64,'fetched_source':'financial_rigor市值验算','fetched_value2':17.64,'fetched_source2':'腾讯/新浪行情'},
]
cmd=['python','tools/report_audit.py','verdict','--results',json.dumps(results,ensure_ascii=False)]
p=subprocess.run(cmd,cwd=pathlib.Path.cwd(),capture_output=True,text=True,encoding='utf-8')
out=p.stdout+p.stderr
print(out)
path=pathlib.Path('reports/平高电气/report_audit_verdict_20260707.txt')
path.write_text(out,encoding='utf-8')
print('saved', path.resolve())
