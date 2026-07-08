import requests,re,html
from bs4 import BeautifulSoup

def parse(url):
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20); r.encoding='gbk'
    soup=BeautifulSoup(r.text,'html.parser')
    # find table with dates
    txt=soup.get_text(' ',strip=True)
    # print relevant table rows
    rows=[]
    for tr in soup.find_all('tr'):
        cells=[c.get_text(' ',strip=True).replace('\xa0',' ') for c in tr.find_all(['td','th'])]
        if cells: rows.append(cells)
    for row in rows[:5]: print(row)
    print('rows',len(rows))
    for kw in ['报表日期','营业收入','营业利润','利润总额','归属于母公司所有者的净利润','经营活动产生的现金流量净额','购建固定资产、无形资产和其他长期资产所支付的现金','货币资金','短期借款','一年内到期的非流动负债','长期借款','应付债券','资产总计','负债合计']:
      for row in rows:
        if row and kw in row[0]:
          print(kw,row[:8]); break

base='https://money.finance.sina.com.cn/corp/go.php/{}/stockid/601088/ctrl/{}/displaytype/4.phtml'
for endpoint in ['vFD_ProfitStatement','vFD_BalanceSheet','vFD_CashFlow','vFD_FinancialGuideLine']:
  print('\n###',endpoint,2025)
  parse(base.format(endpoint,2025))
  print('\n###',endpoint,2024)
  parse(base.format(endpoint,2024))
