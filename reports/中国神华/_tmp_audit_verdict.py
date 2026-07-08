import json, subprocess, pathlib, sys
repo=pathlib.Path.cwd()
report='reports/中国神华/中国神华研究报告-20260706.md'
results=[
 {"id":130,"label":"综合评分","reported_value":3.8,"unit":"","fetched_value":3.8,"fetched_source":"四角色评分加权汇总","fetched_value2":3.8,"fetched_source2":"team-lead复算"},
 {"id":7,"label":"Q1后总股本","reported_value":216.89,"unit":"亿股","fetched_value":216.89434304,"fetched_source":"2026Q1报告股本216.89亿元","fetched_value2":216.89434304,"fetched_source2":"腾讯行情总股本21689434304"},
 {"id":9,"label":"H股估算市值","reported_value":8149.66,"unit":"亿元","fetched_value":8149.65745,"fetched_source":"financial_rigor:21689434304*41.02*0.916/1e8","fetched_value2":8149.66,"fetched_source2":"腾讯行情+汇率折算"},
 {"id":8,"label":"A股估算市值","reported_value":9090.04,"unit":"亿元","fetched_value":9090.04192,"fetched_source":"financial_rigor:21689434304*41.91/1e8","fetched_value2":9090.04,"fetched_source2":"腾讯行情返回市值字段"},
 {"id":23,"label":"2025 FCF Yield H股","reported_value":3.27,"unit":"%","fetched_value":3.27,"fetched_source":"266.61/8149.66","fetched_value2":3.27,"fetched_source2":"financial_rigor复算"},
 {"id":24,"label":"2024重述后营业收入","reported_value":3397.88,"unit":"亿元","fetched_value":3397.88,"fetched_source":"2025年报主要会计数据","fetched_value2":3397.88,"fetched_source2":"akshare/sina财务表"},
 {"id":29,"label":"2026Q1利润总额","reported_value":165.94,"unit":"亿元","fetched_value":165.94,"fetched_source":"2026Q1报告","fetched_value2":165.94,"fetched_source2":"q1_cninfo_dump"},
 {"id":27,"label":"2024重述后利润总额","reported_value":829.28,"unit":"亿元","fetched_value":829.28,"fetched_source":"2025年报主要会计数据","fetched_value2":829.28,"fetched_source2":"年报PDF抽取"},
 {"id":36,"label":"2024重述后经营现金流","reported_value":910.86,"unit":"亿元","fetched_value":910.86,"fetched_source":"2025年报主要会计数据","fetched_value2":910.86,"fetched_source2":"akshare/sina财务表"},
 {"id":51,"label":"2025负债合计","reported_value":1463.10,"unit":"亿元","fetched_value":1463.10,"fetched_source":"2025年报主要会计数据","fetched_value2":1463.10,"fetched_source2":"年报PDF抽取"},
 {"id":56,"label":"2025自产煤销售","reported_value":3.32,"unit":"亿吨","fetched_value":3.323,"fetched_source":"2025年报煤炭分部","fetched_value2":3.323,"fetched_source2":"business-analyst年报表"},
 {"id":57,"label":"2026Q1自产煤销售","reported_value":0.78,"unit":"亿吨","fetched_value":0.780,"fetched_source":"2026Q1报告经营数据","fetched_value2":0.780,"fetched_source2":"q1_cninfo_dump"},
 {"id":58,"label":"2025外购煤销售","reported_value":0.99,"unit":"亿吨","fetched_value":0.986,"fetched_source":"2025年报煤炭分部","fetched_value2":0.986,"fetched_source2":"business-analyst年报表"},
 {"id":60,"label":"2025自有铁路周转量","reported_value":313.0,"unit":"十亿吨公里","fetched_value":313.0,"fetched_source":"2025年报运营数据","fetched_value2":313.0,"fetched_source2":"年报PDF抽取"},
 {"id":63,"label":"2026Q1黄骅港装船量","reported_value":0.55,"unit":"亿吨","fetched_value":0.548,"fetched_source":"2026Q1报告经营数据","fetched_value2":0.548,"fetched_source2":"industry-researcher复核"},
 {"id":71,"label":"煤炭利润占比","reported_value":62.1,"unit":"%","fetched_value":62.1,"fetched_source":"465.97/750.83分部利润复算","fetched_value2":62.1,"fetched_source2":"business-analyst分部表"},
 {"id":72,"label":"发电收入","reported_value":891.39,"unit":"亿元","fetched_value":891.39,"fetched_source":"2025年报分部业绩","fetched_value2":891.39,"fetched_source2":"年报PDF抽取"},
 {"id":109,"label":"熊市合理PE","reported_value":10.0,"unit":"x","fetched_value":10.0,"fetched_source":"team-lead情景假设","fetched_value2":10.0,"fetched_source2":"financial-analyst情景估值"},
 {"id":108,"label":"熊市归一化EPS","reported_value":2.0,"unit":"元","fetched_value":2.0,"fetched_source":"team-lead情景假设","fetched_value2":2.0,"fetched_source2":"financial-analyst情景估值"},
 {"id":115,"label":"基准加一年股息后","reported_value":32.0,"unit":"元","fetched_value":32.0,"fetched_source":"2.5*12+2.01四舍五入","fetched_value2":32.0,"fetched_source2":"financial-analyst情景估值"},
]
p=repo/'reports/中国神华/audit_results_20260706.json'
p.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(p)
