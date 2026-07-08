import pathlib,re
text=(pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for start in [98500, 99800, 101500, 105000, 109000, 113000, 117000, 121000]:
 print('\n===== POS',start,'=====')
 print(text[start:start+5000].replace('\n',' '))
