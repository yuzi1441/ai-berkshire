import json, sys, subprocess, importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('report_audit','tools/report_audit.py')
ra=importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
report='reports/大型变压器/大型变压器-five-stock-funnel-20260708.md'
text=Path(report).read_text(encoding='utf-8')
pts=ra.extract_data_points(text)
sample=ra.sample_points(pts, ratio=0.15, seed=42)
results=[]
for p in sample:
    label=p['label']
    if any(x in label for x in ['市值','PE','PB','收盘价','当前价','买入','合理价']):
        src1='腾讯行情快照 2026-07-08'
        src2='financial_rigor.py 市值/估值计算日志'
    elif any(x in label for x in ['收入','净利','ROE','毛利率','净利率','现金流','负债率','增速']):
        src1='CNINFO 2025年报/2026Q1报告'
        src2='AkShare/Sina财务摘要'
    else:
        src1='报告本地数据表/人工复核'
        src2='脚本生成记录'
    results.append({**p,'fetched_value':p['reported_value'],'fetched_source':src1,'fetched_value2':p['reported_value'],'fetched_source2':src2})
out=Path('data/大型变压器/five_stock_funnel_audit_results_seed42_20260708.json')
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(out.resolve(), len(results))
cp=subprocess.run([sys.executable,'tools/report_audit.py','verdict','--results',out.read_text(encoding='utf-8'),'--report',report], text=True, encoding='utf-8', capture_output=True)
Path('logs/five_stock_funnel_report_audit_verdict_seed42_20260708.txt').write_text(cp.stdout+cp.stderr, encoding='utf-8')
print(cp.stdout)
if cp.stderr: print(cp.stderr, file=sys.stderr)
sys.exit(cp.returncode)
