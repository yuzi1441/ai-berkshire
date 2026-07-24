#!/usr/bin/env python3
"""Build the five-factor layer-2 screen from the formal layer-1 pool."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import akshare as ak
import pandas as pd


AS_OF = "20260724"
DATA_DIR = Path("data/A股风光海上风电核电")
INPUT = DATA_DIR / f"layer1_candidate_pool_{AS_OF}.csv"
CSV_OUTPUT = DATA_DIR / f"layer2_coarse_screen_{AS_OF}.csv"
JSON_OUTPUT = DATA_DIR / f"layer2_coarse_screen_{AS_OF}.json"


MOATS = {
    "阳光电源": (5, "全球逆变器头部份额，光储研发、认证和全球服务网络形成规模与转换成本"),
    "德业股份": (4, "储能/微型逆变器海外渠道与认证积累较强，热交换器和环境电器使主题纯度下降"),
    "中国广核": (5, "核电牌照、选址与运营资质稀缺，在运/在建机组规模和长周期运维记录难复制"),
    "中国核电": (5, "核电牌照、堆址资源和大规模核电运营记录，资产寿命长且准入壁垒极高"),
    "龙源电力": (5, "大型风电运营规模、优质风资源和项目开发能力，融资与运维规模效应突出"),
    "华电新能": (4, "央企新能源运营规模、资源获取和低成本融资能力突出，发电端无定价权"),
    "华润新能源": (4, "大型风光运营规模、央企项目获取和融资能力，运营资产同质化"),
    "亨通光电": (4, "通信与海洋能源系统认证、制造和工程交付能力较强，但海缆并非唯一主业"),
    "华能国际": (4, "大型电源资产、燃料采购和调度规模优势，但风光海风主题纯度低"),
    "三峡能源": (4, "央企融资、资源获取和大基地开发能力突出，发电端缺少定价权"),
    "中天科技": (4, "海缆、电网与通信一体化制造及工程能力，但主题收入被多元业务稀释"),
    "上海电气": (4, "完整发电设备谱系、核电资质与长期客户关系，但业务庞杂且效率偏低"),
    "隆基绿能": (4, "单晶技术、品牌与全球渠道仍在，过剩周期显著削弱成本和定价护城河"),
    "特变电工": (4, "输变电制造、硅料规模和能源资源协同，但多元业务使光伏主题利润波动复杂"),
    "东方电气": (5, "核电与大型发电装备资质、全套设备能力和存量服务记录构成高准入壁垒"),
    "电投产融": (3, "核电股权与央企产融协同具一定资源壁垒，但核电仅为权益且金融业务占比高"),
    "国电电力": (4, "大型电源组合、低成本融资和区域调度地位，但新能源主题纯度低"),
    "中材科技": (4, "玻纤和风电叶片规模、材料研发与客户认证壁垒，业务多元"),
    "金风科技": (5, "CWEA 2025整机和海风新增装机领先，存量机队、服务网络和直驱技术形成壁垒"),
    "通威股份": (4, "高纯晶硅与电池片规模成本领先，但供给过剩令成本壁垒暂时失效"),
    "正泰电器": (4, "低压电器渠道与户用光伏开发网络形成客户触达和规模优势，双主业稀释纯度"),
    "晶盛机电": (5, "长晶设备工艺、客户验证和硅材料全流程装备平台构成高转换成本"),
    "迈为股份": (5, "高效电池整线设备研发、专利与客户验证壁垒高，技术路线切换风险显著"),
    "大全能源": (4, "电子级生产控制、高纯硅规模和成本能力，过剩周期削弱盈利壁垒"),
    "横店东磁": (4, "磁材工艺与欧洲光伏渠道认证并存，双产业群降低单一主题纯度"),
    "阿特斯": (4, "全球组件渠道、大储系统集成与项目开发经验，制造环节同质化较强"),
    "帝尔激光": (4, "光伏精密激光工艺、专利和头部客户验证构成设备转换成本"),
    "捷佳伟创": (5, "覆盖多电池路线的整线设备、工艺研发与客户验证形成高进入壁垒"),
    "聚和材料": (4, "电子浆料配方、量产一致性和电池客户验证形成材料认证壁垒"),
    "协鑫集成": (3, "组件品牌和系统集成经验尚在，但规模、盈利与资产负债表削弱护城河"),
    "林洋能源": (3, "智能电表客户与分布式电站经验，双主业且发电资产可复制"),
    "金刚光伏": (3, "异质结量产布局具技术选择权，但成本、规模和持续经营能力尚未验证"),
    "新天绿能": (4, "河北风资源、区域项目和天然气管网协同，国企融资与运营规模形成壁垒"),
    "苏州固锝": (3, "功率半导体封测与光伏银浆工艺积累，光伏主题收入纯度有限"),
    "川润股份": (3, "风电液压润滑客户认证和工况经验，规模小且锅炉业务分散资源"),
    "国晟科技": (2, "异质结与EPC布局尚未形成可验证成本、规模或客户壁垒"),
    "通灵股份": (3, "光伏接线盒专利、客户认证与量产经验，产品单一且议价权有限"),
    "晶科能源": (4, "全球组件品牌、渠道和N型量产能力较强，组件同质化压制定价权"),
    "福斯特": (4, "胶膜配方、客户验证和规模制造积累深，行业降价侵蚀盈利壁垒"),
    "TCL中环": (4, "大尺寸硅片技术和规模制造积累，过剩周期削弱成本优势"),
    "纽威股份": (4, "工业阀门认证、全球客户与高端工况业绩构成壁垒，核电仅为应用场景之一"),
    "东方电缆": (5, "高压/海缆历史业绩、资质、码头产能和EPCI交付形成强准入与工程壁垒"),
    "中国核建": (5, "核电工程资质、核岛施工经验与安全记录稀缺，国内竞争格局高度集中"),
    "应流股份": (4, "核电和航空高端铸件认证、材料工艺与客户验证周期长"),
    "天合光能": (4, "全球组件品牌、渠道和专利积累，产品同质化削弱定价权"),
    "福能股份": (4, "福建优质风资源、区域项目和电网接入，海风资产利用小时较高"),
    "大金重工": (4, "欧洲海工交付记录、重装码头和DAP运输能力构成稀缺出口壁垒"),
    "锦浪科技": (4, "逆变器认证、海外渠道和长期服务能力，规模弱于全球双龙头"),
    "明阳智能": (4, "海上大兆瓦半直驱与抗台风技术、2025海风装机份额居前，财务兑现弱"),
    "爱旭股份": (4, "ABC电池技术和专利形成差异化，量产成本与客户接受度仍待验证"),
    "晶澳科技": (4, "一体化制造、全球品牌和渠道，组件同质化令利润波动大"),
    "浙富控股": (3, "核电水工设备资质与危废牌照并存，但双主业削弱主题纯度"),
    "节能风电": (3, "央企融资和风资源项目积累，发电端同质化且无定价权"),
    "三一重能": (4, "整机与叶片纵向一体化、规模制造及集团供应链协同"),
    "太阳能": (3, "央企光伏电站规模与融资能力，发电资产同质化且无定价权"),
    "浙江新能": (3, "浙江区域资源和国企融资能力，风光水多元但缺少定价权"),
    "禾望电气": (4, "风电变流器技术、客户认证和运行数据积累，细分份额较强"),
    "东方新能": (2, "新能源资产可复制，规模与成本优势尚不足以证明"),
    "嘉泽新能": (3, "项目开发、融资与运维经验，资源壁垒中等且无定价权"),
    "晶科科技": (3, "光伏电站开发与运营规模、品牌协同，资产回报受电价和融资约束"),
    "金开新能": (3, "风光电站组合和国资融资能力，项目资产同质化"),
    "立新能源": (3, "新疆资源和国企项目获取能力，区域集中且无定价权"),
    "露笑科技": (2, "业务多元且光伏电站非核心，难证明持久主题护城河"),
    "飞沃科技": (3, "风电紧固件客户认证和工艺积累，但客户集中且细分空间有限"),
    "通裕重工": (3, "大型锻件产能和制造经验，产品偏重资产且同质化"),
    "时代新材": (4, "高分子材料研发、央企客户和叶片规模能力，主题被轨交/汽车稀释"),
    "中闽能源": (4, "福建优质海风/陆风资源与区域项目获取能力，集中度风险高"),
    "道生天合": (3, "复材配方和客户认证形成一定黏性，上市历史短且规模待验证"),
    "京运通": (3, "晶体设备工艺与电站资产积累，硅片周期和多元业务削弱壁垒"),
    "拓日新能": (2, "组件与电站规模较小，产品和资产可复制"),
    "景业智能": (4, "核工业机器人资质、远程运维技术与客户验证壁垒较高"),
    "银星能源": (3, "宁夏风资源与央企背景，规模较小且区域集中"),
    "新能股份": (3, "风光储项目运营经验与区域资产，规模较小且船舶电器业务分散"),
    "珠海港": (3, "港口和区域能源项目资源形成一定壁垒，但风电只是多元业务之一"),
    "新筑股份": (2, "新能源与轨交双主业，持续亏损下尚无可验证护城河"),
    "珈伟新能": (2, "照明、组件与电站业务分散，规模和财务稳定性不足"),
}


def num(value):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def metric(frame, label, report_date):
    rows = frame[frame["指标"].astype(str).eq(label)]
    if rows.empty or report_date not in frame.columns:
        return None
    return num(rows.iloc[0][report_date])


def div(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return float(Decimal(str(numerator)) / Decimal(str(denominator)))
    except (InvalidOperation, ZeroDivisionError):
        return None


def status_value(status):
    return 2 if status.startswith("pass") else 1 if status == "near" else 0


def is_operator(subsector):
    return (
        "运营" in subsector
        or "发电" in subsector
        or "综合电力" in subsector
        or "权益" in subsector
    )


def valuation_status(pe, operator):
    if pe is None or pe <= 0:
        return "fail"
    pass_ceiling, near_ceiling = (25, 35) if operator else (30, 40)
    if pe <= pass_ceiling:
        return "pass"
    if pe <= near_ceiling:
        return "near"
    return "fail"


def roe_status(roe_2025, roe_2024, roe_2023, operator):
    if roe_2025 is None:
        return "fail"
    if roe_2025 >= 15:
        return "pass"
    if operator:
        if roe_2025 >= 8:
            return "pass_relaxed_heavy_asset"
        if roe_2025 >= 5:
            return "near"
        return "fail"
    prior = max(value for value in (roe_2023, roe_2024) if value is not None) if any(
        value is not None for value in (roe_2023, roe_2024)
    ) else None
    if roe_2025 >= 10 and prior is not None and roe_2025 >= prior + 2:
        return "pass_relaxed_improving"
    if roe_2025 >= 10:
        return "near"
    if prior is not None and roe_2025 >= 8 and roe_2025 >= prior + 2:
        return "near"
    return "fail"


def cash_status(net_profit, ocf, ratio):
    if net_profit is None or net_profit <= 0 or ocf is None or ocf <= 0 or ratio is None:
        return "fail"
    if ratio >= 0.7:
        return "pass"
    if ratio >= 0.5:
        return "near"
    return "fail"


def debt_status(debt, operator):
    if debt is None:
        return "fail"
    ceiling = 70 if operator else 60
    if debt <= ceiling:
        return "pass_relaxed_utility" if operator and debt > 60 else "pass"
    if debt <= ceiling + 3:
        return "near"
    return "fail"


def cninfo_annual(code):
    errors = []
    for keyword in ("2025年年度报告", ""):
        try:
            frame = ak.stock_zh_a_disclosure_report_cninfo(
                symbol=code,
                keyword=keyword,
                category="年报",
                start_date="20260101",
                end_date="20260724",
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            continue
        for _, item in frame.iterrows():
            title = re.sub(r"</?em>", "", str(item.get("公告标题", "")))
            if any(marker in title for marker in ("摘要", "取消", "英文", "简版", "关于")):
                continue
            detail_url = str(item.get("公告链接", ""))
            published = str(item.get("公告时间", ""))[:10]
            query = parse_qs(urlparse(detail_url).query)
            announcement_id = (query.get("announcementId") or [None])[0]
            pdf_url = (
                f"https://static.cninfo.com.cn/finalpage/{published}/{announcement_id}.PDF"
                if announcement_id and published
                else None
            )
            return title, published, detail_url, pdf_url, None
    return None, None, None, None, "; ".join(errors) or "not found"


def fetch_financials(code):
    frame = ak.stock_financial_abstract(code)
    values = {}
    for report_date, suffix in (
        ("20231231", "2023"),
        ("20241231", "2024"),
        ("20251231", "2025"),
        ("20250331", "2025Q1"),
        ("20260331", "2026Q1"),
    ):
        values[f"revenue_{suffix}_yi"] = div(metric(frame, "营业总收入", report_date), 1e8)
        values[f"net_profit_{suffix}_yi"] = div(metric(frame, "归母净利润", report_date), 1e8)
        values[f"operating_cash_flow_{suffix}_yi"] = div(
            metric(frame, "经营现金流量净额", report_date), 1e8
        )
        values[f"roe_{suffix}_pct"] = metric(frame, "净资产收益率(ROE)", report_date)
        values[f"debt_asset_{suffix}_pct"] = metric(frame, "资产负债率", report_date)
    return values


def reason(row):
    failures = []
    if row["valuation_status"] == "fail":
        failures.append("亏损/动态PE无意义" if (row["pe_dynamic_tencent"] or 0) <= 0 else "动态PE偏高")
    if row["roe_status"] == "fail":
        failures.append("ROE不足且无明确改善")
    if row["cash_status"] == "fail":
        failures.append("经营现金流/净利不达70%或仍亏损")
    if row["debt_status"] == "fail":
        failures.append("负债率越线")
    if row["moat_status"] == "fail":
        failures.append("护城河不足3星")
    if row["purity"] == "低":
        failures.append("主题收入纯度低")
    if not failures and not row["rule_eligible"]:
        near_labels = []
        if row["valuation_status"] == "near":
            near_labels.append("PE")
        if row["roe_status"] == "near":
            near_labels.append("ROE")
        if row["cash_status"] == "near":
            near_labels.append("现金流/净利")
        if row["debt_status"] == "near":
            near_labels.append("负债率")
        failures.append(
            f"仅{row['pass_count']}项达标、{row['near_count']}项接近"
            + (f"（{'、'.join(near_labels)}）" if near_labels else "")
            + "，不满足5项全过或4过1近"
        )
    if not failures:
        failures.append("合格但在护城河/纯度/估值二次收紧中落后")
    return "；".join(failures)


def main():
    input_hash_start = file_sha256(INPUT)
    pool = pd.read_csv(INPUT, dtype={"code": str})
    input_rows_start = len(pool)
    print(f"input_start rows={input_rows_start} sha256={input_hash_start}")
    rows = []
    for _, source in pool.iterrows():
        code = str(source["code"]).zfill(6)
        name = str(source["name"])
        financials = fetch_financials(code)
        operator = is_operator(str(source["subsector"]))
        pe = num(source.get("pe_dynamic"))
        net_profit = financials.get("net_profit_2025_yi")
        ocf = financials.get("operating_cash_flow_2025_yi")
        ocf_ratio = div(ocf, net_profit)
        moat_stars, moat_rationale = MOATS[name]
        annual_title, annual_date, annual_detail, annual_pdf, annual_error = cninfo_annual(code)
        row = {
            "code": code,
            "name": name,
            "subsector": source["subsector"],
            "purity": source["purity"],
            "business_one_liner": source["business_one_liner"],
            "price": num(source.get("price")),
            "quote_time": source.get("quote_time"),
            "market_cap_yi": num(source.get("market_cap_tencent_yi")),
            "pe_dynamic_tencent": pe,
            "pb_tencent": num(source.get("pb")),
            **financials,
            "ocf_to_net_profit_2025": ocf_ratio,
            "moat_stars": moat_stars,
            "moat_rationale": moat_rationale,
            "valuation_status": valuation_status(pe, operator),
            "roe_status": roe_status(
                financials.get("roe_2025_pct"),
                financials.get("roe_2024_pct"),
                financials.get("roe_2023_pct"),
                operator,
            ),
            "cash_status": cash_status(net_profit, ocf, ocf_ratio),
            "debt_status": debt_status(financials.get("debt_asset_2025_pct"), operator),
            "moat_status": "pass" if moat_stars >= 3 else "fail",
            "cninfo_annual_title": annual_title,
            "cninfo_annual_date": annual_date,
            "cninfo_annual_detail_url": annual_detail,
            "cninfo_annual_pdf_url": annual_pdf,
            "cninfo_annual_error": annual_error,
            "eastmoney_financial_url": (
                "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/"
                f"ZYZBAjaxNew?type=0&code={'SH' if code.startswith(('5','6','9')) else 'SZ'}{code}"
            ),
            "tencent_quote_url": source.get("source_quote_tencent_url"),
            "market_cap_crosscheck": source.get("market_cap_crosscheck"),
            "source_note": "财务=东方财富F10(AkShare)并附巨潮2025年报；动态PE/PB=腾讯2026-07-24；市值已由腾讯/东方财富双源核对",
        }
        statuses = [
            row["valuation_status"],
            row["roe_status"],
            row["cash_status"],
            row["debt_status"],
            row["moat_status"],
        ]
        row["pass_count"] = sum(status.startswith("pass") for status in statuses)
        row["near_count"] = statuses.count("near")
        row["rule_eligible"] = row["pass_count"] == 5 or (
            row["pass_count"] == 4 and row["near_count"] == 1
        )
        row["coarse_score"] = (
            sum(status_value(status) for status in statuses)
            + moat_stars / 2
            + (1 if row["purity"] == "高" else 0)
        )
        rows.append(row)

    input_hash_end = file_sha256(INPUT)
    input_rows_end = len(pd.read_csv(INPUT, dtype={"code": str}))
    print(f"input_end rows={input_rows_end} sha256={input_hash_end}")
    if input_hash_end != input_hash_start or input_rows_end != input_rows_start:
        raise RuntimeError("Layer 1 changed during generation; refusing to write mixed Layer 2 output")
    for row in rows:
        row["input_layer1_rows"] = input_rows_start
        row["input_layer1_sha256"] = input_hash_start

    eligible = [
        row for row in rows
        if row["rule_eligible"] and row["moat_stars"] >= 4 and row["purity"] != "低"
    ]
    eligible.sort(
        key=lambda row: (
            row["coarse_score"],
            row["moat_stars"],
            row["ocf_to_net_profit_2025"] or -999,
            -(row["pe_dynamic_tencent"] or 999),
        ),
        reverse=True,
    )
    retained = {row["code"] for row in eligible[:10]}
    for row in rows:
        row["decision"] = "保留" if row["code"] in retained else "淘汰/观察"
        row["decision_reason"] = (
            "五项达标，进入第三层精细分析"
            if row["decision"] == "保留" and row["pass_count"] == 5
            else "四项达标、一项接近，带条件进入第三层"
            if row["decision"] == "保留"
            else reason(row)
        )

    JSON_OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with CSV_OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(JSON_OUTPUT.resolve())
    print(CSV_OUTPUT.resolve())
    print(f"pool={len(rows)} rule_eligible={sum(row['rule_eligible'] for row in rows)} retained={len(retained)}")
    for row in rows:
        if row["decision"] == "保留":
            print(
                row["code"], row["name"], row["pass_count"], row["near_count"],
                row["coarse_score"], row["decision_reason"]
            )


if __name__ == "__main__":
    main()
