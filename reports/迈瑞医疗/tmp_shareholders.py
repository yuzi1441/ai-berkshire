from pathlib import Path
text=Path('source_pdfs/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['实际控制人','控股股东','李西廷','Magnifice','Ever Union','Smartco','前10名股东','前十名股东','持股5%以上']:
 print('\n###',term)
 idx=text.find(term)
 print(idx)
 if idx!=-1: print(text[max(0,idx-1000):idx+2200])
