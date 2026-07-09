import io, contextlib, pathlib, sys
sys.path.insert(0,'tools')
import financial_rigor as fr
pathlib.Path('data/600372').mkdir(parents=True,exist_ok=True)
checks=[('cross_revenue.txt', lambda: fr.cross_validate('revenue_2025', {'annual_report_pdf':24211960384.18,'akshare_eastmoney':24211960384.18}, 'CNY')),
        ('cross_profit.txt', lambda: fr.cross_validate('net_profit_2025', {'annual_report_pdf':1067323487.88,'akshare_eastmoney':1067323487.88}, 'CNY')),
        ('cross_q1_revenue.txt', lambda: fr.cross_validate('q1_revenue_2026', {'q1_report_pdf':4642132666.27,'akshare_eastmoney':4642132666.27}, 'CNY'))]
for fname,fn in checks:
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    text=buf.getvalue()
    print(text)
    pathlib.Path('data/600372',fname).write_text(text,encoding='utf-8')