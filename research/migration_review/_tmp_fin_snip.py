html=open('reports/工商银行/_tmp_fin_reports.html',encoding='utf-8').read()
idx=html.find('2025 年度报告')
for kw in ['2025 年度报告','2025年度报告','2025 年度业绩','2026 第一季度','第一季度报告','季度报告','2025年报','2025 Annual','Annual Report']:
 idx=html.find(kw)
 print('\nKW',kw,idx)
 print(html[max(0,idx-1000):idx+2000] if idx!=-1 else '')
print('\nPDF idx', html.find('.pdf'))
print(html[max(0,html.find('.pdf')-1000):html.find('.pdf')+1000])