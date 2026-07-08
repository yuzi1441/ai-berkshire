import subprocess, pathlib, sys
root = pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire')
json_text = pathlib.Path('audit_results_embodied_robotics_20260706.json').read_text(encoding='utf-8')
cmd = [sys.executable, str(root/'tools'/'report_audit.py'), 'verdict', '--results', json_text, '--report', '具身智能机器人产业链投资研究报告-20260706.md']
res = subprocess.run(cmd, capture_output=True)
for b, stream in [(res.stdout, sys.stdout), (res.stderr, sys.stderr)]:
    if not b: continue
    for enc in ('utf-8','gbk','cp936'):
        try:
            text = b.decode(enc)
            break
        except Exception:
            text = b.decode('utf-8', errors='replace')
    print(text, file=stream)
sys.exit(res.returncode)
