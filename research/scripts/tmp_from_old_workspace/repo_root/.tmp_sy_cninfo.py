import akshare as ak, pandas as pd, json, os
symbol='002028'
queries=[
 ('report_all_2024_2026','', '', '20240101','20260706'),
 ('annual_2025','2025年年度报告', '年报','20260101','20260706'),
 ('q1_2026','2026年第一季度报告','一季报','20260101','20260706'),
]
for name, keyword, cat, start, end in queries:
    print('\n---',name,'---')
    try:
        df=ak.stock_zh_a_disclosure_report_cninfo(symbol=symbol, market='沪深京', keyword=keyword, category=cat, start_date=start, end_date=end)
        print(df.shape)
        print(df.head(20).to_string())
        df.to_csv(f'data/sy_cninfo_{name}.csv',index=False,encoding='utf-8-sig')
    except Exception as e: print('ERR',type(e).__name__,e)
