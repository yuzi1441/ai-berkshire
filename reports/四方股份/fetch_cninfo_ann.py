import akshare as ak
for cat in ['一季报','年报']:
    df=ak.stock_zh_a_disclosure_report_cninfo(symbol='601126', market='沪深京', keyword='', category=cat, start_date='20260101', end_date='20260707')
    print('\nCAT',cat)
    print(df.head(10).to_string())
    df.to_csv(f'cninfo_{cat}.csv',index=False,encoding='utf-8-sig')
