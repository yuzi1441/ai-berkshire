const fs=require('fs');
const html=fs.readFileSync('sifang_2026q1_sse.pdf','utf8');
const arg1=html.match(/var arg1='([^']+)'/)[1];
const posList=eval('['+html.match(/var posList=\[([^\]]+)\]/)[1]+']');
const mask=Buffer.from('MzAwMDE3NjAwMDg1NjAwNjA2MTUwMTUzMzAwMzY5MDAyNzgwMDM3NQ==','base64').toString('utf8');
let out=[]; for(let i=0;i<arg1.length;i++){ for(let j=0;j<posList.length;j++){ if(posList[j]===i+1) out[j]=arg1[i]; }}
const arg2=out.join('');
let arg3=''; for(let i=0;i<arg2.length && i<mask.length;i+=2){ let strChar=parseInt(arg2.slice(i,i+2),16); let maskChar=parseInt(mask.slice(i,i+2),16); let xorChar=(strChar^maskChar).toString(16); if(xorChar.length===1) xorChar='0'+xorChar; arg3+=xorChar; }
console.log({arg1,mask,arg2,arg3});
