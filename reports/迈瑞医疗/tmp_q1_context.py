import pathlib,re
text=(pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports/mindray_2026_q1.pdf.txt').read_text(encoding='utf-8')
for kw in ['国际业务','体外诊断','生命信息与支持','医学影像','新兴业务','研发投入','分红','市占率','瑞智重症','启元']:
 print('\n====',kw,'====')
 for m in list(re.finditer(re.escape(kw), text))[:8]:
  print('pos',m.start())
  print(text[max(0,m.start()-500):min(len(text),m.end()+1200)].replace('\n',' ')[:2000])
