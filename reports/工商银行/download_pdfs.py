import requests, pathlib, json, re, time
base='https://www.sse.com.cn'
files={
'ICBC_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601398_20260430_VX32.pdf',
'ICBC_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-28/601398_20260328_JYCS.pdf',
'CCB_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601939_20260430_QGW6.pdf',
'ABC_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601288_20260430_4VKP.pdf',
'BOC_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601988_20260430_77QJ.pdf',
'BOCOM_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601328_20260430_UBF0.pdf',
'PSBC_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601658_20260430_QCZR.pdf',
'CMB_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-29/600036_20260429_IO3O.pdf',
'CCB_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-04-28/601939_20260428_JVLD.pdf',
'ABC_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-31/601288_20260331_UYJS.pdf',
'BOC_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-31/601988_20260331_IQO4.pdf',
'BOCOM_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-28/601328_20260328_6CRD.pdf',
'PSBC_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-28/601658_20260328_ZO3F.pdf',
'CMB_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-28/600036_20260328_F53J.pdf',
}
out=pathlib.Path('source_pdfs'); out.mkdir(exist_ok=True)
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
for name,path in files.items():
    f=out/(name+'.pdf')
    if not f.exists() or f.stat().st_size<10000:
        r=requests.get(base+path,headers=headers,timeout=60)
        print(name,r.status_code,len(r.content),r.headers.get('content-type'))
        f.write_bytes(r.content)
    else:
        print(name,'exists',f.stat().st_size)
print('done', out.resolve())
