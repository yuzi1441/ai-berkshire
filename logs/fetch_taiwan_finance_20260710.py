import requests, json, pathlib, csv, urllib3
urllib3.disable_warnings()
twse_targets={'2383','6213','3037','2313','8046','2368','4958','1303'}
rows=[x for x in requests.get('https://openapi.twse.com.tw/v1/opendata/t187ap14_L',timeout=20).json() if x.get('公司代號') in twse_targets]
out=[]
for x in rows:
    out.append({'market':'TWSE','year':x.get('年度'),'quarter':x.get('季別'),'code':x.get('公司代號'),'name':x.get('公司名稱'),'industry':x.get('產業別'),'eps_ntd':x.get('基本每股盈餘(元)'),'revenue_ntd_thousand':x.get('營業收入'),'operating_income_ntd_thousand':x.get('營業利益'),'pre_tax_or_nonop_ntd_thousand':x.get('營業外收入及支出'),'net_income_ntd_thousand':x.get('稅後淨利')})
pathlib.Path('data/ai-pcb-materials').mkdir(parents=True,exist_ok=True)
with open('data/ai-pcb-materials/taiwan_twse_finance_q1_2026_snapshot.csv','w',newline='',encoding='utf-8-sig') as fp:
    w=csv.DictWriter(fp,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print(json.dumps(out,ensure_ascii=False,indent=2))
