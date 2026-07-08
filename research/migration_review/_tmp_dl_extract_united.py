import requests, pathlib, pdfplumber, re, json
root=pathlib.Path('reports')/'联影医疗'/'sources'
root.mkdir(parents=True, exist_ok=True)
base='https://www.sse.com.cn'
files={
 '2026Q1': '/disclosure/listedinfo/announcement/c/new/2026-04-29/688271_20260429_78JE.pdf',
 '2025Annual': '/disclosure/listedinfo/announcement/c/new/2026-04-29/688271_20260429_NTY7.pdf',
 '2024Annual': '/disclosure/listedinfo/announcement/c/new/2025-04-29/688271_20250429_BP0A.pdf',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
for name,path in files.items():
    pdf=root/f'{name}.pdf'
    if not pdf.exists() or pdf.stat().st_size<1000:
        r=requests.get(base+path,headers=headers,timeout=60)
        print(name, r.status_code, len(r.content), r.content[:4])
        pdf.write_bytes(r.content)
    txt=root/f'{name}.txt'
    if not txt.exists() or txt.stat().st_size<1000:
        parts=[]
        with pdfplumber.open(str(pdf)) as p:
            print(name,'pages',len(p.pages))
            for i,pg in enumerate(p.pages):
                t=pg.extract_text(x_tolerance=1,y_tolerance=3) or ''
                if t: parts.append(f'\n---PAGE {i+1}---\n'+t)
        txt.write_text('\n'.join(parts),encoding='utf-8')
    text=txt.read_text(encoding='utf-8',errors='ignore')
    print('\n====',name,'txt chars',len(text),'====')
    for pat in ['主要会计数据','营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','研发投入','资产总额','负债合计','货币资金','存货','应收账款','医用磁共振','管理层讨论']:
        m=re.search(pat,text)
        if m:
            s=max(0,m.start()-300); e=min(len(text),m.start()+1000)
            print('\n--',pat,'--')
            print(text[s:e].replace('\n',' ')[:1500])
