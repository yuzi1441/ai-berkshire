import pdfplumber, pathlib
path=pathlib.Path('source_pdfs/CMB_Q1_2026.pdf')
with pdfplumber.open(path) as pdf:
 text='\n'.join((p.extract_text() or '') for p in pdf.pages)
for key in ['贷款和垫款总额','客户贷款和垫款总额','贷款总额','本集团贷款和垫款总额','截至报告期末，本集团贷款']:
 idx=text.find(key)
 print(key, idx, text[idx:idx+500].replace('\n',' | ') if idx!=-1 else '')
