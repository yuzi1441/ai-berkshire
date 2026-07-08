import akshare as ak, pandas as pd
pd.set_option('display.max_rows', 80)
pd.set_option('display.max_columns', 20)
for code in ['600312','002028','601179','000400','600406']:
    print('\n###', code)
    try:
        df=ak.stock_financial_abstract(symbol=code)
        cols=['指标','20251231','20241231','20231231','20221231','20211231']
        print(df[df['指标'].isin(['营业总收入','归母净利润','扣非净利润','经营现金流量净额','毛利率','净利率','净资产收益率(加权)','基本每股收益','总资产','总负债','资产负债率'])][[c for c in cols if c in df.columns]].to_string(index=False))
    except Exception as e:
        print(type(e).__name__, e)
