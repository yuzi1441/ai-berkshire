import requests, re
urls={
'q1_sina':'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12188063&stockid=601088',
'ann_sina':'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12048559&stockid=601088',
'sse_query':'https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?jsonCallBack=jsonpCallback&isPagination=true&productId=601088&keyWord=&securityType=0101,120100,020100,020200,120200&reportType2=DQBG&reportType=ALL&beginDate=2025-01-01&endDate=2026-07-07&pageHelp.pageSize=25&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
for name,url in urls.items():
    print('\n---',name,url)
    try:
        r=requests.get(url,headers=headers,timeout=20)
        print(r.status_code, r.headers.get('content-type'), len(r.content), r.url)
        enc=r.apparent_encoding or r.encoding or 'utf-8'
        print('enc',enc)
        text=r.content.decode(enc,'replace')
        print(text[:2000].replace('\n',' ')[:2000])
        print('pdfs', re.findall(r'https?://[^\"\']+?\.PDF|https?://[^\"\']+?\.pdf|/[^\"\']+?\.pdf', text, re.I)[:20])
    except Exception as e: print('ERR',repr(e))
