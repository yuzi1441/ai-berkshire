import pathlib,re
base=pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports'
text=(base/'mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
keywords=['主营业务分行业','主营业务分产品','主营业务分地区','营业收入构成','收入构成','生命信息与支持类产品','体外诊断类产品','医学影像类产品','国际市场','国内市场','分产品','分地区','公司主营业务','2025年，公司实现营业收入','同比']
for kw in keywords:
 print('\n====',kw,'====')
 starts=[m.start() for m in re.finditer(re.escape(kw), text)]
 print('count',len(starts), starts[:10])
 for i,idx in enumerate(starts[:3]):
  print(f'-- hit {i+1} at {idx} --')
  print(text[max(0,idx-1000):min(len(text),idx+2500)].replace('\n',' ')[:4000])
