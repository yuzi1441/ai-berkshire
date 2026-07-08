html=open('reports/工商银行/_tmp_1228714343244328961.html.html',encoding='utf-8').read()
for idx in [html.find('2025年度'), html.find('2025半年度'), html.find('财务报告')]:
 print('\nIDX',idx)
 print(html[max(0,idx-1000):idx+2000])