import pathlib,re
text=(pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for kw in ['报告期内，公司生命信息与支持业务','生命信息与支持业务实现营业收入','医学影像业务实现营业收入','新兴业务实现营业收入','医学影像业务','新兴业务类产品','MT 8000','新增订单超过','瑞检生态','超声','微创外科']:
 print('\n====',kw,'====')
 for m in list(re.finditer(re.escape(kw), text))[:5]:
  print('pos',m.start())
  print(text[max(0,m.start()-700):min(len(text),m.end()+1600)].replace('\n',' ')[:2600])
