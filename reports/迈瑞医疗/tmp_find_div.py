from pathlib import Path
text=Path('source_pdfs/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['现金分红','股利分配','利润分配','每10股派发','5,212','市场份额','占有率','全球排名','国内排名','核心竞争力','公司的主要业务']:
 print('\n###',term)
 idx=text.find(term)
 print(idx)
 if idx!=-1: print(text[max(0,idx-900):idx+1800])
