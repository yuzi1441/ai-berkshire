import requests, pathlib, pypdf
items=[('2025年度报告','finalpage/2026-03-28/1225042202.PDF'),('2026年第一季度报告','finalpage/2026-04-30/1225255055.PDF'),('2025年度报告摘要','finalpage/2026-03-28/1225042159.PDF')]
base='https://static.cninfo.com.cn/'
dir=pathlib.Path('research/source_docs/国药现代'); dir.mkdir(parents=True, exist_ok=True)
for title,path in items:
    url=base+path
    out=dir/f'国药现代-{title}-{path.split("/")[-1]}'
    r=requests.get(url, timeout=60, headers={'User-Agent':'Mozilla/5.0'})
    print(title, r.status_code, r.headers.get('content-type'), len(r.content), out)
    out.write_bytes(r.content)
    try:
        reader=pypdf.PdfReader(str(out))
        txt=[]
        for i,p in enumerate(reader.pages):
            txt.append(f'\n--- page {i+1} ---\n'+(p.extract_text() or ''))
        txtout=out.with_suffix('.txt')
        txtout.write_text('\n'.join(txt), encoding='utf-8')
        print(' extracted', len(reader.pages), txtout.stat().st_size, txtout)
    except Exception as e:
        print(' extract err', e)
