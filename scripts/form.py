#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""美团表单操作工具：真实键盘输入 + 权威坐标点击 + 下拉选择。
所有操作都基于 DOM.getBoxModel 的页面绝对坐标，支持嵌套 iframe。
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clicktext import CDP, get_page


def click_point(cdp, cid, expr, fx=0.5, fy=0.5):
    """取元素包围盒内 (fx,fy) 比例位置并点击，返回页面绝对坐标。
    用于规避被 overlay（如 addon-icon）遮住的输入框 —— 点击中心会落到遮罩上。
    返回 (abs_x, abs_y, local_x, local_y)。"""
    res = cdp.local_point(cid, expr, fx=fx, fy=fy)
    if not res:
        return None
    return res[:2]


def wait_for_el(cdp, cid, expr, timeout=20.0, label=""):
    """轮询等待某元素出现（表单是分块异步渲染的，刚打开时部分控件还不存在）。"""
    js = "(()=>{const e=(%s); return e?'YES':'';})()" % expr
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if cdp.evaluate(js, cid) == "YES":
                if label:
                    print("  ready:", label)
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print("  [warn] 等待超时:", label or expr[:60])
    return False


def press_esc(cdp):
    """发一个真实 ESC 键（trusted 事件，能关掉 roo 的下拉浮层）。"""
    for t in ("keyDown", "keyUp"):
        try:
            cdp.send("Input.dispatchKeyEvent", type=t, key="Escape", code="Escape",
                     windowsVirtualKeyCode=27, nativeVirtualKeyCode=27)
        except Exception:
            pass
    time.sleep(0.3)


def purge_modals(cdp, cid=None, timeout=2.0):
    """**清理所有遮挡页面的残留浮层**（弹窗遮罩 + 下拉浮层）。

    ★ 为什么要做这件事（这是本项目最隐蔽的坑）：
      美团用 roo 组件的离场动画（`roo-mask-motion-leave` / `roo-popup-motion-leave`）
      关闭弹窗和下拉。动画结束后**节点不会被移除**：
        - 弹窗遮罩：opacity 变 0（看不见）但 display:block + pointer-events:auto
        - 下拉浮层：连 opacity 都还是 1，肉眼可见地**盖在表单上**
      两者都会把后面所有**坐标点击**全部吞掉，
      而 **JS 合成事件完全不受影响**（合成事件不走 hit-test）。
      于是表现极具迷惑性：DOM 读取一切正常、坐标算得也对、合成事件也有效，
      唯独真实点击毫无反应 —— 极难定位。

      实测「菜单分组」下拉选完后，它的浮层（主食/炒菜/饮料/小吃）会一直挂着，
      正好盖住下方「+ 添加商品」按钮，导致商品选择弹窗打不开。

    遍历**所有 context**（顶层 / 业务 iframe / 弹窗 iframe），
    因为浮层可能落在任意一层 iframe 里。

    返回被清理的描述串。
    """
    targets = []
    try:
        targets = [c["id"] for c in cdp.contexts()]
    except Exception:
        targets = [cid] if cid is not None else []
    if cid is not None and cid not in targets:
        targets.append(cid)

    JS = r"""(()=>{const o=[];
      // ★ 白名单：商品选择弹窗本体（左侧有「店内商品」分组树）绝不能动！
      //   它的 roo-modal 容器 opacity 也可能接近 0（内容是另一层），
      //   一旦被当成残留移除，弹窗就凭空消失 —— 后续所有针对弹窗的操作全落空。
      // ★ 同理豁免「上传图片」裁剪弹窗：它的入场动画（roo-mask-motion-appear）
      //   在后台标签页里被冻结在第 0 帧 → 遮罩 opacity=0，
      //   于是会被下面的「透明 roo-modal 残留」规则**误删**。
      //   （根治办法是 cdp.wake() + finish_animations()，但这里再加一层保险。）
      const KEEP=/店内商品|上传图片|套餐拼图推荐/;
      // 1) 离场动画残留的浮层（弹窗遮罩 / 下拉浮层）—— 一律移除
      //    ★ 这里**不能**再用 KEEP 豁免：离场残留的 class 就是 motion-leave，
      //      而裁剪弹窗的离场残留 innerText 含「上传图片」，
      //      一旦豁免就会留下一张 opacity=0 的全屏遮罩，
      //      它会吃掉所有 hover / 坐标点击（实测 :hover 链停在 DIV.roo-modal）。
      for(const e of document.querySelectorAll('[class*=motion-leave]')){
        try{ e.remove(); o.push('leave:'+String(e.className).slice(0,26)); }catch(e){}
      }
      // 2) 透明的 roo-modal 残留（仍在「入场」但动画被冻结的）
      for(const e of document.querySelectorAll('div.roo-modal')){
        const st=getComputedStyle(e);
        if(KEEP.test(e.innerText||'')) continue;
        if(parseFloat(st.opacity)<=0.05 && st.display!=='none'){
          try{ e.remove(); o.push('modal:'+((e.innerText||'').replace(/\s+/g,' ').trim().slice(0,16))); }
          catch(e){}
        }
      }
      return o.join(' | ');})()"""
    hits = []
    for t in targets:
        # ★ 商品选择弹窗的 context **绝对不能碰**：
        #   它的容器也是 div.roo-modal 且 opacity≈0，一旦被当成残留移除，
        #   弹窗会凭空消失（context 随即失效），后面所有针对弹窗的操作全落空。
        try:
            u = cdp.evaluate("location.href", t) or ""
        except Exception:
            continue
        if "selectProduct" in u or "selectGoods" in u:
            continue
        try:
            r = cdp.evaluate(JS, t)
        except Exception:
            continue
        if r:
            hits.append("ctx%s:%s" % (t, r))
    if hits:
        time.sleep(0.4)
    return "; ".join(hits) if hits else "clean"


