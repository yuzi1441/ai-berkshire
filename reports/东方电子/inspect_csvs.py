import pandas as pd
from pathlib import Path
base=Path('data_snapshots')
for fname in ['em_profit.csv','em_balance.csv','em_cash.csv','sina_indicator.csv','sina_abstract.csv','em_indicator.csv']:
    df=pd.read_csv(base/fname)
    print('\n###',fname,df.shape)
    print(list(enumerate(df.columns)))
    # print first rows selected around date cols
    print(df.head(2).to_string(max_cols=12))
