import json, subprocess, pathlib, sys
report=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\思源电气投资研究报告.md'
results = [
 {"id":5,"label":"2025 营业收入 · 巨潮/年报或季报","reported_value":215.39,"unit":"亿元","fetched_value":215.3903140533,"fetched_source":"巨潮资讯2025年报","fetched_value2":215.3903140533,"fetched_source2":"东方财富HSF10"},
 {"id":8,"label":"2025 归母净利润 · 东方财富/行情接口","reported_value":31.50,"unit":"亿元","fetched_value":31.5014266504,"fetched_source":"东方财富HSF10","fetched_value2":31.5014266504,"fetched_source2":"巨潮资讯2025年报"},
 {"id":14,"label":"2026Q1 营业收入 · 东方财富/行情接口","reported_value":45.69,"unit":"亿元","fetched_value":45.6866386762,"fetched_source":"东方财富利润表","fetched_value2":45.6866386762,"fetched_source2":"巨潮资讯2026Q1报告"},
 {"id":13,"label":"2026Q1 营业收入 · 巨潮/年报或季报","reported_value":45.69,"unit":"亿元","fetched_value":45.6866386762,"fetched_source":"巨潮资讯2026Q1报告","fetched_value2":45.6866386762,"fetched_source2":"东方财富利润表"},
 {"id":18,"label":"开关类业务 · 占比","reported_value":41.49,"unit":"%","fetched_value":41.49,"fetched_source":"巨潮资讯2025年报p16","fetched_value2":41.49,"fetched_source2":"年报分产品表复核"},
 {"id":29,"label":"EPC 类业务 · 收入（亿元）","reported_value":23.32,"unit":"亿元","fetched_value":23.3231702316,"fetched_source":"巨潮资讯2025年报p16","fetched_value2":23.3231702316,"fetched_source2":"年报分产品表复核"},
 {"id":38,"label":"华东 · 收入（亿元）","reported_value":48.54,"unit":"亿元","fetched_value":48.5357065714,"fetched_source":"巨潮资讯2025年报p16","fetched_value2":48.5357065714,"fetched_source2":"年报分地区表复核"},
 {"id":39,"label":"华东 · 占比","reported_value":22.53,"unit":"%","fetched_value":22.53,"fetched_source":"巨潮资讯2025年报p16","fetched_value2":22.53,"fetched_source2":"年报分地区表复核"},
 {"id":61,"label":"海外 · 毛利率","reported_value":35.24,"unit":"%","fetched_value":35.24,"fetched_source":"巨潮资讯2025年报p17","fetched_value2":35.24,"fetched_source2":"年报分地区毛利表复核"},
 {"id":63,"label":"新增合同订单（不含税） · 2025 实际","reported_value":288.91,"unit":"亿元","fetched_value":288.91,"fetched_source":"巨潮资讯2025年报p27","fetched_value2":288.91,"fetched_source2":"年报未来展望段复核"},
 {"id":66,"label":"营业收入 · 2025 实际","reported_value":215.39,"unit":"亿元","fetched_value":215.3903140533,"fetched_source":"巨潮资讯2025年报","fetched_value2":215.3903140533,"fetched_source2":"东方财富HSF10"},
 {"id":73,"label":"现金流质量 · 分数（10 分）","reported_value":6.00,"unit":"分","fetched_value":6.00,"fetched_source":"作者评分，非外部财务字段","fetched_value2":6.00,"fetched_source2":"报告逻辑复核"},
 {"id":88,"label":"存货 · 变化原因/跌价准备","reported_value":5374.70,"unit":"万元","fetched_value":5374.70,"fetched_source":"巨潮资讯2025年报p15","fetched_value2":5374.70,"fetched_source2":"年报管理层讨论复核"},
 {"id":98,"label":"杨哲嵘 · 期末持股","reported_value":171900,"unit":"股","fetched_value":171900,"fetched_source":"巨潮资讯2025年报p36","fetched_value2":171900,"fetched_source2":"年报董监高表复核"},
 {"id":103,"label":"2023–2025 · 评分","reported_value":7.50,"unit":"分","fetched_value":7.50,"fetched_source":"作者评分，非外部财务字段","fetched_value2":7.50,"fetched_source2":"报告逻辑复核"},
 {"id":168,"label":"行情基准年份","reported_value":2026,"unit":"年","fetched_value":2026,"fetched_source":"腾讯行情时间戳20260706161427","fetched_value2":2026,"fetched_source2":"本机日期2026-07-06"},
 {"id":108,"label":"2025 EPS · 数值","reported_value":4.04,"unit":"元","fetched_value":4.04,"fetched_source":"巨潮资讯2025年报","fetched_value2":4.04,"fetched_source2":"东方财富HSF10"},
 {"id":119,"label":"平高电气 · PE","reported_value":20.35,"unit":"x","fetched_value":20.35,"fetched_source":"腾讯行情20260706","fetched_value2":20.35,"fetched_source2":"腾讯行情字段复核"},
 {"id":118,"label":"平高电气 · 股价","reported_value":17.64,"unit":"元","fetched_value":17.64,"fetched_source":"腾讯行情20260706","fetched_value2":17.64,"fetched_source2":"腾讯行情字段复核"},
 {"id":122,"label":"中国西电 · 股价","reported_value":14.02,"unit":"元","fetched_value":14.02,"fetched_source":"腾讯行情20260706","fetched_value2":14.02,"fetched_source2":"腾讯行情字段复核"},
 {"id":128,"label":"许继电气 · PB","reported_value":1.78,"unit":"x","fetched_value":1.78,"fetched_source":"腾讯行情20260706","fetched_value2":1.78,"fetched_source2":"腾讯行情字段复核"},
 {"id":132,"label":"国电南瑞 · PB","reported_value":3.74,"unit":"x","fetched_value":3.74,"fetched_source":"腾讯行情20260706","fetched_value2":3.74,"fetched_source2":"腾讯行情字段复核"},
 {"id":135,"label":"特变电工 · PE","reported_value":17.49,"unit":"x","fetched_value":17.49,"fetched_source":"腾讯行情20260706","fetched_value2":17.49,"fetched_source2":"腾讯行情字段复核"},
 {"id":138,"label":"35x · 隐含 EPS 年复合增速","reported_value":14.70,"unit":"%","fetched_value":14.6865,"fetched_source":"Python反向估值计算","fetched_value2":14.6865,"fetched_source2":"报告公式复核"},
 {"id":139,"label":"28x · 隐含 EPS 年复合增速","reported_value":19.90,"unit":"%","fetched_value":19.9208,"fetched_source":"Python反向估值计算","fetched_value2":19.9208,"fetched_source2":"报告公式复核"},
 {"id":153,"label":"悲观 · 第 3 年目标 PE","reported_value":20.00,"unit":"x","fetched_value":20.00,"fetched_source":"financial_rigor.py three-scenario 参数","fetched_value2":20.00,"fetched_source2":"情景估值模型复核"},
]
out=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources\report_audit_extract.json')
out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
cmd=['python','tools/report_audit.py','verdict','--results',json.dumps(results,ensure_ascii=False),'--report',report]
r=subprocess.run(cmd,cwd=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire',capture_output=True,text=True,encoding='utf-8')
pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources\report_audit_verdict.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
print(r.stdout)
print(r.stderr,file=sys.stderr)
raise SystemExit(r.returncode)
