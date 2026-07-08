import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 100)
funcs=['stock_financial_abstract','stock_financial_analysis_indicator','stock_zh_a_spot_em','stock_zh_a_spot','stock_zh_a_hist']
for f in funcs:
    print('\n###', f)
    try:
        obj=getattr(ak,f)
        if f=='stock_financial_abstract':
            df=obj(symbol='601126')
        elif f=='stock_financial_analysis_indicator':
            df=obj(symbol='601126')
        elif f=='stock_zh_a_hist':
            df=obj(symbol='601126', period='daily', start_date='20260706', end_date='20260706', adjust='')
        else:
            df=obj()
            if '代码' in df.columns: df=df[df['代码'].astype(str).str.contains('601126')]
            elif 'code' in df.columns: df=df[df['code'].astype(str).str.contains('601126')]
        print(df.head().to_string())
        print(df.tail().to_string())
        print(df.columns.tolist())
    except Exception as e:
        print('ERR', type(e).__name__, repr(e)[:500])