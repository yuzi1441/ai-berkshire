import pathlib
text=(pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
idx=text.find('4、新兴业务领域')
print(idx)
print(text[idx:idx+6500].replace('\n',' '))
