import json, subprocess, urllib.parse
from pathlib import Path
base='https://datacenter.eastmoney.com/securities/api/data/get'
params={'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL','filter':'(SECUCODE%3D%22600276.SH%22)','p':'1','ps':'12','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
# build manually because quoted filter easier encoded
url='https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL&filter=(SECUCODE%3D%22600276.SH%22)&p=1&ps=12&sr=-1&st=REPORT_DATE&source=HSF10&client=PC'
txt=subprocess.check_output(['curl.exe','-s','--noproxy','*','-H','User-Agent: Mozilla/5.0',url],timeout=30).decode('utf-8')
Path('data/hengrui_mainfina_all.json').write_text(txt, encoding='utf-8')
raw=subprocess.check_output(['curl.exe','-s','--noproxy','*','-H','User-Agent: Mozilla/5.0','https://qt.gtimg.cn/q=sh600276'],timeout=30).decode('gbk','replace')
Path('data/hengrui_quote_raw.txt').write_text(raw,encoding='utf-8')
print('saved', len(txt), len(raw))
