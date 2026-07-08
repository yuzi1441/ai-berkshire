import importlib.util, pathlib, json, io, contextlib
root=pathlib.Path.cwd()
spec=importlib.util.spec_from_file_location('ra', root/'tools'/'report_audit.py')
ra=importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
results=json.loads((root/'sources'/'东方电子'/'audit_results_final_article.json').read_text(encoding='utf-8'))
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
    outcome=ra.render_verdict(results, report_name='reports/东方电子/东方电子-earnings-2025年报-2026Q1.md')
text=buf.getvalue()
print(text)
(root/'sources'/'东方电子'/'audit_verdict_final_article.txt').write_text(text+'\nOUTCOME='+json.dumps(outcome,ensure_ascii=False,indent=2),encoding='utf-8')
print('OUTCOME',json.dumps(outcome,ensure_ascii=False))