import sys, pathlib
sys.path.insert(0, r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\tools')
import financial_rigor as fr
checks=[
 ('cross_revenue.txt','revenue_2025', {'annual_report':332.82159404,'akshare':332.82159404}, '亿元'),
 ('cross_net_profit.txt','net_profit_parent_2025', {'annual_report':81.35775409,'akshare':81.35775409}, '亿元'),
 ('cross_quote.txt','quote_20260706_close', {'tencent':140.60,'sina':140.60}, '元'),
]
for fn, field, vals, unit in checks:
    import io, contextlib
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):
        fr.cross_validate(field, vals, unit, 0.1)
    pathlib.Path(fn).write_text(buf.getvalue(),encoding='utf-8')
    print(buf.getvalue())
