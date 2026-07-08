from pathlib import Path
text=Path('sources/cninfo_hmzb/20260227_2025年年度报告.txt').read_text(encoding='utf-8',errors='ignore')
for pat in ['上海华明电力设备集团有限公司','上海华明电力发展有限公司','肖毅','肖日明','肖申','香港中央结算有限公司']:
 print('\nPAT',pat)
 for pos in [m.start() for m in __import__('re').finditer(pat,text)][-5:]:
  print('pos',pos, text[pos-500:pos+1000].replace('\n',' '))