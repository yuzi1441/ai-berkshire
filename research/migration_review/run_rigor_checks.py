from tools.financial_rigor import cross_validate, verify_market_cap, verify_valuation
from contextlib import redirect_stdout
from pathlib import Path
out=Path('reports/中国神华/sources/financial_rigor_checks.txt')
with out.open('w',encoding='utf-8') as f, redirect_stdout(f):
    cross_validate('2026Q1营业收入', {'2026Q1原文PDF':70397,'新浪公告镜像':70397}, '百万元', 1.0)
    cross_validate('2026Q1归母净利润', {'2026Q1原文PDF':10667,'新浪公告镜像':10667}, '百万元', 1.0)
    cross_validate('2025营业收入', {'2025年报原文PDF':294916,'既有研究报告':294900}, '百万元', 1.0)
    cross_validate('2025归母净利润', {'2025年报原文PDF':52771,'既有研究报告':52849}, '百万元', 1.0)
    verify_market_cap(41.91, 21689000000, 908980000000, 'CNY')
    verify_valuation(41.91, eps=2.655, bvps=22.17, dividend=2.26)
print(out)
