# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

def main():
    cdp = cdp_connect()
    form = None
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            form = x; break
    if form is None:
        print("NO FORM"); return
    fid = form["id"]
    print("--- visibility/focus ---")
    print(cdp.evaluate(r'''(()=>JSON.stringify({
      vis:document.visibilityState, hidden:document.hidden, focus:document.hasFocus(),
      anims:(document.getAnimations?document.getAnimations().length:-1),
      motion:(matchMedia('(prefers-reduced-motion: reduce)').matches),
    }))()''', fid))

    print("\n--- roo-modal 数量 & 每个的状态 ---")
    print(cdp.evaluate(r'''(()=>{const o=[];
      const ms=document.querySelectorAll('div.roo-modal');
      o.push('count='+ms.length);
      let i=0;
      for(const m of ms){ const st=getComputedStyle(m);
        o.push('#'+(i++)+' cls='+String(m.className)
          +' op='+st.opacity+' disp='+st.display+' pe='+st.pointerEvents
          +' animName='+st.animationName+' animDur='+st.animationDuration
          +' animPlay='+st.animationPlayState+' animDelay='+st.animationDelay
          +' transform='+st.transform+' w='+st.width+' h='+st.height);
        const d=m.querySelector('.roo-modal-dialog'); if(d){ const ds=getComputedStyle(d);
          o.push('   dialog cls='+String(d.className)+' offW='+d.offsetWidth+' offH='+d.offsetHeight
            +' op='+ds.opacity+' transform='+ds.transform+' w='+ds.width+' h='+ds.height
            +' animName='+ds.animationName+' pe='+ds.pointerEvents+' pos='+ds.position);
          const c=m.querySelector('.cropper-body'); if(c){ const cs=getComputedStyle(c);
            o.push('   cropper-body offW='+c.offsetWidth+' offH='+c.offsetHeight+' w='+cs.width+' h='+cs.height+' op='+cs.opacity+' transform='+cs.transform); }
        }
      }
      return o.join('\n');})()''', fid))

    print("\n--- getAnimations 明细 ---")
    print(cdp.evaluate(r'''(()=>{if(!document.getAnimations) return 'NA';
      return document.getAnimations().map(a=>{
        try{ return (a.animationName||a.constructor.name)+' state='+a.playState+' time='+Math.round(a.currentTime||0)+' dur='+(a.effect&&a.effect.getTiming().duration); }catch(e){ return 'ERR'; }
      }).join('\n')||'NONE';})()''', fid))

    print("\n--- .roo-modal 相关 CSS 规则（sheet 扫描） ---")
    print(cdp.evaluate(r'''(()=>{const out=[];
      for(const sh of document.styleSheets){ let rules; try{rules=sh.cssRules}catch(e){continue}
        for(const r of rules||[]){ const t=r.cssText||'';
          if(/roo-modal|roo-mask|cropper-modal/.test(t)) out.push(t.slice(0,300)); } }
      return out.slice(0,25).join('\n---\n')||'NONE';})()''', fid))

main()
