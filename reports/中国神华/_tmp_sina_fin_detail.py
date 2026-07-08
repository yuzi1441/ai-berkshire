import requests
codes=['sh601088','hk01088','sh600188','sh601225','sh601898','sh600011','sh600900','sz000983']
r=requests.get('https://qt.gtimg.cn/q='+','.join(codes),headers={'User-Agent':'Mozilla/5.0'},timeout=20); r.encoding='gbk'
for line in r.text.strip().split('\n'):
 if not line: continue
 left,data=line.split('="',1); data=data.rstrip('";')
 arr=data.split('~')
 code=left.replace('v_','')
 print('\n',code,len(arr))
 for i,v in enumerate(arr[:90]):
  print(i, v)
