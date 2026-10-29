# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect
cdp = cdp_connect(); cdp.wake(); time.sleep(0.4)
form=None
for x in cdp.contexts():
    if "套餐名称" in x["text"]: form=x; break
fid=form["id"]
print(cdp.evaluate(r'''(()=>{const o=[];
  const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')]
    .filter(t=>!String(t.className).includes('upload'));
  if(!li.length) return 'NO LI';
  const c=li[0].querySelector('img[class*=closeIcon]');
  if(!c) return 'NO CLOSE';
  // 向上找带 onClick 的元素
  let n=c; for(let i=0;i<6&&n;i++){
    const keys=Object.keys(n).filter(k=>k.startsWith('__reactProps')||k.startsWith('__reactFiber'));
    const info=keys.map(k=>{ const p=n[k]||{};
      return k.slice(0,22)+'{keys:'+Object.keys(p).slice(0,10).join(',')+'}'; }).join(' ');
    const fiberKey=keys.find(k=>k.startsWith('__reactFiber'));
    let fs='';
    if(fiberKey){ let f=n[fiberKey], d=0;
      while(f&&d<10){ const p=f.memoizedProps||{};
        const onk=Object.keys(p).filter(x=>/^on[A-Z]/.test(x));
        if(onk.length){ fs+='[d'+d+' '+onk.join('/')+']'; break; }
        f=f.return; d++; } }
    o.push(i+' '+n.tagName+'.'+String(n.className).slice(0,32)+' props='+info+' fiber='+fs);
    n=n.parentElement; }
  return o.join('\n');})()''', fid))
