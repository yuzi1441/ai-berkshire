from pathlib import Path
import re,json
base=Path('sources/cninfo_hmzb')
files=['20260227_2025年年度报告.txt','20250411_2024年年度报告.txt','20240411_2023年年度报告.txt','20230412_2022年年度报告.txt','20220601_2021年年度报告（修订稿）.txt','20260427_2026年一季度报告.txt','20250419_2025年员工持股计划（草案）.txt','20260303_关于回购公司股份方案实施完毕暨回购实施结果的公告.txt','20260227_关于2025年度利润分配预案的公告.txt','20251027_关于2025年第三季度利润分配预案的公告.txt','20250808_关于2025年半年度利润分配预案的公告.txt','20250411_关于2025年度日常关联交易预计的公告.txt']
patterns=['肖毅','雷纯立','肖星星','刘毅','张伟','董事、监事、高级管理人员','实际控制人','控股股东','前十名股东','普通股股东','任职情况','薪酬','关联交易','日常关联交易','利润分配','现金红利','现金分红','回购','员工持股','海外','新加坡','印尼','承诺','股份支付','营收','净利润','经营活动产生的现金流量']
for fn in files:
    p=base/fn
    if not p.exists(): continue
    text=p.read_text(encoding='utf-8',errors='ignore')
    print('\n====',fn,'chars',len(text),'====')
    for pat in patterns:
        hits=[m.start() for m in re.finditer(re.escape(pat), text)]
        if hits:
            print('\n--',pat,'hits',len(hits),'--')
            for pos in hits[:3]:
                s=max(0,pos-250); e=min(len(text),pos+600)
                print(text[s:e].replace('\n',' ')[:1000])