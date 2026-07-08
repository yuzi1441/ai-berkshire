html=open('reports/工商银行/_tmp_1228714343244328961.html.html',encoding='utf-8').read()
for kw in ['第一季度报告','季度报告','2026年第一季度','2025年度报告','业绩','定期报告','财务报告']:
 idx=html.find(kw)
 print('\nKW',kw,idx)
 print(html[max(0,idx-500):idx+1000] if idx!=-1 else '')