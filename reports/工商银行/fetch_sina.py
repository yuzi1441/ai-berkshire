import urllib.request
url='https://money.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/601398/ctrl/2025/displaytype/4.phtml'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
raw=urllib.request.urlopen(req,timeout=20).read()
for enc in ['gb18030','gbk','utf-8']:
 try:
  text=raw.decode(enc)
  print('ENC',enc,'LEN',len(text))
  open('_source/sina_profit.html','w',encoding='utf-8').write(text)
  break
 except Exception as e: print(enc,e)
