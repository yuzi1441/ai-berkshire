import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 200)
for func,args in [('stock_financial_analysis_indicator', {'symbol':'002226'}),('stock_financial_abstract', {'symbol':'002226'})]:
 print('\n###',func)
 df=getattr(ak,func)(**args)
 print(df.head(30).to_string())
 print(df.columns.tolist()[:20], df.shape)
