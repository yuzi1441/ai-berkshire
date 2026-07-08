import requests, json, re
url='https://np-anotice-stock.eastmoney.com/api/security/ann'
params={'page_size':200,'page_index':1,'ann_type':'A','client_source':'web','stock_list':'601126','f_node':'0','s_node':'0'}
r=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
data=r.json()['data']['list']
for item in data:
    title=item.get('title','')
    if any(k in title for k in ['2025年年度报告','2026年第一季度报告','2024年年度报告','2023年年度报告','2022年年度报告','2025年半年度报告','利润分配','回购','限制性股票','员工持股','关联交易','H股','副总裁','薪酬']):
        print(item.get('notice_date')[:10], item['art_code'], title)
        print('url?', item.get('attach_url'))
