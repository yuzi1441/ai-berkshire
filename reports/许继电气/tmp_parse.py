from pathlib import Path
from bs4 import BeautifulSoup
raw=Path('sina_xj_2025.html').read_bytes()
text=raw.decode('gbk','ignore')
for term in ['董事长','总经理','李俊涛','陆飞','财务负责人','薪酬','分红','关联交易','实际控制人','控股股东','现金分红','员工']:
    idx=text.find(term)
    print('\nTERM',term,'IDX',idx)
    print(text[idx-200:idx+500] if idx!=-1 else 'not found')