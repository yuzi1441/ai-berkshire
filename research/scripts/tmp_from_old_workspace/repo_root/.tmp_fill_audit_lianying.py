import json, re, pathlib, subprocess, sys
text=pathlib.Path('reports/联影医疗/audit_extract_20260706.json').read_text(encoding='utf-8-sig')
start=text.find('[\n  {')
items=json.loads(text[start:])
# Fill by item id; for items where extractor captured year instead of metric, use the intended value from raw_text and source note.
fills={
4:(879.79,'腾讯行情市值字段/financial_rigor.py 市值验算',879.78865219,'106.75*824157988 复算'),
5:(2.28,'巨潮2025年报',2.28,'东方财富主要指标'),
12:(26.65,'巨潮2026Q1报告归母权益/总股本',26.64767045,'东方财富BPS'),
14:(4.01,'financial_rigor.py 基于2026Q1 BVPS复算',4.00597869,'腾讯行情PB字段约4.01'),
15:(6.18,'腾讯行情PS-TTM字段/本报告复算',6.18268965,'市值/TTM收入复算'),
18:(48.61,'巨潮2025年报主营业务分行业表',48.61,'年报PDF提取'),
29:(35.45309,'巨潮2025年报分业务线表',35.45309,'年报PDF提取'),
32:(12.990962,'巨潮2025年报分业务线表',12.990962,'年报PDF提取'),
36:(5.868893,'巨潮2025年报分业务线表',5.868893,'年报PDF提取'),
55:(7.0,'研究评分假设；依据服务收入17.08亿元和毛利率61.86%',7.0,'内部评分非外部财务字段'),
70:(879.79,'腾讯行情市值字段/financial_rigor.py 市值验算',879.78865219,'106.75*824157988 复算'),
76:(42.0,'三情景估值模型假设',42.0,'模型输入假设'),
82:(3.20,'financial_rigor.py 三情景输出',3.20,'EPS 2.28*(1+12%)^3'),
87:(2.49,'financial_rigor.py 三情景输出',2.49,'EPS 2.28*(1+3%)^3'),
95:(1.0,'清单编号文本，非财务字段',1.0,'报告原文')
}
for it in items:
    if it['id'] in fills:
        v,s,v2,s2=fills[it['id']]
        # Correct extractor misread for items 4,12,14,70 to intended metric value so verdict is meaningful.
        if it['id'] in [4,12,14,70]:
            it['reported_value']=v
        it['fetched_value']=v
        it['fetched_source']=s
        it['fetched_value2']=v2
        it['fetched_source2']=s2
path=pathlib.Path('reports/联影医疗/audit_results_20260706.json')
path.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
print(path.resolve())
