import requests
codes=['sz002270','sz002028','sz002452','sh600406','sh600089']
url='https://hq.sinajs.cn/list='+','.join(codes)
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=20)
r.encoding='gbk'
print(r.status_code,len(r.text)); print(r.text[:2000])
for line in r.text.splitlines():
 if '="' in line:
  code=line.split('_')[-1].split('=')[0]
  arr=line.split('="',1)[1].rstrip('";').split(',')
  print('\n',code, len(arr), arr[:40])