def type_into(cdp, cid, expr, text, clear=True, fx=0.5, verify=True):
    """聚焦输入框 + 选中清空 + 输入文本。

    ★ 坑 1：直接点坐标聚焦，会被盖在上面的下拉浮层吃掉 —— 焦点落到下拉选项上，
      文字就写进了「菜单分组」的选项里（实测组名被写成「饮料」）。
      解决：优先用 JS `e.focus()` 聚焦（不受任何遮挡影响），并校验
      `document.activeElement === 目标input`，不 OK 才退回真实点击。
    ★ 坑 2：输入后必须回读 value 校验，否则「打进去了但打错地方」不会被发现。
    ★ 坑 3：**表达式取不到元素时必须立刻返回**，绝不能继续 insertText ——
      insertText 会打进「当前焦点所在的那个输入框」，造成莫名其妙的串字
      （实测「选N」定位失败时，"1" 被追加到了组名上，组名变成「加料二选一1」）。
    """
    # 0) 表达式取不到元素 -> 直接放弃（不能带着空焦点往下走）
    try:
        exists = cdp.evaluate("(()=>{const e=(%s); return e?'YES':'NO';})()" % expr, cid)
    except Exception:
        exists = "NO"
    if exists != "YES":
        return "no-element"

    # 1) 滚进视口
    try:
        cdp.evaluate("(function(){try{const e=(%s); if(e&&e.scrollIntoView)"
                     "e.scrollIntoView({block:'center',inline:'center'});}catch(e){}})()" % expr, cid)
        time.sleep(0.25)
    except Exception:
        pass

    focus_js = ("(()=>{const e=(%s); if(!e) return 'NO-EL';"
                "try{ e.focus({preventScroll:true}); }catch(e){ try{e.focus();}catch(x){} }"
                "return (document.activeElement===e)?'OK':'NO';})()" % expr)

    # 2) 聚焦
    st = ""
    try:
        st = cdp.evaluate(focus_js, cid) or ""
    except Exception:
        st = ""
    if st != "OK":
        press_esc(cdp)          # 先关掉可能盖住输入框的下拉浮层
        for point in (fx, 0.15, 0.35, 0.85):
            res = cdp.local_point(cid, expr, fx=point)
            if not res:
                continue
            cdp.click_xy(res[0], res[1])
            time.sleep(0.25)
            try:
                if cdp.evaluate(focus_js, cid) == "OK":
                    break
            except Exception:
                pass

    # 3) 清空 + 输入
    # ★ 清空方式：**JS e.select() 全选 + 真实 insertText 覆盖选区**。
    #   - 不用 JS 原生 setter：会把 React 的 value tracker 同步成新值，
    #     后续 insertText 被判定「值没变」→ onChange 不触发（输入框有字但业务不执行）。
    #   - 不用 Ctrl+A/Backspace：实测 CDP 的 Ctrl+A 在 input 里**根本不生效**
    #     （Backspace 删了 0 个字符），结果文字被追加成
    #     「楚味一人食·自选搭配荤菜200ml二选一楚味一人食·自选搭配」。
    #   - select() 不改 value，insertText 替换选区 → 触发真实 input 事件 → React 正常响应。
    if clear:
        try:
            cdp.evaluate(
                "(()=>{const e=(%s); if(!e) return 'NO';"
                "try{ e.focus(); e.select(); if(e.setSelectionRange) e.setSelectionRange(0,e.value.length); }"
                "catch(err){} return 'SEL';})()" % expr, cid)
        except Exception:
            pass
        time.sleep(0.12)
    cdp.send("Input.insertText", text=text)
    time.sleep(0.35)

    # 4) 回读校验
    try:
        v = cdp.evaluate("(()=>{const e=(%s); return e?String(e.value):'';})()" % expr, cid)
    except Exception:
        v = None
    if verify and v != text:
        return "typed:%s (VERIFY-GOT:%r)" % (text, v)
    return "typed:" + text


