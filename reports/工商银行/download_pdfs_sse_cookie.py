import requests, pathlib, re, subprocess, json, os, time
base='https://www.sse.com.cn'
files={
'ICBC_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601398_20260430_VX32.pdf',
'ICBC_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-28/601398_20260328_JYCS.pdf',
'CCB_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601939_20260430_QGW6.pdf',
'ABC_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601288_20260430_4VKP.pdf',
'BOC_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601988_20260430_77QJ.pdf',
'BOCOM_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601328_20260430_UBF0.pdf',
'PSBC_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-30/601658_20260430_QCZR.pdf',
'CMB_Q1_2026':'/disclosure/listedinfo/announcement/c/new/2026-04-29/600036_20260429_IO3O.pdf',
'CCB_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-04-28/601939_20260428_JVLD.pdf',
'ABC_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-31/601288_20260331_UYJS.pdf',
'BOC_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-31/601988_20260331_IQO4.pdf',
'BOCOM_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-28/601328_20260328_6CRD.pdf',
'PSBC_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-28/601658_20260328_ZO3F.pdf',
'CMB_AR_2025':'/disclosure/listedinfo/announcement/c/new/2026-03-28/600036_20260328_F53J.pdf',
}
out=pathlib.Path('source_pdfs'); out.mkdir(exist_ok=True)
js = r'''
const fs=require('fs');
let html=fs.readFileSync(process.argv[2],'utf8');
let arg1=(html.match(/var arg1='([^']+)'/)||[])[1];
let posList=(html.match(/var posList=\[([^\]]+)\]/)||[])[1].split(',').map(x=>parseInt(x));
let m=html.match(/var _0x3e9e=\[([^\]]+)\]/);
let arr=[]; let re=/'([^']*)'/g; let mm; while((mm=re.exec(m[1]))){arr.push(Buffer.from(mm[1],'base64').toString('utf8'));}
function rot(a,n){while(--n){a.push(a.shift())}}
rot(arr,0x176);
let mask=arr[0];
let out=[]; for(let i=0;i<arg1.length;i++){ for(let j=0;j<posList.length;j++){ if(posList[j]==i+1) out[j]=arg1[i]; }}
let arg2=out.join(''); let arg3='';
for(let i=0;i<arg2.length && i<mask.length;i+=2){ let strChar=parseInt(arg2.slice(i,i+2),16); let maskChar=parseInt(mask.slice(i,i+2),16); let x=(strChar^maskChar).toString(16); if(x.length==1)x='0'+x; arg3+=x; }
console.log(arg3);
'''
pathlib.Path('solve_sse_cookie.js').write_text(js,encoding='utf-8')
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
s=requests.Session(); s.headers.update(headers)
for name,path in files.items():
    f=out/(name+'.pdf')
    url=base+path
    r=s.get(url,timeout=60)
    ct=r.headers.get('content-type','')
    if (b'%PDF' not in r.content[:20]) and b'arg1' in r.content[:1000]:
        tmp=out/(name+'.html'); tmp.write_bytes(r.content)
        cookie=subprocess.check_output(['node','solve_sse_cookie.js',str(tmp)],text=True).strip()
        s.cookies.set('acw_sc__v2',cookie,domain='sse.com.cn',path='/')
        r=s.get(url,timeout=60)
        ct=r.headers.get('content-type','')
    print(name,r.status_code,len(r.content),ct,r.content[:4])
    f.write_bytes(r.content)
