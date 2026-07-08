import importlib.util, pathlib
spec=importlib.util.spec_from_file_location('fr','tools/financial_rigor.py')
fr=importlib.util.module_from_spec(spec); spec.loader.exec_module(fr)
checks=[
('2025营业收入', {'年报PDF':138.0025166395,'东方财富':138.0025}, '亿元'),
('2025归母净利润', {'年报PDF':18.6930080565,'东方财富':18.69301}, '亿元'),
('2026Q1营业收入', {'一季报PDF':29.0756553173,'东方财富':29.07566}, '亿元'),
('2026Q1归母净利润', {'一季报PDF':3.9886925824,'东方财富':3.98869}, '亿元'),
('总股本', {'东方财富股本结构':824157988,'腾讯行情':824157988}, '股'),
]
for field, vals, unit in checks:
    fr.cross_validate(field, vals, unit, tolerance_pct=1.0)
    print('\n')
