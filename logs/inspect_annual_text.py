from pathlib import Path
text=Path('research/source_docs/中航机载/extracted_text/annual_2025_sina.txt').read_text(encoding='utf-8')
terms=['主营业务分行业情况','主营业务分产品情况','主营业务分地区情况','研发投入','主要控股参股公司分析','前十名股东']
for term in terms:
    idx=text.find(term)
    print('\nTERM', term, 'IDX', idx)
    print(text[idx:idx+2500] if idx!=-1 else 'not found')