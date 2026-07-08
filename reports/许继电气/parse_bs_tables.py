from bs4 import BeautifulSoup
from pathlib import Path
import pandas as pd
from io import StringIO
html=Path('sina_xj_2025.html').read_bytes().decode('gbk','ignore')
soup=BeautifulSoup(html,'html.parser')
tables=soup.find_all('table')
print('tables',len(tables))
for i,t in enumerate(tables):
    txt=t.get_text(' ',strip=True)
    if any(term in txt for term in ['季侃','胡四全','李俊涛','陆飞','年度报酬','董事长','总经理','高级管理人员','关联交易','前10名股东','分红','承诺']):
        print('\n### raw table',i,'chars',len(txt),'snippet:',txt[:500])
        try:
            df=pd.read_html(StringIO(str(t)))[0]
            print('shape',df.shape)
            print(df.head(15).to_string(index=False))
        except Exception as e:
            print('parse err',e)