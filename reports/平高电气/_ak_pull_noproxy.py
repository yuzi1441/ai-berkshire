import os
for k in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:
    os.environ.pop(k, None)
import akshare as ak
code='600312'
for name, func in [
    ('stock_zh_a_spot_em', lambda: ak.stock_zh_a_spot_em()),
    ('stock_individual_info_em', lambda: ak.stock_individual_info_em(symbol=code)),
    ('stock_financial_abstract', lambda: ak.stock_financial_abstract(symbol=code)),
    ('stock_financial_analysis_indicator', lambda: ak.stock_financial_analysis_indicator(symbol=code, start_year='2024')),
]:
    try:
        df=func()
        print('\n', name, getattr(df,'shape',None))
        if name=='stock_zh_a_spot_em':
            row=df[df['代码'].astype(str)==code]
            print(row.to_string(index=False))
        else:
            print(df.head(20).to_string(index=False))
    except Exception as e:
        print('ERR', name, type(e).__name__, e)
