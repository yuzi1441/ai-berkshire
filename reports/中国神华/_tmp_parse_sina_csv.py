import requests,re,csv
from bs4 import BeautifulSoup
endpoints={'profit':'vFD_ProfitStatement','balance':'vFD_BalanceSheet','cash':'vFD_CashFlow','ind':'vFD_FinancialGuideLine'}
for endpoint in endpoints.values():
 for year in [2025,2024,2023,2022,2021]:
  url=f'https://money.finance.sina.com.cn/corp/go.php/{endpoint}/stockid/601088/ctrl/{year}/displaytype/4.phtml'
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20); r.encoding='gbk'
  soup=BeautifulSoup(r.text,'html.parser')
  rows=[]
  for tr in soup.find_all('tr'):
   cells=[c.get_text(' ',strip=True).replace('\xa0',' ') for c in tr.find_all(['td','th'])]
   if cells: rows.append(cells)
  print('\n###',endpoint,year)
  for kw in ['报表日期','营业收入','三、营业利润','四、利润总额','五、净利润','归属于母公司所有者的净利润','经营活动产生的现金流量净额','购建固定资产、无形资产和其他长期资产所支付的现金','货币资金','短期借款','一年内到期的非流动负债','长期借款','应付债券','资产总计','负债合计','所有者权益(或股东权益)合计','归属于母公司所有者权益合计','净资产收益率(%)','加权净资产收益率(%)','资产负债率(%)','销售净利率(%)','总资产净利润率(%)','每股净资产_调整后(元)']:
   for row in rows:
    if row and row[0]==kw:
     print(row[:6]); break
