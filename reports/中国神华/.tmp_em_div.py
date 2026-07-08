import urllib.request, urllib.parse, json, pathlib, re
params={
 'reportName':'RPT_F10_DIVIDEND','columns':'ALL','quoteColumns':'','filter':'(SECUCODE="601088.SH")','pageNumber':'1','pageSize':'10','sortTypes':'-1','sortColumns':'REPORT_DATE','source':'HSF10','client':'PC'
}
url='https://datacenter.eastmoney.com/securities/api/data/v1/get?'+urllib.parse.urlencode(params)
try:
    txt=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'}),timeout=30).read().decode('utf-8')
    print(txt[:2000])
    pathlib.Path('sources/eastmoney_dividend.json').write_text(txt,encoding='utf-8')
except Exception as e:
    print('ERR',repr(e))
