import akshare as ak
import pandas as pd
from pathlib import Path
codes=['601179','600089','600550','002028','688676','002270','002922','301012','002112','600019','000959','600362']
rows=[]
for c in codes:
    for kw,cat in [('2025年年度报告','年报'),('2026年第一季度报告','一季报')]:
        try:
            df=ak.stock_zh_a_disclosure_report_cninfo(symbol=c, keyword=kw, category=cat, start_date='20260101', end_date='20260708')
            for _,r in df.head(2).iterrows():
                rows.append({'code':c,'keyword':kw,'title':str(r.get('公告标题','')).replace('<em>','').replace('</em>',''),'date':r.get('公告时间'),'url':r.get('公告链接')})
        except Exception as e:
            rows.append({'code':c,'keyword':kw,'title':'ERROR '+type(e).__name__,'date':'','url':str(e)})
out=Path('data/大型变压器/cninfo_report_links_20260708.csv')
pd.DataFrame(rows).to_csv(out,index=False,encoding='utf-8-sig')
print(out.resolve())
print(pd.DataFrame(rows).head(20).to_string(index=False))
