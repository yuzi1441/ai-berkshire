import requests, pandas as pd, json, pathlib
headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'}
base='https://datacenter.eastmoney.com/securities/api/data/get'
apis={
 'income':('RPT_F10_FINANCE_GINCOME','APP_F10_GINCOME'),
 'balance':('RPT_F10_FINANCE_GBALANCE','APP_F10_GBALANCE'),
 'cashflow':('RPT_F10_FINANCE_GCASHFLOW','APP_F10_GCASHFLOW'),
}
out=pathlib.Path('reports/长江电力/sources'); out.mkdir(parents=True,exist_ok=True)
for name,(typ,sty) in apis.items():
    params={'type':typ,'sty':sty,'filter':'(SECUCODE="600900.SH")','p':1,'ps':100,'source':'HSF10','client':'PC'}
    r=requests.get(base,params=params,headers=headers,timeout=20)
    print(name,r.status_code,r.url)
    js=r.json(); data=js.get('result',{}).get('data',[])
    print('rows',len(data))
    df=pd.DataFrame(data)
    df.to_csv(out/f'eastmoney_{name}.csv',index=False,encoding='utf-8-sig')
    print(df[['REPORT_DATE','REPORT_DATE_NAME','NOTICE_DATE']].head().to_string(index=False))
    print([c for c in df.columns if any(k in c for k in ['TOTAL_OPERATE_INCOME','PARENT_NETPROFIT','NETPROFIT','OPERATE_PROFIT','TOTAL_ASSETS','TOTAL_LIABILITIES','MONETARYFUNDS','TOTAL_CURRENT_ASSETS','TOTAL_CURRENT_LIAB','NETCASH_OPERATE','CONSTRUCT','CAPITAL','DISTRIBUTION'])][:80])
