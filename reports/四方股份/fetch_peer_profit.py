import akshare as ak
symbols=['SH601126','SH600406','SZ000400','SH600312','SZ002028']
for sym in symbols:
    print('\n---', sym, 'profit')
    df=ak.stock_profit_sheet_by_report_em(sym)
    print(df.head().to_string())
    print(df.columns.tolist()[:20], df.shape)
