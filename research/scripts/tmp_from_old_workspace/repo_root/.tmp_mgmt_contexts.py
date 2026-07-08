from pathlib import Path
text=Path('data/ar2025_management_pages.txt').read_text(encoding='utf-8')
for needle in ['一、公司董事、监事和高级管理人员情况','任职情况','陈梅芳 女 董事长','吴传彬','朱碧霞','在股东单位任职情况','公司控股股东','实际控制人']:
 idx=text.find(needle)
 print('\n###',needle,idx)
 print(text[max(0,idx-600):idx+2200])
