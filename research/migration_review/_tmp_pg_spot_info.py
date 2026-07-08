import akshare as ak
import pandas as pd
from pathlib import Path
base=Path('sources/pgdq'); base.mkdir(exist_ok=True, parents=True)
symbol='600312'
for label,call in [
    ('spot_em', lambda: ak.stock_zh_a_spot_em()),
    ('individual_info_em', lambda: ak.stock_individual_info_em(symbol=symbol)),
]:
    try:
        df=call()
        if label=='spot_em' and '代码' in df.columns: df=df[df['代码']==symbol]
        print('\n',label,df.shape); print(df.T.to_string())
        df.to_csv(base/f'{label}.csv',index=False,encoding='utf-8-sig')
    except Exception as e: print(label,'ERR',repr(e))
