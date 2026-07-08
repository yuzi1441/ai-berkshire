import pathlib,re,json
src=pathlib.Path('reports/联影医疗/sources')
text=(src/'2025Annual.txt').read_text(encoding='utf-8',errors='ignore')
q1=(src/'2026Q1.txt').read_text(encoding='utf-8',errors='ignore')
queries={
'产品线': r'截至报告期末，公司累计向市场推出[^。]{0,200}。',
'中国收入市占率': r'报告期内公司中国市场实现营业收入[^。]{0,250}。',
'海外收入': r'海外[^。]{0,80}营业收入[^。]{0,200}。',
'新增市场第一': r'2025 年蝉联中国新增市场综合市占率第一[^。]{0,100}。',
'研发投入金额': r'研发投入合计[^\n]{0,300}',
'利润分配': r'每10股派发现金红利人民币1\.80元[^。]{0,300}。',
'回购': r'回购[^。]{0,200}。',
'实控人': r'实际控制人[^\n]{0,500}',
'控股股东': r'控股股东[^\n]{0,500}',
'前五客户': r'前五名客户[^\n]{0,800}',
'应收款风险': r'应收[^。]{0,100}风险[^。]{0,300}。',
'供应链风险': r'供应链[^。]{0,100}风险[^。]{0,300}。',
'市场竞争风险': r'市场竞争[^。]{0,100}风险[^。]{0,300}。',
}
for name,pat in queries.items():
 print('\n##',name)
 for m in list(re.finditer(pat,text))[:5]:
  s=max(0,m.start()-200); e=min(len(text),m.end()+300)
  print(text[s:e].replace('\n',' ')[:1000])
  print('---')
print('\n## Q1 snippets')
for pat in ['主要会计数据','营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','总资产','研发投入']:
 print('\n--',pat)
 for m in list(re.finditer(pat,q1))[:3]:
  s=max(0,m.start()-300); e=min(len(q1),m.start()+1200)
  print(q1[s:e].replace('\n',' ')[:1500]); print('---')
