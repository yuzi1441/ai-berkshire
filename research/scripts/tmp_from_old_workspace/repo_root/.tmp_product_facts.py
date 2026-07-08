import re, json
from pathlib import Path
html=Path('sources/sec/2025_10k.html').read_text(encoding='utf-8',errors='ignore')
# collect context id to product/year
ctx={}
for m in re.finditer(r'<xbrli:context id="(c-\d+)">(.*?)</xbrli:context>', html, re.S):
    cid=m.group(1); block=m.group(2)
    prod=re.search(r'dimension="bgne:ProductNameAxis">bgne:([^<]+)</xbrldi:explicitMember>', block)
    start=re.search(r'<xbrli:startDate>([^<]+)</xbrli:startDate>', block)
    end=re.search(r'<xbrli:endDate>([^<]+)</xbrli:endDate>', block)
    if prod and start and end:
        ctx[cid]=(prod.group(1),start.group(1),end.group(1))
# find numeric facts with context refs product
facts=[]
for cid,(prod,start,end) in ctx.items():
    # any ix nonfraction with contextRef=cid
    for m in re.finditer(r'<ix:nonFraction[^>]*contextRef="'+re.escape(cid)+r'"[^>]*name="([^"]+)"[^>]*>(.*?)</ix:nonFraction>', html, re.S):
        name=m.group(1); raw=re.sub('<.*?>','',m.group(2)).strip()
        if raw:
            facts.append((cid,prod,start,end,name,raw))
for f in facts[:200]: print(f)
print('count',len(facts))