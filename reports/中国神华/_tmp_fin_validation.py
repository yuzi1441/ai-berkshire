import importlib.util, pathlib
spec=importlib.util.spec_from_file_location('fr', pathlib.Path('tools/financial_rigor.py'))
fr=importlib.util.module_from_spec(spec); spec.loader.exec_module(fr)
for field, vals in [
 ('revenue_2025', {'annual_report':294916,'akshare_sina':294916}),
 ('net_profit_2025', {'annual_report':52849,'akshare_sina':52849}),
 ('ocf_2025', {'annual_report':75059,'akshare_sina':75059}),
 ('q1_revenue_2026', {'cninfo_pdf':70397,'sina_summary':70397}),
 ('q1_net_profit_2026', {'cninfo_pdf':10667,'sina_summary':10667}),
]:
 print('\n##', field)
 fr.cross_validate(field, vals, '百万元')
