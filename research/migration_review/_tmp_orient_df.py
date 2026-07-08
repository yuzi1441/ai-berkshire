import akshare as ak
import pandas as pd
symbol='000682'
print('spot')
try:
    df=ak.stock_zh_a_spot_em()
    row=df[df['代码']==symbol]
    print(row.T.to_string())
except Exception as e: print('spot err',type(e),e)

funcs=['stock_financial_abstract','stock_financial_analysis_indicator']
for f in funcs:
    print('\nFUNC',f)
    try:
        fn=getattr(ak,f)
        try: df=fn(symbol=symbol)
        except TypeError: df=fn(symbol=symbol, start_year='2020')
        print(df.head().to_string())
        print(df.tail().to_string())
        print(df.columns.tolist())
    except Exception as e: print('err',type(e),e)

print('\nindividual info')
try:
    print(ak.stock_individual_info_em(symbol=symbol).to_string())
except Exception as e: print('info err',e)
