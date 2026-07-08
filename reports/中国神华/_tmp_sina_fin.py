import requests,re
urls=[
'https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/stockid/601088/ctrl/2025/displaytype/4.phtml',
'https://money.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/601088/ctrl/2025/displaytype/4.phtml',
'https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/601088/ctrl/2025/displaytype/4.phtml',
'https://money.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/601088/ctrl/2025/displaytype/4.phtml',
]
for url in urls:
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 r.encoding='gbk'
 print('\nURL',url,r.status_code,len(r.text),r.url)
 title=re.search(r'<title>(.*?)</title>',r.text,re.S); print(title.group(1) if title else '')
 text=re.sub('<[^>]+>',' ',r.text)
 text=re.sub(r'\s+',' ',text)
 for kw in ['营业收入','归属于母公司所有者的净利润','净利润','经营活动产生的现金流量净额','资产负债率','基本每股收益','净资产收益率']:
  i=text.find(kw)
  print('KW',kw,i,text[i:i+500] if i!=-1 else '')
