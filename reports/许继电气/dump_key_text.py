from pathlib import Path
files=['xj_2026q1_pdftext.txt','1224941317_chairman_change.txt','1224933606_gm_resign.txt','1224969923_director_resign.txt','1222833289_mgmt_change_20250319.txt','1225096193_exec_comp_2026.txt','1225096198_comp_policy.txt','1218534938_acquire_habiao.txt','1216956766_acquire_assets_related.txt','1224744820_entrusted_loan.txt','1224842049_related_2025_adjust.txt','1224842050_related_2026_est.txt']
for f in files:
    p=Path(f)
    if not p.exists(): continue
    text=p.read_text(encoding='utf-8',errors='ignore')
    print('\n\n################',f,'################')
    print(text[:5000])