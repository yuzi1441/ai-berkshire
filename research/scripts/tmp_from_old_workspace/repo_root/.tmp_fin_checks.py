import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('fr', Path('tools/financial_rigor.py'))
fr=importlib.util.module_from_spec(spec); spec.loader.exec_module(fr)
checks=[
('2025营业收入', {'东方财富':33282159404,'巨潮年报':33282159404}, '元'),
('2025归母净利润', {'东方财富':8135775409,'巨潮年报':8135775409}, '元'),
('2025经营现金流', {'东方财富/年报摘录':10144968535,'巨潮年报':10144968535}, '元'),
('2026Q1营业收入', {'东方财富':8352015912,'巨潮一季报':8352015912}, '元'),
('2026Q1归母净利润', {'东方财富':2329658005,'巨潮一季报':2329658005}, '元'),
('总股本', {'腾讯行情':1212441394,'巨潮一季报':1212441394}, '股'),
]
for field, values, unit in checks:
    fr.cross_validate(field, values, unit, 1)
