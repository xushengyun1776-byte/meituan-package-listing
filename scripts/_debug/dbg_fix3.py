# -*- coding: utf-8 -*-
"""对照实验：分步验证 每一步的贡献。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_el

SEL_SLOT = ("(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')]"
            ".filter(e=>String(e.className).includes('upload'));"
            "if(!l.length) return null; return l[l.length-1];})()")

def snap(cdp, fid, tag):
    r = cdp.evaluate(r'''(()=>{const o=[];
      const ms=document.querySelectorAll('div.roo-modal');
      o.push('modals='+ms.length);
      for(const m of ms){ const st=getComputedStyle(m);
        const d=m.querySelector('.roo-modal-dialog'); const dr=d?d.getBoundingClientRect():null;
        o.push('  cls='+String(m.className).slice(0,46)+' op='+st.opacity+' pe='+st.pointerEvents
          +' parent='+(m.parentElement?m.parentElement.tagName+'.'+String(m.parentElement.className).slice(0,18):'-')
          +' dialog='+(dr?Math.round(dr.width)+'x'+Math.round(dr.height):'-'));
        const b=[...m.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存图片');
        if(b){ const br=b.getBoundingClientRect();
          const hit=document.elementFromPoint(br.x+br.width/2, br.y+br.height/2);
          o.push('  BTN @'+Math.round(br.x)+','+Math.round(br.y)+' pe='+getComputedStyle(b).pointerEvents
            +' hit='+(hit?hit.tagName+'.'+String(hit.className).slice(0,30):'NULL')); }
      }
      const im=document.querySelector('div.cropper-container img');
      o.push('  canvasImg='+(im?Math.round(im.getBoundingClientRect().width)+'x'+Math.round(im.getBoundingClientRect().height)+' nat='+im.naturalWidth:'-'));
      return o.join('\n');})()''', fid)
    print("[%s]\n%s" % (tag, r))

def main():
    cdp = cdp_connect()
    form = None
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            form = x; break
    if form is None: print("NO FORM"); return
    fid = form["id"]

    print("=== A. 当前状态（已 finish + 已 appendChild body）===")
    snap(cdp, fid, "A")

    print("\n=== B. 只设 style 不动 DOM ===")
    print(cdp.evaluate(r'''(()=>{const m=document.querySelector('div.roo-modal'); if(!m) return 'NO MODAL';
      m.style.pointerEvents='auto'; m.style.zIndex='2147483647';
      return 'style set';})()''', fid))
    time.sleep(0.5)
    snap(cdp, fid, "B")

    print("\n=== C. 移回原父级（测试 React 委托是否还活着）===")
    print(cdp.evaluate(r'''(()=>{const m=document.querySelector('div.roo-modal'); if(!m) return 'NO';
      // 找 #root 或原始容器
      let host=null;
      for(const el of document.querySelectorAll('div')){ if(el.id==='root') {host=el;break;} }
      if(!host) host=document.getElementById('root')||document.body.firstElementChild;
      if(!host) return 'NO HOST';
      host.appendChild(m);
      m.style.pointerEvents=''; m.style.zIndex='';
      return 'moved to '+host.tagName+'#'+host.id;})()''', fid))
    time.sleep(0.8)
    snap(cdp, fid, "C")

    print("\n=== D. 唤醒页面（focus emulation + bringToFront）===")
    try: cdp.send("Emulation.setFocusEmulationEnabled", enabled=True)
    except Exception as e: print("emu err", e)
    try: cdp.send("Page.bringToFront")
    except Exception as e: print("btf err", e)
    time.sleep(1.0)
    print("vis:", cdp.evaluate("document.visibilityState", fid))
    snap(cdp, fid, "D")

main()
