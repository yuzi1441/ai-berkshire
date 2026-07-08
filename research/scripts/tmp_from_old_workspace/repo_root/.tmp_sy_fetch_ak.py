import akshare as ak, pandas as pd, json
symbol='002028'
funcs=[
 ('stock_individual_info_em', lambda: ak.stock_individual_info_em(symbol=symbol)),
 ('stock_zh_a_spot_em', lambda: ak.stock_zh_a_spot_em()),
 ('stock_financial_analysis_indicator', lambda: ak.stock_financial_analysis_indicator(symbol=symbol)),
 ('stock_financial_analysis_indicator_em', lambda: ak.stock_financial_analysis_indicator_em(symbol=symbol)),
 ('stock_financial_abstract', lambda: ak.stock_financial_abstract(symbol=symbol)),
 ('stock_zh_a_gbjg_em', lambda: ak.stock_zh_a_gbjg_em(symbol=symbol)),
 ('stock_zh_a_disclosure_report_cninfo', lambda: ak.stock_zh_a_disclosure_report_cninfo(symbol=symbol)),
]
for name,fn in funcs:
    print('\n---',name,'---')
    try:
        df=fn()
        print(type(df), getattr(df,'shape',None))
        print(df.head(10).to_string())
        p=f'data/sy_{name}.csv'
        df.to_csv(p,index=False,encoding='utf-8-sig')
        print('saved',p)
    except Exception as e:
        print('ERR',type(e).__name__,e)
