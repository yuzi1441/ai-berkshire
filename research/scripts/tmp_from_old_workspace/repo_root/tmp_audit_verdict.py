import sys
sys.path.insert(0, r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\tools')
from report_audit import render_verdict
results=[
 {"id":95,"label":"2025归母净利润","reported_value":11.67,"unit":"亿元","fetched_value":11.6721,"fetched_source":"2025年报","fetched_value2":11.6721,"fetched_source2":"新浪年报HTML"},
 {"id":101,"label":"粗略FCF","reported_value":24.22,"unit":"亿元","fetched_value":24.2193,"fetched_source":"financial_rigor: 26.7038-2.4845","fetched_value2":24.2193,"fetched_source2":"2025年报现金流量表"},
 {"id":105,"label":"分红率","reported_value":40.06,"unit":"%","fetched_value":40.0569,"fetched_source":"financial_rigor: 4.6755/11.6721","fetched_value2":40.06,"fetched_source2":"2025年报披露"},
 {"id":110,"label":"哈表所交易价/2025净利","reported_value":2.69,"unit":"倍","fetched_value":2.6934,"fetched_source":"financial_rigor: 4.404946/1.635465","fetched_value2":2.69,"fetched_source2":"收购公告+2025年报"},
 {"id":115,"label":"估算市值","reported_value":215.03,"unit":"亿元","fetched_value":215.03,"fetched_source":"腾讯行情接口","fetched_value2":215.0,"fetched_source2":"financial_rigor:21.11*1018622249"},
 {"id":116,"label":"静态PE","reported_value":18.31,"unit":"x","fetched_value":18.31,"fetched_source":"financial_rigor:21.11/1.1531","fetched_value2":18.31,"fetched_source2":"2025年报EPS+腾讯收盘价"},
]
render_verdict(results, 'reports/许继电气/许继电气-management-20260707.md')