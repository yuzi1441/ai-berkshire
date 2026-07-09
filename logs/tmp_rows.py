import pandas as pd
from pathlib import Path
f=Path('data/600420/akshare_financial_abstract_20260708.csv')
df=pd.read_csv(f)
print('\n'.join(df['指标'].astype(str).tolist()))