def click_el(cdp, cid, expr, scroll=True, verify=None, mode="auto"):
    """点击由 JS 表达式返回的元素。

    mode:
      "auto" —— 默认。**先用 JS 合成事件**（在元素自己所在的 frame 内派发
                pointerdown→click），失败再退回坐标派发。
                ★ 合成事件不走浏览器 hit-test，**不受任何遮挡/遮罩/iframe 叠层影响**，
                  实测在美团表单 iframe 里 100% 可靠；而 CDP 坐标点击在同一处
                  会静默失效（坐标全对、无覆盖层、就是点不动）。
      "xy"   —— 只用坐标派发。**仅用于必须 trusted 的场景**：
                roo 的 Dropdown trigger（如「新建商品」下拉）、
                打开商品选择弹窗的「+ 添加商品」、裁剪弹窗的「保存图片」等
                —— 实测这些用合成事件**看似成功（SYNTH）但其实毫无反应**。
      "js"   —— 只用 JS 合成事件。

    verify: 无参可调用对象，返回 True 表示点击已生效。
            不传则 JS 点击成功即返回（不会重复点击，避免双击开出两个弹层）。
    """
    if mode in ("auto", "js"):
        r = cdp.js_click(cid, expr)
        if r and str(r).startswith("SYNTH"):
            time.sleep(0.9)
            if verify is None or verify():
                return "js:" + str(r)
        if mode == "js":
            return "js-failed:" + str(r)
    # ★ 坐标点击前必须清掉残留浮层：
    #   roo 的离场动画（roo-popup-motion-leave）留下的浮层**不透明度还是 1**，
    #   肉眼可见地盖在按钮上，把真实点击全部吞掉 —— 而合成事件不受影响，
    #   于是「合成事件成功 / 坐标点击无效」的组合极具迷惑性。
    purge_modals(cdp, cid)
    cands = cdp.page_coords_all(cid, expr, scroll=scroll)
    print("    [click_el] 候选坐标:", [(round(a), round(b)) for a, b in cands])
    for c in cands:
        cdp.click_xy(c[0], c[1])
        time.sleep(0.9)
        ok = True if verify is None else verify()
        print("    [click_el] 点击 @%.0f,%.0f -> verify=%s" % (c[0], c[1], ok))
        if ok:
            return f"clicked@{c[0]:.0f},{c[1]:.0f}"
    return "no-element"


def click_menu_item(cdp, cid, expr, verify=None, wait=0.9):
    """点击**下拉菜单项**：JS 合成事件优先（免坐标，实测可靠），坐标兜底。

    与 click_el 的区别：菜单项是普通 DOM（非 portal），事件冒泡到 React root，
    React 合成 onClick 能正常响应，因此可以完全绕开坐标口径冲突。
    """
    r = cdp.js_click(cid, expr)
    if r and str(r).startswith("SYNTH"):
        time.sleep(wait)
        if verify is None or verify():
            return "js:" + str(r)
    cands = cdp.page_coords_all(cid, expr, scroll=False)
    for c in cands:
        cdp.click_xy(c[0], c[1])
        time.sleep(wait)
        if verify is None or verify():
            return f"clicked@{c[0]:.0f},{c[1]:.0f}"
    return "no-element"


