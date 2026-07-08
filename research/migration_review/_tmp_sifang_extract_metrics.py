from pathlib import Path
import pdfplumber, re, sys, json, csv
sys.stdout.reconfigure(encoding='utf-8')
# Extract selected structured tables
result={}
# Annual tables pages 8,9 etc
with pdfplumber.open('sources/sifang/2025_annual_sse_real.pdf') as pdf:
    for page_no in [8,9,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200]:
        if page_no>len(pdf.pages): continue
        text=pdf.pages[page_no-1].extract_text() or ''
        if any(k in text for k in ['普通股股份变动情况表','数量变动情况','股份总数','营业收入和营业成本','主营业务分行业','主营业务分产品','前五名客户','前五名供应商','研发投入','合并资产负债表','合并利润表','合并现金流量表','货币资金','应收账款','合同资产','存货','短期借款','营业总收入','营业成本','销售费用','管理费用','研发费用','经营活动产生的现金流量净额']):
            print('\n===== Annual page',page_no,'=====')
            print(text[:2200])
            tables=pdf.pages[page_no-1].extract_tables() or []
            for ti,t in enumerate(tables[:5]):
                print('--- table',ti,'rows',len(t),'---')
                for row in t[:20]: print(' | '.join('' if c is None else str(c).replace('\n',' ') for c in row))
# Q1 key pages
with pdfplumber.open('sources/sifang/2026_q1_sse_real.pdf') as pdf:
    for page_no in range(1,13):
        text=pdf.pages[page_no-1].extract_text() or ''
        print('\n===== Q1 page',page_no,'=====')
        print(text[:2200])
        tables=pdf.pages[page_no-1].extract_tables() or []
        for ti,t in enumerate(tables[:3]):
            print('--- table',ti,'rows',len(t),'---')
            for row in t[:25]: print(' | '.join('' if c is None else str(c).replace('\n',' ') for c in row))
