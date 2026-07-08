import pandas as pd
from pathlib import Path
for f in ['hudian_indicator_sina.csv','hudian_profit_em.csv','hudian_balance_em.csv','hudian_cashflow_em.csv']:
    path=Path('..')/'..'/'data'/f
    df=pd.read_csv(path)
    print('\n===',f, df.shape)
    print(df.head(3).to_string())
    print(df.tail(8).to_string())
