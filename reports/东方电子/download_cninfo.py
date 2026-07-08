import requests, pathlib, json
base=pathlib.Path('cninfo_pdfs'); base.mkdir(exist_ok=True)
ann=[
('2025年度报告','finalpage/2026-04-24/1225161855.PDF'),
('2024年度报告','finalpage/2025-04-23/1223215550.PDF'),
('2023年度报告','finalpage/2024-04-19/1219670688.PDF'),
('2022年度报告','finalpage/2023-04-19/1216455460.PDF'),
('2021年度报告','finalpage/2022-04-23/1213057382.PDF'),
('2026一季报','finalpage/2026-04-29/1225233627.PDF'),
]
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
for title,path in ann:
    url='https://static.cninfo.com.cn/'+path
    fn=base/(title+'.PDF')
    if not fn.exists() or fn.stat().st_size<1000:
        r=requests.get(url,headers=headers,timeout=60)
        print(title, r.status_code, r.headers.get('content-type'), len(r.content))
        fn.write_bytes(r.content)
    else:
        print(title,'exists',fn.stat().st_size)
print(base.resolve())
