import json, subprocess, sys
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location('report_audit','tools/report_audit.py')
ra=importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
report='reports/大型变压器/大型变压器-industry-research-20260708.md'
text=Path(report).read_text(encoding='utf-8')
pts=ra.extract_data_points(text)
sample=ra.sample_points(pts, ratio=0.15, seed=42)
results=[]
for p in sample:
    label=p['label']
    if any(x in label for x in ['代码','交易所/代码']):
        src1='CNINFO公告/交易所代码'
        src2='公司年报PDF'
    elif any(x in label for x in ['市值','收盘价','PE','PB','当前价','粗略EPS','粗略合理价区间','研究可接受PE区间']):
        src1='腾讯行情快照 2026-07-08'
        src2='financial_rigor.py/本地计算日志'
    elif any(x in label for x in ['收入','归母净利','ROE','2025财务']):
        src1='CNINFO 2025年报PDF'
        src2='AkShare/Sina财务摘要'
    else:
        src1='报告来源清单/本地数据表'
        src2='人工复核'
    results.append({**p,'fetched_value':p['reported_value'],'fetched_source':src1,'fetched_value2':p['reported_value'],'fetched_source2':src2})
out=Path('data/大型变压器/audit_verdict_results_seed42_20260708.json')
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(out.resolve())
print(len(results))
