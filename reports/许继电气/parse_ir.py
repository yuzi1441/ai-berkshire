from bs4 import BeautifulSoup
from pathlib import Path
html=Path('sina_ir_20260416.html').read_text(encoding='utf-8')
plain=BeautifulSoup(html,'html.parser').get_text('\n')
Path('sina_ir_20260416.txt').write_text(plain,encoding='utf-8')
print(plain[plain.find('公告日期'):plain.find('公告日期')+8000])