import requests
from pathlib import Path
ann={
'1224941317_chairman_change.pdf':'finalpage/2026-01-21/1224941317.PDF',
'1224933606_gm_resign.pdf':'finalpage/2026-01-15/1224933606.PDF',
'1224969923_director_resign.pdf':'finalpage/2026-02-07/1224969923.PDF',
'1222833289_mgmt_change_20250319.pdf':'finalpage/2025-03-19/1222833289.PDF',
'1225096193_exec_comp_2026.pdf':'finalpage/2026-04-11/1225096193.PDF',
'1225096198_comp_policy.pdf':'finalpage/2026-04-11/1225096198.PDF',
'1221909714_related_2025_est.pdf':'finalpage/2024-12-03/1221909714.PDF',
'1224842049_related_2025_adjust.pdf':'finalpage/2025-12-02/1224842049.PDF',
'1224842050_related_2026_est.pdf':'finalpage/2025-12-02/1224842050.PDF',
'1218534938_acquire_habiao.pdf':'finalpage/2023-12-07/1218534938.PDF',
'1216956766_acquire_assets_related.pdf':'finalpage/2023-06-01/1216956766.PDF',
'1224744820_entrusted_loan.pdf':'finalpage/2025-10-28/1224744820.PDF',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for fn,path in ann.items():
    p=Path(fn)
    if p.exists() and p.stat().st_size>1000:
        print('exists',fn,p.stat().st_size); continue
    r=requests.get('http://static.cninfo.com.cn/'+path,headers=headers,timeout=30)
    print(fn,r.status_code,len(r.content),r.content[:4])
    p.write_bytes(r.content)