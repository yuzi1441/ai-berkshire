import pdfplumber, re, pathlib, json
pdf='sources/annual_cypc.pdf'
with pdfplumber.open(pdf) as p:
    print('pages', len(p.pages))
    # search terms
    terms=['主营业务','收入','境内水电','溪洛渡','向家坝','乌东德','白鹤滩','三峡','葛洲坝','装机容量','发电量','售电量','上网电价','综合利用','区域','营业收入','分行业','分产品','电力销售']
    hits={t:[] for t in terms}
    for i,page in enumerate(p.pages,1):
        text=page.extract_text() or ''
        for t in terms:
            if t in text and len(hits[t])<10:
                hits[t].append(i)
    for t,ps in hits.items(): print(t, ps)