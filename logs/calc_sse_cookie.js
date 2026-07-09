const fs=require('fs');
let html=fs.readFileSync('logs/sse_guard.html','utf8');
let js=html.match(/<script>([\s\S]*)<\/script>/)[1];
global.window=global;
global.location={host:'www.sse.com.cn'};
let cookie='';
global.document={get cookie(){return cookie;},set cookie(v){cookie=v;},location:{reload(){}}};
try { eval(js.replace('document.location.reload()','')); } catch(e) { console.error('ERR', e); }
console.log(cookie);
