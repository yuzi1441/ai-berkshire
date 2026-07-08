import json
from pathlib import Path
items = [
  (1,'股价',106.75,106.75,'新浪/腾讯行情基准'),
  (2,'总股本',824157988,824157988,'新浪jsvar/东方财富股本口径'),
  (3,'总市值亿元',879.79,879.79,'financial_rigor.py市值验算'),
  (4,'2025营收亿元',138.00,138.00,'2025年报/东方财富'),
  (5,'2025归母净利润亿元',18.69,18.69,'2025年报/东方财富'),
  (6,'2025扣非净利润亿元',17.70,17.6984,'2025年报/东方财富'),
  (7,'2025毛利率%',47.01,47.01,'新浪/东方财富财务指标'),
  (8,'2025经营现金流亿元',26.79,26.79,'2025年报现金流量表'),
  (9,'2025自由现金流亿元',5.86,5.86,'OCF-Capex复算'),
  (10,'PE',46.82,46.82,'financial_rigor.py verify-valuation'),
  (11,'PB',4.01,4.01,'financial_rigor.py verify-valuation'),
  (12,'服务收入亿元',17.08,17.08,'2025年报分部'),
  (13,'境外收入亿元',33.93,33.93,'2025年报地区收入'),
  (14,'研发投入亿元',26.21,26.21,'2025年报'),
  (15,'中性目标价元',97.1,97.1,'financial_rigor.py three-scenario'),
]
results=[]
for i,field,reported,fetched,source in items:
    results.append({
        'id': i,
        'field': field,
        'reported_value': reported,
        'fetched_value': fetched,
        'source': source,
        'unit': '',
        'note': 'team report audit sample'
    })
p=Path(r'reports/联影医疗/audit_results_team_20260706.json')
p.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(p)
