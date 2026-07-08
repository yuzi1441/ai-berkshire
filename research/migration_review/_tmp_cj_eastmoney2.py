import requests, pandas as pd, json, pathlib
headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'}
base='https://datacenter.eastmoney.com/securities/api/data/get'
for typ in ['RPT_F10_FINANCE_GBALANCE','RPT_F10_FINANCE_GCASHFLOW','RPT_F10_FINANCE_BALANCE','RPT_F10_FINANCE_CASHFLOW','RPT_DMSK_FN_BALANCE','RPT_DMSK_FN_CASHFLOW']:
  for sty in ['APP_F10_GBALANCE','APP_F10_GCASHFLOW','APP_F10_BALANCE','APP_F10_CASHFLOW']:
    params={'type':typ,'sty':sty,'filter':'(SECUCODE="600900.SH")','p':1,'ps':5,'source':'HSF10','client':'PC'}
    try:
      r=requests.get(base,params=params,headers=headers,timeout=15)
      txt=r.text[:200]
      ok=False
      try:
        js=r.json(); data=(js.get('result') or {}).get('data') or []
        ok=len(data)>0
      except Exception as e: data=[]
      if ok: print('OK',typ,sty,'rows',len(data),'keys',list(data[0].keys())[:20])
      else: print('NO',typ,sty,r.status_code,txt[:80])
    except Exception as e: print('ERR',typ,sty,repr(e))
