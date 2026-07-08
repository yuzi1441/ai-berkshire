import pdfplumber, pathlib, re
for pdf in ['data/长江电力/annual2025.pdf','data/长江电力/annual2024.pdf']:
    print('\n===',pdf,'===')
    with pdfplumber.open(pdf) as p:
        for i,page in enumerate(p.pages,1):
            txt=page.extract_text() or ''
            if any(k in txt for k in ['未来五年分红','分红规划','现金分红政策','投资者回报规划','每10股派发','派发现金股利','承诺事项','同业竞争','利润分配预案']):
                for kw in ['未来五年分红','分红规划','现金分红政策','投资者回报规划','每10股派发','派发现金股利','承诺事项','同业竞争','利润分配预案']:
                    if kw in txt:
                        idx=txt.find(kw); print('P',i,kw,txt[max(0,idx-300):idx+1000].replace('\n',' ')[:1400]); break
