import pathlib,re
text=(pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for kw in ['受 DRG/DIP','医疗新基建','报告期内，公司生命信息','报告期内，公司医学影像','报告期内，公司新兴业务','迈瑞重症','瑞智','启元','Project2030','M&A','海肽生物','惠泰医疗','DiaSys','国内市场，受']:
 print('\n====',kw,'====')
 for m in list(re.finditer(re.escape(kw), text))[:4]:
  print(text[max(0,m.start()-500):min(len(text),m.end()+2000)].replace('\n',' ')[:2800])