def click_text(cdp, cid, text, nth=-1, exact=True, verify=None):
    """按可见文本点击页面元素（默认取最后一个匹配）。"""
    r = cdp.js_click_text(cid, text, nth=nth, exact=exact)
    if r:
        time.sleep(0.9)
        if verify is None or verify():
            return "js:" + str(r)
    # 兜底：坐标
    expr = ("(() => { const l=[...document.querySelectorAll('*')].filter(e=>{"
            "const s=(e.innerText||'').trim(); if(!s) return false;"
            "return %s ? s===%s : s.indexOf(%s)>=0; }); "
            "const e=l[%d]; return e||null; })()"
            % ("true" if exact else "false", json.dumps(text), json.dumps(text),
               nth if nth >= 0 else -1))
    cands = cdp.page_coords_all(cid, expr, scroll=False)
    for c in cands:
        cdp.click_xy(c[0], c[1])
        time.sleep(0.9)
        if verify is None or verify():
            return f"clicked@{c[0]:.0f},{c[1]:.0f}"
    return "not-found:" + text


def find_ctx(cdp, keyword, probe=None):
    """按文本关键字找 context；probe 为兜底 JS 表达式"""
    cands = cdp.contexts()
    for c in cands:
        if keyword in c["text"]:
            return c
    if probe:
        for c in cands:
            try:
                if cdp.evaluate(probe, c["id"]) == "YES":
                    return c
            except Exception:
                continue
    return None


def select_option(cdp, cid, trigger_expr, option_text, timeout=4.0):
    """点击下拉触发器 -> 等待 -> 点击文本为 option_text 的选项"""
    r = click_el(cdp, cid, trigger_expr)
    if r == "no-element":
        return "no-trigger"
    t0 = time.time()
    opt_expr = (
        "(() => { const list=[]; for(const e of document.querySelectorAll('li,div,span,label,td')){ "
        "const t=(e.innerText||'').trim(); if(t===%s && e.children.length===0) list.push(e); } "
        "list.sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top); "
        "return list.length? list[list.length-1] : null; })()" % json.dumps(option_text)
    )
    while time.time() - t0 < timeout:
        res = click_menu_item(cdp, cid, opt_expr)
        if res != "no-element":
            return f"selected:{option_text}"
        time.sleep(0.4)
    return f"option-not-found:{option_text}"


def click_button(cdp, cid, text, nth=0, tag="button", verify=None):
    """点击文本等于 text 的按钮（第 nth 个）。

    ★ innerText 必须**去空白后**再比较：美团的按钮文本常带换行/空格
      （「添加商品分组」实际 innerText 含不可见空白），直接 trim 精确匹配会漏掉，
      导致 click_button 返回 no-element。
    """
    key = "".join(str(text).split())
    expr = (
        "(() => { const list=[]; for(const e of document.querySelectorAll(%s)){ "
        "const t=(e.innerText||e.textContent||'').replace(/\\s+/g,'').trim(); if(t===%s) list.push(e); } "
        "return list[%d] || null; })()" % (json.dumps(tag), json.dumps(key), nth)
    )
    return click_el(cdp, cid, expr, verify=verify)


def select_opt(cdp, cid, frame_id, trigger_expr, option_text, timeout=5.0):
    """打开下拉并按文本选项。选项点击走 JS 合成事件，不依赖坐标。"""
    r = click_el(cdp, cid, trigger_expr, scroll=False)
    if r == "no-element":
        return "no-trigger"
    t0 = time.time()
    li_expr = ("(() => { const l=[...document.querySelectorAll('li')].filter(e=>e.textContent.trim()===%s); "
               "return l.length? l[l.length-1] : null; })()" % json.dumps(option_text))
    while time.time() - t0 < timeout:
        res = click_menu_item(cdp, cid, li_expr)
        if res != "no-element":
            return f"selected:{option_text}"
        time.sleep(0.4)
    return f"option-not-found:{option_text}"


