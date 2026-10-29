# -*- coding: utf-8 -*-
"""从 React fiber 读出「组类型」下拉的选项列表。"""
import sys, time, json
sys.path.insert(0, '.')
from form import cdp_connect
from addgroup import form_ctx, grp_type_expr

cdp = cdp_connect()
form = form_ctx(cdp)
fid = form['id']
expr = grp_type_expr(3)

FIBER = r'''(()=>{const e=%s; if(!e) return 'NO-EL';
const k=Object.keys(e).find(x=>x.startsWith('__reactFiber')||x.startsWith('__reactInternalInstance'));
if(!k) return 'NO-FIBER';
let f=e[k],d=0,out=[];
while(f&&d<60){
  const p=f.memoizedProps||{};
  for(const key of ['options','dataSource','data','items','optionList']){
    const v=p[key];
    if(Array.isArray(v)&&v.length&&v.length<20){
      out.push('d'+d+'.'+key+'='+JSON.stringify(v).slice(0,300));
    }
  }
  if(p.children&&Array.isArray(p.children)&&p.children.length&&p.children.length<20){
    try{ out.push('d'+d+'.children='+JSON.stringify(p.children).slice(0,300)); }catch(e){}
  }
  f=f.return; d++;
}
return out.join('\n')||'NO-OPTIONS';})()'''

print(cdp.evaluate(FIBER % expr, fid)[:2500])
