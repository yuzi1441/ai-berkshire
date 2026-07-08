from pathlib import Path
import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')
for page_no in [11,12,13,14,15,16,17,73,74,75,76,77,78,79,80,81,82,83,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180]:
    with pdfplumber.open('sources/sifang/hkex_prospectus_2026.pdf') as pdf:
        if page_no>len(pdf.pages): continue
        text=pdf.pages[page_no-1].extract_text() or ''
        if any(k in text for k in ['收入', '毛利', '市場份額','排名','客戶','供應商','研發','董事','高級管理層','核心技術','保護及自動化','變電站自動化','智能運維','業務模式','我們的解決方案','競爭優勢']):
            print('\n===== HKEX page',page_no,'=====')
            print(text[:4500])
            tables=pdf.pages[page_no-1].extract_tables() or []
            for ti,t in enumerate(tables[:5]):
                print('--- table',ti,'rows',len(t),'---')
                for row in t[:25]: print(' | '.join('' if c is None else str(c).replace('\n',' ') for c in row))
