from decimal import Decimal, getcontext
import json, pathlib
getcontext().prec=28
checks=[]
def add(name, a_source, a, b_source, b, unit):
    a=Decimal(str(a)); b=Decimal(str(b)); diff=abs(a-b)/a*100 if a!=0 else Decimal(0)
    checks.append({"name":name,"source1":a_source,"value1":str(a),"source2":b_source,"value2":str(b),"unit":unit,"diff_pct":str(diff.quantize(Decimal('0.0001'))),"pass": diff<=Decimal('1')})
add('2025营业收入','公司2025年报PDF',294916,'东方财富API',294916,'百万元')
add('2025归母净利润','公司2025年报PDF',52849,'东方财富API',52849,'百万元')
add('2026Q1营业收入','公司2026一季报PDF',70397,'东方财富API',70397,'百万元')
add('2026Q1归母净利润','公司2026一季报PDF',10667,'东方财富API',10667,'百万元')
price=Decimal('41.91'); shares=Decimal('216.89434304')
calc_cap=price*shares
add('总市值','腾讯行情字段45',9090.04,'股价×总股本',calc_cap,'亿元')
path=pathlib.Path('sources/validation_checks.json')
path.write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
for c in checks: print(c)
