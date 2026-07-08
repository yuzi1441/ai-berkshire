import pdfplumber, pathlib
for fn in ['1225181771_2026年一季度报告.PDF','1224986242_2025年年度报告.PDF','1224992209_关于回购公司股份方案实施完毕暨回购实施结果的公告.PDF','1221697938_关于诉讼事项的公告.PDF','1202181647_关于公司重大资产重组购入资产2015年度业绩承诺实现情况的说明.PDF','1203383069_2016年度重大资产重组购入资产业绩承诺实现情况鉴证报告.PDF','1204700886_2017年度重大资产重组购入资产业绩承诺实现情况鉴证报告.PDF']:
 p=pathlib.Path('sources/huaming')/fn
 print('\n###',fn)
 if not p.exists(): print('missing'); continue
 with pdfplumber.open(p) as pdf:
  for i,page in enumerate(pdf.pages[:20]):
   text=page.extract_text() or ''
   print(f'---p{i+1}---')
   print(text[:3000])
