import pdfplumber, pathlib
p=pathlib.Path('sources/huaming/1221697938_关于诉讼事项的公告.PDF')
with pdfplumber.open(p) as pdf:
 text='\n'.join((page.extract_text() or '') for page in pdf.pages)
 print(text)
