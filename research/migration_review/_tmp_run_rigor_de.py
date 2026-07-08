import importlib.util, pathlib, io, contextlib, json
root=pathlib.Path.cwd()
spec=importlib.util.spec_from_file_location('fr', root/'tools'/'financial_rigor.py')
fr=importlib.util.module_from_spec(spec); spec.loader.exec_module(fr)
out=[]
def cap(title, fn):
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    s=buf.getvalue(); out.append('### '+title+'\n'+s); print('### '+title); print(s)
cap('2026Q1营业收入交叉验证', lambda: fr.cross_validate('2026Q1营业收入', {'巨潮一季报':1518934346.19,'AKShare财务摘要':1518934000}, '元', 0.01))
cap('2025营业收入交叉验证', lambda: fr.cross_validate('2025营业收入', {'巨潮年报':8377482887.40,'AKShare财务摘要':8377483000}, '元', 0.01))
cap('2026Q1归母净利润交叉验证', lambda: fr.cross_validate('2026Q1归母净利润', {'巨潮一季报':235825663.52,'AKShare财务摘要':235825700}, '元', 0.01))
cap('2025归母净利润交叉验证', lambda: fr.cross_validate('2025归母净利润', {'巨潮年报':911992429.90,'AKShare财务摘要':911992400}, '元', 0.01))
cap('市值验算', lambda: fr.verify_market_cap(12.37, 1340727007, 16585000000, 'CNY'))
cap('估值指标验算', lambda: fr.verify_valuation(12.37, 0.6802, 4.410641, 0.6028, 0.05, None))
cap('三情景估值', lambda: fr.three_scenario_valuation(12.37,0.6802,13.40727007,0.15,0.08,0.00,22,18,12,3,'CNY'))
(pathlib.Path('sources')/'东方电子'/'financial_rigor_outputs.txt').write_text('\n'.join(out),encoding='utf-8')