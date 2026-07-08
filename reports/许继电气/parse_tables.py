import pandas as pd
from pathlib import Path
html=Path('sina_xj_2025.html').read_bytes().decode('gbk','ignore')
tables=pd.read_html(html)
print('tables',len(tables))
for i,df in enumerate(tables):
    s=' '.join(map(str,df.astype(str).values.flatten()[:80]))
    if any(term in s for term in ['季侃','胡四全','李俊涛','陆飞','年度报酬','董事长','总经理','高级管理人员','关联交易','前10名股东','分红','承诺']):
        print('\n### table',i,'shape',df.shape)
        print(df.head(20).to_string(index=False))