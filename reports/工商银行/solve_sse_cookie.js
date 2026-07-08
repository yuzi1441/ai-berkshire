
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
