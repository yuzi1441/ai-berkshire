import akshare as ak, pandas as pd, json, os
os.makedirs('data/002270', exist_ok=True)
items={
'indicator_em': ak.stock_financial_analysis_indicator_em(symbol='002270.SZ'),
'profit_em': ak.stock_profit_sheet_by_report_em(symbol='SZ002270'),
'balance_em': ak.stock_balance_sheet_by_report_em(symbol='SZ002270'),
'cash_em': ak.stock_cash_flow_sheet_by_report_em(symbol='SZ002270'),
'sina_abstract': ak.stock_financial_abstract(symbol='002270'),
'sina_indicator': ak.stock_financial_analysis_indicator(symbol='002270', start_year='2021'),
}
for name,df in items.items():
    df.to_csv(f'data/002270/{name}_20260706.csv', index=False, encoding='utf-8-sig')
    print('\n###',name,df.shape)
    print('COLUMNS')
    print('\n'.join(map(str, df.columns.tolist())))
    print('HEADJSON')
    print(df.head(3).to_json(orient='records', force_ascii=False, date_format='iso')[:3000])
