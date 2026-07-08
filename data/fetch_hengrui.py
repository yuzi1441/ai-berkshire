import json
import subprocess
import urllib.parse
from pathlib import Path

base = "https://datacenter.eastmoney.com/securities/api/data/get"
params = {
    "type": "RPT_F10_FINANCE_MAINFINADATA",
    "sty": "ALL",
    "filter": '(SECUCODE="600276.SH")',
    "p": "1",
    "ps": "12",
    "sr": "-1",
    "st": "REPORT_DATE",
    "source": "HSF10",
    "client": "PC",
}
url = base + "?" + urllib.parse.urlencode(params, safe='(),="')
txt = subprocess.check_output([
    "curl.exe", "-s", "--noproxy", "*", "-H", "User-Agent: Mozilla/5.0", url
], timeout=30).decode("utf-8")
data = json.loads(txt)
Path("data/hengrui_mainfina_all.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
raw = subprocess.check_output([
    "curl.exe", "-s", "--noproxy", "*", "-H", "User-Agent: Mozilla/5.0", "https://qt.gtimg.cn/q=sh600276"
], timeout=30).decode("gbk", "replace")
Path("data/hengrui_quote_raw.txt").write_text(raw, encoding="utf-8")
print(raw[:240])
print("rows", len(data.get("result", {}).get("data", [])))
for r in data["result"]["data"][:10]:
    print(r["REPORT_DATE_NAME"], r["REPORT_DATE"][:10], r.get("TOTALOPERATEREVE"), r.get("PARENTNETPROFIT"), r.get("NETCASH_OPERATE_PK"), r.get("ROEJQ"), r.get("XSMLL"), r.get("ZCFZL"), r.get("TOTAL_SHARE"), r.get("RDEXPEND"))