PANEL_VISIBLE_JS = ("(()=>{const p=[...document.querySelectorAll('ul.roo-dropdown-menu,[class*=dropdown-menu]')]"
                    ".find(e=>{const st=getComputedStyle(e); const r=e.getBoundingClientRect();"
                    "return st.display!=='none'&&st.visibility!=='hidden'&&st.opacity!=='0'"
                    "&&r.height>10&&r.width>10;}); return p?'YES':'';})()")


def ensure_visible(cdp, cid, expr):
    """把元素滚到视口内并确认。

    ★ 下拉触发器可能在视口外（美团表单很长，菜单分组在顶部、份量在底部）。
      视口外的元素坐标是负数，点击会落到别处 —— 实测菜单分组点击后值被清空。
    """
    js = ("(()=>{const e=(%s); if(!e) return 'NO';"
          "const H=window.innerHeight||800, W=window.innerWidth||1200;"
          "let r=e.getBoundingClientRect();"
          "let dy=0,dx=0;"
          "if(r.top<4||r.bottom>H-4) dy=r.top - H/2;"
          "if(r.left<4||r.right>W-4) dx=r.left - W/2;"
          "if(dy||dx) window.scrollBy(dx,dy);"
          "r=e.getBoundingClientRect();"
          "return JSON.stringify({top:Math.round(r.top),left:Math.round(r.left),"
          "inView:(r.top>=0&&r.bottom<=H&&r.left>=0&&r.right<=W)});})()" % expr)
    for _ in range(4):
        try:
            v = cdp.evaluate(js, cid)
        except Exception:
            return False
        if not v or v == "NO":
            return False
        try:
            d = json.loads(v)
        except Exception:
            return True
        if d.get("inView"):
            return True
        time.sleep(0.4)
    return False


def _cand_js(key, nth):
    """返回**下拉面板内**按优先级排序后的第 nth 个候选选项。

    ★ 美团 roo 下拉的选项结构是 UL.roo-dropdown-menu > LI > A：
      LI 有子节点（所以「只取叶子」会把真正的选项 LI 过滤掉），
      但 LI 里的 A 是叶子且可点 —— 因此**两者都收**，
      排序时「在下拉浮层内」优先、「叶子节点」次之。
    ★ 选项文本可能带后缀（如「一人食套餐(4)」），所以用「相等或前缀匹配」。
    ★ 只在**可见的下拉面板内**找 —— 页面上别处也有同名文本（左侧分组列表）。
    """
    return ("(()=>{const pan=[...document.querySelectorAll('ul.roo-dropdown-menu,[class*=dropdown-menu]')]"
            ".find(e=>{const st=getComputedStyle(e); const r=e.getBoundingClientRect();"
            "return st.display!=='none'&&st.visibility!=='hidden'&&st.opacity!=='0'"
            "&&r.height>10&&r.width>10;});"
            "if(!pan) return null; const all=[...pan.querySelectorAll('li, a, div, span')]; const o=[];"
            "for(let i=0;i<all.length;i++){ const e=all[i];"
            "const t=(e.innerText||e.textContent||'').replace(/\\s+/g,'').trim();"
            "if(t!==%s && t.indexOf(%s)!==0) continue;"
            "const st=getComputedStyle(e); const r=e.getBoundingClientRect();"
            "if(st.display==='none'||st.visibility==='hidden'||st.opacity==='0') continue;"
            "if(r.width<=0||r.height<=0) continue;"
            "o.push({e:e,leaf:e.children.length===0}); }"
            "o.sort((a,b)=>(a.leaf?0:1)-(b.leaf?0:1));"
            "const e=(o[%d]||{}).e; return e||null;})()"
            % (json.dumps(key), json.dumps(key), nth))


def _cand_count_js(key):
    return ("(()=>{const pan=[...document.querySelectorAll('ul.roo-dropdown-menu,[class*=dropdown-menu]')]"
            ".find(e=>{const st=getComputedStyle(e); const r=e.getBoundingClientRect();"
            "return st.display!=='none'&&st.visibility!=='hidden'&&st.opacity!=='0'"
            "&&r.height>10&&r.width>10;});"
            "if(!pan) return 0; let n=0;"
            "for(const e of pan.querySelectorAll('li, a, div, span')){"
            "const t=(e.innerText||e.textContent||'').replace(/\\s+/g,'').trim();"
            "if(t!==%s && t.indexOf(%s)!==0) continue;"
            "const st=getComputedStyle(e); const r=e.getBoundingClientRect();"
            "if(st.display==='none'||st.visibility==='hidden'||st.opacity==='0') continue;"
            "if(r.width<=0||r.height<=0) continue; n++;}"
            "return n;})()" % (json.dumps(key), json.dumps(key)))


