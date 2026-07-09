import subprocess, sys
from pathlib import Path
j=Path('data/大型变压器/audit_verdict_results_seed42_20260708.json').read_text(encoding='utf-8')
cp=subprocess.run([sys.executable,'tools/report_audit.py','verdict','--results',j,'--report','reports/大型变压器/大型变压器-industry-research-20260708.md'], cwd='.', text=True, encoding='utf-8', capture_output=True)
Path('logs/large_transformer_report_audit_verdict_seed42_20260708.txt').write_text(cp.stdout+cp.stderr, encoding='utf-8')
print(cp.stdout)
if cp.stderr: print(cp.stderr, file=sys.stderr)
sys.exit(cp.returncode)
