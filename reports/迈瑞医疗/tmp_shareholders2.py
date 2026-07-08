from pathlib import Path
text=Path('source_pdfs/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['普通股股东总数','股东总数','股东持股情况','SmartcoDevelopment','Magnifice（HK）','EverUnion']:
 print('\n###',term)
 idx=text.find(term, text.find('第六节'))
 print(idx)
 if idx!=-1: print(text[max(0,idx-1000):idx+3000])
