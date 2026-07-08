from pathlib import Path
text=Path('sources/oriental_electronics/2025annual_1225161855.txt').read_text(encoding='utf-8')
# print neighborhoods of table headers
for pat in ['分行业','分产品','营业收入比上年同期增减','公司主营业务数据统计口径','前五名客户合计销售金额','研发人员数量','研发投入金额','现金分红总额','每10股派发现金红利']:
    print('\n===',pat,'===')
    i=text.find(pat)
    print('idx',i)
    if i!=-1:
        print(text[max(0,i-800):i+2500])
