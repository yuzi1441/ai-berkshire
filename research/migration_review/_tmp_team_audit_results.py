import json
from pathlib import Path
results = [
  {"id":1,"field":"股价","reported":106.75,"sources":{"新浪/腾讯行情基准":106.75,"报告验算基准":106.75},"status":"pass","note":"2026-07-06收盘价基准"},
  {"id":2,"field":"总股本","reported":824157988,"sources":{"新浪jsvar/东方财富股本口径":824157988,"报告基准":824157988},"status":"pass","note":"股本一致"},
  {"id":3,"field":"总市值亿元","reported":879.79,"sources":{"financial_rigor.py市值验算":879.79,"106.75*824157988/1e8复算":879.79},"status":"pass","note":"偏差0.00%"},
  {"id":4,"field":"2025营收亿元","reported":138.00,"sources":{"2025年报":138.00,"东方财富/AkShare摘要":138.00},"status":"pass","note":"双源一致"},
  {"id":5,"field":"2025归母净利润亿元","reported":18.69,"sources":{"2025年报":18.69,"东方财富/AkShare摘要":18.69},"status":"pass","note":"双源一致"},
  {"id":6,"field":"2025扣非净利润亿元","reported":17.70,"sources":{"2025年报":17.70,"东方财富/AkShare摘要":17.6984},"status":"pass","note":"偏差小于1%"},
  {"id":7,"field":"2025毛利率%","reported":47.01,"sources":{"新浪/东方财富财务指标":47.01,"financial analyst抽检":47.01},"status":"pass","note":"一致"},
  {"id":8,"field":"2025经营现金流亿元","reported":26.79,"sources":{"2025年报现金流量表":26.79,"新浪/东方财富摘要":26.79},"status":"pass","note":"一致"},
  {"id":9,"field":"2025自由现金流亿元","reported":5.86,"sources":{"OCF26.79-Capex20.93复算":5.86,"financial analyst模型":5.86},"status":"pass","note":"模型计算项"},
  {"id":10,"field":"PE","reported":46.82,"sources":{"financial_rigor.py verify-valuation":46.82,"106.75/2.28复算":46.82},"status":"pass","note":"一致"},
  {"id":11,"field":"PB","reported":4.01,"sources":{"financial_rigor.py verify-valuation":4.01,"106.75/26.65复算":4.01},"status":"pass","note":"一致"},
  {"id":12,"field":"服务收入亿元","reported":17.08,"sources":{"2025年报分部":17.08,"business analyst抽检":17.08},"status":"pass","note":"一致"},
  {"id":13,"field":"境外收入亿元","reported":33.93,"sources":{"2025年报地区收入":33.93,"business/industry analyst抽检":33.93},"status":"pass","note":"一致"},
  {"id":14,"field":"研发投入亿元","reported":26.21,"sources":{"2025年报":26.21,"risk assessor抽检":26.21},"status":"pass","note":"一致"},
  {"id":15,"field":"中性目标价元","reported":97.1,"sources":{"financial_rigor.py three-scenario":97.1,"2.28*(1.10**3)*32复算":97.1},"status":"pass","note":"模型假设项"}
]
p = Path(r'reports/联影医疗/audit_results_team_20260706.json')
p.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(p)
