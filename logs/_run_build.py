from pathlib import Path
import traceback, importlib, sys
log = Path(r"E:\ai-berkshire\logs\dashboard-rebuild.log")
done = Path(r"E:\ai-berkshire\logs\dashboard-rebuild.done")
if done.exists(): done.unlink()
try:
    sys.path.insert(0, r"E:\ai-berkshire\tools")
    import build_investment_dashboard as d
    importlib.reload(d)
    board = d.build_dashboard(Path(r"E:\ai-berkshire"))
    # sample a few
    rows = []
    for name in ["工业富联", "特变电工", "中国神华", "腾讯", "恒瑞医疗", "格力电器"]:
        item = next((x for x in board["decisions"] if name in x["company"]), None)
        if not item: 
            rows.append(f"{name}: missing"); continue
        md = (item.get("valuation_section") or {}).get("markdown") or ""
        rows.append(f"{item['company']}: has8={('第八步' in md or '最终决策' in md)} len={len(md)} head={(item.get('valuation_section') or {}).get('heading')}")
    log.write_text(f"count={board['decision_count']}\n" + "\n".join(rows) + "\n", encoding="utf-8")
    done.write_text("0", encoding="utf-8")
except Exception:
    log.write_text(traceback.format_exc(), encoding="utf-8")
    done.write_text("1", encoding="utf-8")
