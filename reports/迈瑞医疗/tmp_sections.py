import pathlib,re
text=(pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for phrase in ['3、医学影像领域','4、新兴业务领域','报告期内，公司医学影像业务实现','报告期内，公司新兴业务实现']:
 idx=text.find(phrase)
 print(phrase, idx)
 if idx!=-1: print(text[idx:idx+5500].replace('\n',' '))
