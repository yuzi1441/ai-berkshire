import requests, bs4, re
url='https://www.nfra.gov.cn/cn/static/data/DocInfo/SelectByDocId/data_docId=1260352.json'
r=requests.get(url); r.encoding='utf-8'
html=r.json()['data']['docClob']
soup=bs4.BeautifulSoup(html,'html.parser')
text=soup.get_text('\n', strip=True)
print(text[:5000])
