import requests, pathlib
urls={
 'q1':'https://file.finance.sina.com.cn/211.154.219.97%3A9494/MRGG/CNSESH_STOCK/2026/2026-4/2026-04-29/12249291.PDF',
 'ir2026apr':'https://sns.sseinfo.com/resources/images/upload/202604/202604302142040972414905.pdf',
 'ir2025apr':'https://sns.sseinfo.com/resources/images/upload/202504/2025043012530341379201354.pdf',
 'ir2025aug':'https://sns.sseinfo.com/resources/images/upload/202509/202509012048053711881924.pdf',
 'ir2025oct':'https://sns.sseinfo.com/resources/images/upload/202510/202510302043016514459751.pdf',
}
pathlib.Path('data').mkdir(exist_ok=True)
for k,u in urls.items():
    try:
        r=requests.get(u,timeout=30)
        print(k,r.status_code,r.headers.get('content-type'),len(r.content))
        pathlib.Path('data',k+'.pdf').write_bytes(r.content)
    except Exception as e:
        print(k,'ERR',repr(e))