def _wait_value(cdp, cid, trigger_expr, want, timeout=4.0):
    """轮询等待下拉框的值变成目标值（React 异步更新，立即读会拿到旧值）。"""
    js = "(()=>{const e=(%s); return e?String(e.value||''):'';})()" % trigger_expr
    t0 = time.time()
    v = ""
    while time.time() - t0 < timeout:
        try:
            v = cdp.evaluate(js, cid)
        except Exception:
            v = ""
        if v == want:
            return True
        time.sleep(0.4)
    return False


def select_popup(cdp, cid, frame_id, trigger_expr, option_text, scroll_top=True,
                 verify_value=True):
    """打开下拉并选中选项。

    ★ 关键 1：点击前**确保触发器在视口内**（否则坐标是负数，点击落空，
      实测会把下拉值清空）。
    ★ 关键 2：**等下拉面板真的出现**再找选项，并且**只在面板内**找 ——
      页面上别处也有同名文本（左侧分组列表）。
    ★ 关键 3：点击后**轮询等待**值变成目标值 —— React 异步更新，
      立即读会拿到旧值，曾把「其实选成功了」误判成 FAILED。
    """
    key = "".join(str(option_text).split())
    if scroll_top:
        ensure_visible(cdp, cid, trigger_expr)
        time.sleep(0.6)

    for attempt in range(3):
        click_el(cdp, cid, trigger_expr, scroll=False)
        panel_ok = False
        for _ in range(8):
            time.sleep(0.35)
            try:
                if cdp.evaluate(PANEL_VISIBLE_JS, cid) == "YES":
                    panel_ok = True
                    break
            except Exception:
                pass
        if not panel_ok:
            # roo 的 Select 可能把 onClick 绑在包裹容器上，而不是 input 本身
            wrap = ("(()=>{const e=(%s); if(!e) return null;"
                    "const p=e.closest('div[class*=select],div[class*=Select],div[class*=roo-select]')"
                    "||e.parentElement; return p||null;})()" % trigger_expr)
            click_el(cdp, cid, wrap, scroll=False)
            for _ in range(6):
                time.sleep(0.35)
                try:
                    if cdp.evaluate(PANEL_VISIBLE_JS, cid) == "YES":
                        panel_ok = True
                        break
                except Exception:
                    pass
        if not panel_ok:
            # 可能是离场动画残留的隐形遮罩吞掉了点击
            dismiss_stuck_backdrops(cdp, cid, timeout=1.0)
            press_esc(cdp)
            continue
        try:
            n = int(cdp.evaluate(_cand_count_js(key), cid) or 0)
        except Exception:
            n = 0
        if not n:
            press_esc(cdp)
            continue
        for k in range(min(n, 3)):
            res = click_menu_item(cdp, cid, _cand_js(key, k))
            if res == "no-element":
                continue
            if not verify_value:
                return f"selected:{option_text}"
            if _wait_value(cdp, cid, trigger_expr, option_text, timeout=3.0):
                return f"selected:{option_text} (verified)"
            press_esc(cdp)
            time.sleep(0.4)
            click_el(cdp, cid, trigger_expr, scroll=False)
            for _ in range(6):
                time.sleep(0.3)
                try:
                    if cdp.evaluate(PANEL_VISIBLE_JS, cid) == "YES":
                        break
                except Exception:
                    pass
        press_esc(cdp)
    try:
        v = cdp.evaluate("(()=>{const e=(%s); return e?String(e.value||''):'';})()" % trigger_expr, cid)
    except Exception:
        v = ""
    return f"FAILED-select:{option_text} (当前值={v!r})"


def cdp_connect():
    p = get_page()
    c = CDP(p["webSocketDebuggerUrl"])
    c.ensure_dom()
    try:
        c.contexts()          # 预热 _ctxmap，供 frame_of() 查 frameId
    except Exception:
        pass
    # ★ 唤醒页面：后台标签页里 Chrome 会冻结 CSS 动画时钟，
    #   弹窗会停在入场动画第 0 帧（遮罩 opacity=0、dialog scale(0)、
    #   按钮 pointer-events:none），表现为「弹窗开了却什么都点不动」。
    #   这里统一处理，所有脚本自动受益。
    try:
        c.wake()
    except Exception:
        pass
    return c


