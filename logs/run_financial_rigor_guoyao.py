from pathlib import Path
import io, contextlib, sys
sys.path.insert(0,'tools')
import financial_rigor as fr
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
    fr.cross_validate('2025营业收入', {'年报':9363074210.11,'东方财富':9363074210.11}, '元')
    fr.cross_validate('2025归母净利润', {'年报':941601686.09,'东方财富':941601686.09}, '元')
    fr.cross_validate('2025经营现金流净额', {'主要会计数据':1698089053.33,'现金流量表':1698089053.33}, '元')
    fr.verify_market_cap(8.70, 1341172692, 11668000000, 'CNY')
out=buf.getvalue()
print(out)
Path('data/国药现代/financial_rigor_risk_assessor_20260708.txt').write_text(out, encoding='utf-8')
