from pypdf import PdfReader
from pathlib import Path
p=Path('sources/联影医疗/lianying_annual_20260429_1225233728.pdf')
r=PdfReader(str(p))
text='\n'.join((page.extract_text() or '') for page in r.pages[:20])
Path('data/lianying_pypdf_first20.txt').write_text(text,encoding='utf-8')
print(text[:3000].encode('unicode_escape').decode())
