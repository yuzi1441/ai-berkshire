import requests, pathlib
files={
 '四方股份2026年第一季度报告-上交所-static.pdf':'http://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/601126_20260430_8ESA.pdf',
 '四方股份2025年年度报告-上交所-static.pdf':'http://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-24/601126_20260324_2K9N.pdf',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/'}
for name,url in files.items():
    r=requests.get(url,headers=headers,timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:4])
    pathlib.Path(name).write_bytes(r.content)