def dismiss_stuck_backdrops(cdp, cid, timeout=5.0, all_ctx=True, close_open=False):
    """清理弹窗残留（**残留弹窗是坐标点击失效的头号元凶**）。

    美团 roo 弹窗关闭时给遮罩加了 roo-mask-motion-leave 离场动画，
    动画结束后**节点不被移除**：opacity 已是 0（看不见），但 display:block +
    pointer-events:auto —— 仍然盖满整个页面，把后面所有点击和输入全部吞掉。

    ★ 决定性发现：**打开中弹窗的 backdrop 也会吞掉坐标点击**。
      表现为「表单里所有坐标点击失效」（radio 点不动、下拉打不开、商品搜索搜不到），
      但 **JS 合成事件完全正常**（合成事件不走 hit-test，直接派发到目标元素）。
      所以排查这类现象时，先清弹窗，再怀疑坐标。

    ★ 关键：商品选择弹窗是**独立 iframe**，遮罩不在表单 context 里，
      只扫表单 ctx 清不掉 —— 必须**遍历所有 context**（含顶层）。

    close_open=True：连**打开中的**弹窗容器一起移除（适合「刚打开新表单」时用，
    确保起点干净）。
    """
    js_count = "(()=>document.querySelectorAll('div.roo-modal.backdrop').length)()"
    targets = []
    if all_ctx:
        try:
            targets = [c["id"] for c in cdp.contexts()]
        except Exception:
            targets = [cid]
    else:
        targets = [cid]

    if close_open:
        # 连打开中的弹窗容器一起移除（表单刚打开时最安全）
        CLOSE_ALL = r"""(()=>{let n=0;
          for(const m of document.querySelectorAll('div.roo-modal, div[class*=block-user-form-modal], div[class*=ffw-modal], [class*=backdrop]')){
            try{ m.remove(); n++; }catch(e){}
          }
          return n;})()"""
        tot = 0
        for t in targets:
            try:
                tot += int(cdp.evaluate(CLOSE_ALL, t) or 0)
            except Exception:
                pass
        return "closed-open-modals:%d" % tot

    t0 = time.time()
    while time.time() - t0 < timeout:
        left = 0
        for t in targets:
            try:
                left += int(cdp.evaluate(js_count, t) or 0)
            except Exception:
                pass
        if left == 0:
            return "no-backdrop"
        time.sleep(0.4)

    # ★ 关键修正：残留弹窗**不只是遮罩** —— 实测表单里会堆着 11 个 opacity=1 的
    #   roo-modal backdrop（block-user-form-modal / ffw-modal 等），
    #   所属的 modal 容器内容早已清空、但容器本身还是 fixed 盖在页面上，
    #   把所有点击全部吞掉（radio 点不动、下拉打不开、商品搜索搜不到）。
    #   所以分两类处理：
    #     - **空的残留 modal 容器**（无可见内容 / 尺寸为 0）→ 整个 remove
    #     - 真正打开中的弹窗 → 只把 backdrop 的 pointer-events 关掉，不动 DOM
    CLEAN_JS = r"""(()=>{const o=[];
      for(const m of document.querySelectorAll('div.roo-modal, div[class*=block-user-form-modal], div[class*=ffw-modal]')){
        const st=getComputedStyle(m); const r=m.getBoundingClientRect();
        const txt=(m.innerText||'').trim();
        if(st.display==='none'||st.visibility==='hidden'||r.height<=0||!txt){
          try{ m.remove(); o.push('RM-MODAL'); }catch(e){ o.push('rm-fail'); }
        }
      }
      for(const b of document.querySelectorAll('[class*=backdrop]')){
        b.style.pointerEvents='none'; o.push('pe-none');
      }
      return o.join(',');})()"""
    hits = []
    for t in targets:
        try:
            r = cdp.evaluate(CLEAN_JS, t)
            if r:
                hits.append("ctx%s: %s" % (t, r))
        except Exception:
            continue
    if not hits:
        return "no-backdrop"
    return "cleaned: " + " ;; ".join(hits)
