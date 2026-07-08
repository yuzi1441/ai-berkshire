import requests, re
urls=['https://www.glassdoor.com/Reviews/BeiGene-Reviews-E916812.htm','https://www.comparably.com/companies/beigene','https://www.indeed.com/cmp/Beigene/reviews']
for url in urls:
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
  print('\nURL',url,'status',r.status_code,'len',len(r.text),'final',r.url)
  txt=re.sub('<[^<]+?>',' ',r.text)
  txt=re.sub('\s+',' ',txt)
  print(txt[:1000])
 except Exception as e: print('ERR',e)
