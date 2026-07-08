import re, json, subprocess, sys
from pathlib import Path
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\迈瑞医疗')
q1=(base/'sources'/'mindray_2026_q1.txt').read_text(encoding='utf-8')
annual=(base/'sources'/'mindray_2025_annual.txt').read_text(encoding='utf-8')
# Manual facts from extracted source snippets; all RMB unless stated
facts={
 'cutoff':'2026-07-06 23:43 CST',
 'company':'迈瑞医疗','ticker':'300760.SZ',
 'latest_report':'2026年第一季度报告（未审计）','annual_report':'2025年年度报告（安永审计）',
 'q1':{
   'revenue':8352015912.00,'revenue_yoy':1.39,
   'net_profit_parent':2329658005.00,'net_profit_parent_yoy':-11.37,
   'deducted_net_profit':2296470040.00,'deducted_net_profit_yoy':-9.25,
   'ocf':1381035479.00,'ocf_yoy':-7.59,
   'eps_basic':1.9225,'roe_weighted':5.96,
   'total_assets':59614755270.00,'equity_parent':40110091891.00,
   'shareholders':152082,
   'segment':{
     'ivd':{'revenue':3029000000,'yoy':21.01,'intl_growth':'over 20%, intl immuno over 30%','domestic_core_share':'13%'},
     'life_support':{'revenue':2264000000,'yoy':-5.86,'intl_growth':'15%','intl_mix':'79%'},
     'imaging':{'revenue':1396000000,'yoy':-11.83,'intl_growth':'over 10%','intl_mix':'67%'},
     'emerging':{'revenue':1663000000,'yoy':28.50,'intl_growth':'over 40%','domestic_growth':'over 20%'},
   }
 },
 'annual_2025':{
   'revenue':33282159404.00,'revenue_yoy':-9.38,
   'net_profit_parent':8135775409.00,'net_profit_parent_yoy':-30.28,
   'deducted_net_profit':8068550808.00,'deducted_net_profit_yoy':-29.48,
   'ocf':10144968535.00,'ocf_yoy':-18.40,
   'eps_basic':6.7147,'roe_weighted':21.58,
   'total_assets':59266767707.00,'equity_parent':38093330471.00,
   'quarter_revenue':[8237179005,8505824849,9090902689,7448252861],
   'quarter_np_parent':[2628580553,2440186545,2501277420,565730891],
   'segments':{
    'ivd':{'revenue':12240656910.00,'cost':5101259962.00,'gross_margin':58.33,'revenue_yoy':-9.41,'cost_yoy':-0.11,'gm_change':-3.88},
    'life_support':{'revenue':9836723709.00,'cost':3996461004.00,'gross_margin':59.37,'revenue_yoy':-19.80,'cost_yoy':-12.57,'gm_change':-3.36},
    'imaging':{'revenue':5716705579.00,'cost':2112251141.00,'gross_margin':63.05,'revenue_yoy':-18.02,'cost_yoy':-7.47,'gm_change':-4.21},
    'emerging':{'revenue':5377961114.00,'cost':1949887263.00,'gross_margin':63.74,'revenue_yoy':38.85,'cost_yoy':26.65,'gm_change':3.49},
   },
   'domestic_revenue':15631784200.00,'domestic_yoy':-22.97,
   'rd_expense':3578692207.00,
   'finance_expense':-262908161.00,
   'credit_impairment':-196027800.00,
   'inventory_impairment':-319367126.00,
   'goodwill_2025':11404100000.00,
   'goodwill_2024':11093180000.00,
   'ocf_to_np_parent':10144968535.00/8135775409.00,
   'ocf_to_revenue':10144968535.00/33282159404.00,
 },
 'quote':{
   'source_tencent':'qt.gtimg.cn','source_sina':'hq.sinajs.cn',
   'date':'2026-07-06','close':140.60,'prev_close':140.02,'market_cap_billion_tencent':1703.23,'pe_ttm_tencent':21.75,
   'total_shares_tencent':1212441394,
   'float_shares_tencent':1211399283,
   'sina_close':140.60,
   'sina_amount_yuan':1735279183.510
 }
}
out=base/'mindray_facts.json'
out.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding='utf-8')
print(out)
# Derived metrics
for k,v in [('Q1 OCF/NP',facts['q1']['ocf']/facts['q1']['net_profit_parent']),('2025 OCF/NP',facts['annual_2025']['ocf_to_np_parent']),('2025 R&D/rev',facts['annual_2025']['rd_expense']/facts['annual_2025']['revenue'])]:
 print(k, v)
