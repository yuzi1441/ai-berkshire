import urllib.request, pathlib, gzip, re
cookie='acw_sc__v2=6a4e3ee802c2b76a82acbfd013b940f59685833a'
urls={
'annual_2025':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-28/600420_20260328_Z967.pdf',
'q1_2026':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/600420_20260430_EI4W.pdf',
'profit_2025':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-28/600420_20260328_UW8F.pdf',
'related_2026':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-28/600420_20260328_13X6.pdf',
'finance_company_risk':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-28/600420_20260328_C99V.pdf',
'impairment_2026jan':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-01-27/600420_20260127_WWTP.pdf',
'central_procurement_2026feb':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-02-12/600420_20260212_CSV1.pdf',
'board_2025_change':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2025-12-25/600420_20251225_RYBG.pdf',
'consistency_20260701':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-07-01/600420_20260701_ZWV1.pdf'
}
outdir=pathlib.Path('research/source_docs/国药现代'); outdir.mkdir(parents=True, exist_ok=True)
for name,url in urls.items():
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/','Cookie':cookie,'Accept':'application/pdf,*/*'})
    data=urllib.request.urlopen(req,timeout=30).read()
    # if gzipped, decompress for check but save raw if PDF after decompression? currently likely bytes PDF if cookie accepted
    if data[:2]==b'\x1f\x8b':
        dec=gzip.decompress(data)
        print(name, 'gzip', len(data), dec[:20])
        if dec.startswith(b'%PDF'):
            data=dec
    print(name, len(data), data[:5])
    (outdir/(name+'.pdf')).write_bytes(data)
