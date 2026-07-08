import json
for fn in ['tmp_zyzb_0.json','tmp_zyzb_1.json','tmp_zyzb_2.json']:
 print('\n===',fn)
 j=json.load(open(fn,encoding='utf-8'))
 for row in j['data'][:8]:
  keys=['REPORT_DATE','REPORT_TYPE','EPSJB','BPS','TOTALOPERATEREVE','PARENTNETPROFIT','KCFJCXSYJLR','MGJYXJJE','XSMLL','XSJLL','ROEJQ','ROE_DILUTED','ZCFZL','TOTALOPERATEREVETZ','PARENTNETPROFITTZ','KFJLRGDHBZC']
  print({k:row.get(k) for k in keys if k in row})