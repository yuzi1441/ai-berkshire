import pandas as pd
for file in ['data/002270/cash_em_20260706.csv','data/002270/profit_em_20260706.csv','data/002270/balance_em_20260706.csv']:
    df=pd.read_csv(file, nrows=1)
    print('\nFILE',file)
    for c in df.columns:
        uc=c.upper()
        if any(k in uc for k in ['OPERATE','CASH','FIX','INTANG','CONSTRUCT','ASSET','LIAB','PARENT','REVENUE','NETPROFIT','TOTAL_PROFIT','BUY','PURCHASE','PAY']):
            print(c)
