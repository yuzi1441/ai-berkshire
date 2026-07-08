import pdfplumber, pathlib, re, json
base=pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports'
for fn in ['mindray_2026_q1.pdf','mindray_2025_annual.pdf']:
    p=base/fn
    with pdfplumber.open(p) as pdf:
        text='\n'.join((page.extract_text(x_tolerance=1, y_tolerance=3) or '') for page in pdf.pages)
    (base/(fn+'.txt')).write_text(text, encoding='utf-8')
    print(fn, len(text), base/(fn+'.txt'))
    for kw in ['营业收入（元）','销售费用','营业成本','研发费用','生命信息与支持类产品','体外诊断类产品','医学影像类产品','其他类产品','主营业务分行业','分产品','分地区','收入构成','国内市场','国际市场','医疗新基建','采购','反腐','海外','本地化','集采']:
        print('---',kw)
        for m in list(re.finditer(re.escape(kw), text))[:5]:
            s=max(0,m.start()-500); e=min(len(text),m.end()+1200)
            print(text[s:e].replace('\n',' ')[:1800])
