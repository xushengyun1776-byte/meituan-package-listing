# -*- coding: utf-8 -*-
"""验证：finish 所有 CSS 动画 + 强制焦点，弹窗是否恢复正常。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

def main():
    cdp = cdp_connect()
    form = None
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            form = x; break
    if form is None: print("NO FORM"); return
    fid = form["id"]
    try:
        cdp.send("Emulation.setFocusEmulationEnabled", enabled=True)
        print("focus emulation ON")
    except Exception as e:
        print("focus emu err:", e)
    try:
        cdp.send("Page.bringToFront")
        print("bringToFront OK")
    except Exception as e:
        print("bringToFront err:", e)
    time.sleep(0.5)
    print("vis:", cdp.evaluate("document.visibilityState", fid))
    # finish 所有动画
    r = cdp.evaluate(r'''(()=>{ if(!document.getAnimations) return 'NA';
      let n=0; for(const a of document.getAnimations()){ try{ a.finish(); n++; }catch(e){} }
      return 'finished='+n;})()''', fid)
    print("anims:", r)
    time.sleep(0.6)
    print("--- after fix ---")
    print(cdp.evaluate(r'''(()=>{const o=[];
      const m=document.querySelector('div.roo-modal'); if(!m) return 'NO MODAL';
      const st=getComputedStyle(m); const d=m.querySelector('.roo-modal-dialog');
      const ds=d?getComputedStyle(d):null;
      o.push('modal op='+st.opacity+' pe='+st.pointerEvents+' cls='+String(m.className));
      if(d){ const dr=d.getBoundingClientRect();
        o.push('dialog rect='+Math.round(dr.width)+'x'+Math.round(dr.height)+' @'+Math.round(dr.x)+','+Math.round(dr.y)
          +' transform='+ds.transform+' pe='+ds.pointerEvents+' op='+ds.opacity); }
      const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存图片');
      if(b){ const br=b.getBoundingClientRect(); const bs=getComputedStyle(b);
        o.push('BTN 保存图片 rect='+Math.round(br.width)+'x'+Math.round(br.height)+' @'+Math.round(br.x)+','+Math.round(br.y)+' pe='+bs.pointerEvents+' disabled='+b.disabled);
        const hit=document.elementFromPoint(br.x+br.width/2, br.y+br.height/2);
        o.push('elementFromPoint -> '+(hit?hit.tagName+'.'+String(hit.className).slice(0,40):'NULL'));
      } else o.push('NO SAVE BTN');
      return o.join('\n');})()''', fid))

main()
