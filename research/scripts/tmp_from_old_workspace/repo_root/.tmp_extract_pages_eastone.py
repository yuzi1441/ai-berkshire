import pdfplumber, pathlib, re
base=pathlib.Path('data/eastone_000682_raw')
p=base/'1225161855.pdf'
with pdfplumber.open(p) as doc:
    for start,end,name in [(8,18,'business'),(24,31,'op_analysis'),(34,42,'revenue_rd_cash'),(60,70,'directors'),(90,105,'shareholders')]:
        parts=[]
        for i in range(start-1,end):
            if i < len(doc.pages):
                parts.append(f'\n---page {i+1}---\n'+(doc.pages[i].extract_text(x_tolerance=1,y_tolerance=3) or ''))
        (base/f'annual_{name}_p{start}_{end}.txt').write_text('\n'.join(parts),encoding='utf-8')
        print(name, len(parts))
# q1 all
p=base/'1225233627.pdf'
with pdfplumber.open(p) as doc:
    text='\n'.join(f'\n---page {i+1}---\n'+(pg.extract_text() or '') for i,pg in enumerate(doc.pages))
    (base/'q1_all.txt').write_text(text,encoding='utf-8')
    print('q1 pages',len(doc.pages))
