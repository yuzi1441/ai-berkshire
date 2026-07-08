from pathlib import Path
text=Path('sources/mindray_2025_annual.txt').read_text(encoding='utf-8')
for pat in ['医疗器械行','业 分产品','公司主营业务数据统计口径','地区','境内','境外','销售费用','管理费用','研发费用','财务费用']:
    print('\nPAT',pat)
    for i in [m.start() for m in __import__('re').finditer(pat,text)][:10]:
        print('IDX',i)
        print(text[max(0,i-500):i+1800].replace('\n',' ')[:2300])
