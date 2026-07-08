import pathlib,re
text=(pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
# print business section chunks pages 23-45 approx based on text positions around 19000-65000
for start in range(19000, 70000, 6000):
 print('\n===== POS',start,'=====')
 print(text[start:start+6000].replace('\n',' '))
