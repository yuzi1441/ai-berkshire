from pathlib import Path
import pandas as pd, json, math, re
base=Path('sources/pgdq')
# Read available CSVs and summarize key items
for f in ['spot_em.csv','individual_info_em.csv','stock_financial_analysis_indicator.csv','stock_dividend_cninfo.csv','stock_fhps_detail_em.csv']:
    p=base/f
    print('\n===',f,p.exists(),p.stat().st_size if p.exists() else '')
    if p.exists():
        df=pd.read_csv(p)
        print(df.head(12).to_string())
        print('cols', df.columns.tolist()[:80])
