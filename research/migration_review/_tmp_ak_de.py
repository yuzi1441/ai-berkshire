import akshare as ak, pandas as pd, json, traceback
calls=[
 ('stock_individual_info_em', lambda: ak.stock_individual_info_em(symbol='000682')),
 ('stock_financial_abstract', lambda: ak.stock_financial_abstract(symbol='000682')),
 ('stock_financial_abstract_new_ths', lambda: ak.stock_financial_abstract_new_ths(symbol='000682')),
 ('stock_financial_analysis_indicator_em', lambda: ak.stock_financial_analysis_indicator_em(symbol='000682')),
 ('stock_zh_a_spot_em_filter', lambda: ak.stock_zh_a_spot_em()),
]
for name,fn in calls:
    print('\n###',name)
    try:
        df=fn()
        print(type(df), getattr(df,'shape',None))
        if name=='stock_zh_a_spot_em_filter':
            print(df[df.astype(str).apply(lambda row: row.str.contains('000682').any(), axis=1)].head().to_string())
        else:
            print(df.head(20).to_string())
    except Exception as e:
        print('ERR',repr(e)); traceback.print_exc(limit=1)