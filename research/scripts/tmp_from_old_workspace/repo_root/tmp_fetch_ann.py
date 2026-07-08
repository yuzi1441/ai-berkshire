import requests, json, re
url='https://np-anotice-stock.eastmoney.com/api/security/ann'
params={'page_size':50,'page_index':1,'ann_type':'A','client_source':'web','stock_list':'601126','f_node':'0','s_node':'0'}
r=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.url)
print(r.status_code, r.text[:500])
data=r.json(); print(data.keys());
for item in data.get('data',{}).get('list',[])[:20]:
    print(item.get('title'), item.get('notice_date'), item.get('art_code'), item.get('columns'))
    print(item.get('attach_url'))
