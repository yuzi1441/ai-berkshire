import requests,re,json
pages={
'annual':'https://money.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/601088/ctrl/2025/displaytype/4.phtml',
'balance':'https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/601088/ctrl/2025/displaytype/4.phtml',
'cash':'https://money.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/601088/ctrl/2025/displaytype/4.phtml',
'ind':'https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/stockid/601088/ctrl/2025/displaytype/4.phtml',
}
for name,url in pages.items():
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20); r.encoding='gbk'
 print('\n====',name, len(r.text))
 # dates from table headers
 for m in re.finditer(r'<th[^>]*>(.*?)</th>',r.text,re.S):
  s=re.sub('<.*?>',' ',m.group(1)); s=re.sub(r'\s+',' ',s).strip()
  if '202' in s: print('TH',s[:80])
 # Print row texts for target keywords
 for kw in ['报表日期','营业收入','营业成本','营业利润','利润总额','归属于母公司所有者的净利润','经营活动产生的现金流量净额','购建固定资产','货币资金','短期借款','长期借款','应付债券','一年内到期的非流动负债','资产总计','负债合计','所有者权益','净资产收益率','资产负债率','销售净利率','每股净资产','基本每股收益']:
  idx=r.text.find(kw)
  if idx!=-1:
   sn=r.text[max(0,idx-500):idx+1000]
   txt=re.sub('<[^>]+>',' ',sn); txt=re.sub(r'\s+',' ',txt).strip()
   print('KW',kw,':',txt[:1200])
