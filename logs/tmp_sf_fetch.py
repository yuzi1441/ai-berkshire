"""临时取数脚本：顺丰控股 002352 中报数据（东方财富 + 巨潮公告）。用完即删。"""

import json
import os
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
EM = "https://datacenter.eastmoney.com/securities/api/data/get"
CN = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
OUT_DIR = os.path.join("data", "002352")


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def em_dump(name, rtype, ptype, ps=6):
    params = {
        "type": ptype,
        "sty": "ALL",
        "filter": f'(SECUCODE="002352.SZ")(REPORT_TYPE="{rtype}")',
        "p": "1",
        "ps": str(ps),
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
    }
    url = f"{EM}?{urllib.parse.urlencode(params, safe='()')}"
    try:
        data = get_json(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[EM {ptype}/{rtype}] 失败: {exc}")
        return
    rows = (data.get("result") or {}).get("data") or []
    if not rows:
        print(f"[EM {ptype}/{rtype}] 0 行")
        return
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    print(f"[EM {ptype}/{rtype}] {len(rows)} 行 -> {path}")


def cninfo_search():
    payload = urllib.parse.urlencode(
        {
            "pageNum": "1",
            "pageSize": "50",
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": "002352,9900010448",
            "searchkey": "",
            "secid": "9900010448",
            "category": "category_bndbg_szsh",
            "trade": "",
            "seDate": "2026-08-25~2026-09-01",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
    ).encode()
    req = urllib.request.Request(
        CN,
        data=payload,
        headers={
            "User-Agent": UA["User-Agent"],
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "http://www.cninfo.com.cn/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for a in (data.get("announcements") or [])[:20]:
        print(
            a.get("announcementTitle"),
            "|",
            a.get("adjunctUrl"),
            "|",
            a.get("announcementTime"),
        )
    if not data.get("announcements"):
        print("[CN] 无公告")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for rtype in ("中报",):
        em_dump(f"eastmoney-cashflow-interim-20260831.json", rtype, "RPT_F10_FINANCE_CASHFLOW")
        em_dump(f"eastmoney-balance-interim-20260831.json", rtype, "RPT_F10_FINANCE_BALANCE")
        em_dump(f"eastmoney-income-interim-20260831.json", rtype, "RPT_F10_FINANCE_INCOME")
        em_dump(f"eastmoney-bcashflow-interim-20260831.json", rtype, "RPT_F10_FINANCE_BCASHFLOW")
        em_dump(f"eastmoney-bbalance-interim-20260831.json", rtype, "RPT_F10_FINANCE_BBALANCE")
    print("--- 巨潮公告 ---")
    cninfo_search()


if __name__ == "__main__":
    main()
