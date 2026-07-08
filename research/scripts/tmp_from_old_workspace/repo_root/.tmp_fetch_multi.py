import requests, re, json
session=requests.Session(); session.trust_env=False
urls={
 'eastmoney_quote':'https://push2.eastmoney.com/api/qt/stock/get?secid=0.002028&fields=f43,f57,f58,f169,f170,f46,f44,f45,f60,f116,f117,f162,f167,f168,f47,f48,f152,f71,f122,f84,f85,f127,f128,f129,f130',
 'tencent_quote':'http://qt.gtimg.cn/q=sz002028',
 'sina_quote':'https://hq.sinajs.cn/list=sz002028',
 'eastmoney_bal':'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/zcfzbAjaxNew?companyType=4&reportDateType=0&reportType=1&dates=&code=SZ002028',
 'eastmoney_income':'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/lrbAjaxNew?companyType=4&reportDateType=0&reportType=1&dates=&code=SZ002028',
 'eastmoney_cash':'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/xjllbAjaxNew?companyType=4&reportDateType=0&reportType=1&dates=&code=SZ002028',
}
for k,u in urls.items():
 print('\n---',k,'---')
 try:
  r=session.get(u,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'} )
  print(r.status_code,r.headers.get('content-type'),len(r.content),r.url)
  data=r.content
  enc='gbk' if k in ('tencent_quote','sina_quote') else 'utf-8'
  print(data[:2000].decode(enc,'ignore'))
 except Exception as e:
  print('ERR',repr(e))
