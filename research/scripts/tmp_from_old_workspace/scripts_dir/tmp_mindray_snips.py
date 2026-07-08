from pathlib import Path
for fn in ['sources/mindray/mindray-2025-annual.txt','sources/mindray/mindray-2026-q1.txt']:
    text=Path(fn).read_text(encoding='utf-8')
    print('\n###',fn,len(text))
    pats=['生命信息与支持','体外诊断','医学影像','主营业务分行业','主营业务分产品','境内','境外','研发投入','专利','员工','医疗新基建','设备更新','集采','反腐','分季度主要财务指标','每10股','现金股利','国际业务实现收入','国内业务实现收入','报告期内，公司实现营业收入']
    for pat in pats:
        starts=[]; idx=0
        while True:
            idx=text.find(pat, idx)
            if idx==-1: break
            starts.append(idx); idx += len(pat)
            if len(starts)>=3: break
        if starts:
            print('\n--',pat,starts[:3])
            for s in starts[:2]:
                print(text[max(0,s-350):s+1200].replace('\n',' ')[:1800])
