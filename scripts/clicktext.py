#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""真实坐标点击：在指定文本元素上派发 mousePressed/Released，自动穿透 iframe 偏移。
用法: python clicktext.py <text> [--kw <keyword>] [--nth N] [--sel <css>]
"""
import sys, json, time, os, urllib.request, websocket, re

PORT = 9222
CWD = os.path.dirname(os.path.abspath(__file__))


def list_pages():
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/list")
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def get_page():
    for p in list_pages():
        if p.get("type") == "page" and "waimaie.meituan.com" in p.get("url", ""):
            return p
    raise SystemExit("no meituan page")


class JSError(RuntimeError):
    """JS 表达式求值时抛出的异常（语法错误 / 运行时错误）。"""
    pass


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=90)
        self._id = 0
        self.events = []

    def send(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            r = json.loads(self.ws.recv())
            if "id" in r and r.get("id") == self._id:
                if "error" in r:
                    raise RuntimeError(r["error"])
                return r
            self.events.append(r)

    def evaluate(self, expr, ctx=None, strict=False):
        """在指定 context 求值。

        ★ 默认**静默**返回 None（保持向后兼容）；
          strict=True 时，若 JS 抛异常/语法错误，抛出 JSError 并带上原始消息。
        ★ 为什么要加这个：Runtime.evaluate 对 JS 语法错误**不抛 Python 异常**，
          只在 exceptionDetails 里带信息，而原来这里直接 return res.get("value")
          → 语法错误被**静默吞掉**返回 None，调用方一律当成「元素不存在」，
          于是排查时反复怀疑选择器/CSS 类名，而真正的原因是表达式本身写错了
          （例如 `array.map(...).filter(...)` 写成了 `{...}.filter(...)`）。
        """
        self.send("Runtime.enable")
        params = dict(expression=expr, returnByValue=True, awaitPromise=True)
        if ctx is not None:
            params["contextId"] = int(ctx)
        r = self.send("Runtime.evaluate", **params)
        if strict:
            det = r.get("result", {}).get("exceptionDetails")
            if det:
                desc = det.get("exception", {}).get("description") or det.get("text") or "JS error"
                raise JSError("%s\n  expr: %s" % (desc, expr[:300]))
        res = r.get("result", {}).get("result", {})
        return res.get("value")

    def wake(self):
        """★ 把后台标签页「叫醒」，否则所有弹窗都会卡在入场动画第一帧。

        症状（美团「上传图片」裁剪弹窗最典型）：
          - 弹窗 DOM 明明插进来了，文本也在，但**什么都点不动**
          - `div.roo-modal` 的 class 停在 `roo-mask-motion-appear`
          - 遮罩 `opacity=0`、dialog `transform: matrix(0,0,0,0,0,0)`（缩放为 0）
          - 按钮 `pointer-events:none`、`getBoundingClientRect()` 全是 0x0
          - `document.getAnimations()` 里每个动画 `currentTime=0` 且 `playState=running`

        根因：Chrome 对 **hidden（后台）标签页** 不推进 CSS 动画时钟。
        此时 `document.visibilityState === 'hidden'`，
        弹窗永远停在 appear 动画的 0% 关键帧 → 遮罩透明、内容缩放为 0。

        解决：
          1) `Emulation.setFocusEmulationEnabled` —— 强制页面认为「有焦点」，
             即使标签页在后台也照常推进动画（比 `Page.bringToFront` 更温和，
             不会把用户的浏览器窗口抢到前台）
          2) `Page.bringToFront` —— 真正把标签页切到前台（兜底）
        """
        try:
            self.send("Emulation.setFocusEmulationEnabled", enabled=True)
        except Exception:
            pass
        try:
            self.send("Page.bringToFront")
        except Exception:
            pass
        return True

    def finish_animations(self, ctx_id):
        """★ 把当前 context 里所有 CSS 动画/过渡**直接推到终态**。

        配合 wake() 使用：即使动画时钟仍被冻结，也能让弹窗从
        「appear 第 0 帧」直接变成「完全展开」。
        实测：finish 后 `roo-modal` opacity 1、dialog `transform:none`、
        按钮 `pointer-events:auto`、`elementFromPoint` 能命中按钮内部的 span。
        """
        return self.evaluate(
            "(()=>{ if(!document.getAnimations) return 'NA';"
            " let n=0; for(const a of document.getAnimations()){ try{ a.finish(); n++; }catch(e){} }"
            " return 'finished='+n; })()", ctx_id)

    def contexts(self):
        """返回 [{id, frameId, text}]。context 累积保存，避免清空事件缓冲漏掉新建 iframe。

        ★★★ 关键：**绝不能在这里清空 self.events**。
          CDP 事件只在 `send()` 等待响应期间从 websocket 读取，
          也就是说「两次 send() 之间」发生的事件会被留在 socket 缓冲区里，
          直到下一次 send() 才被收取。
          如果这里把 events 清空了，那么「清空之后、下一次 send 之前」新建的
          iframe（商品选择弹窗就是这种）它的 executionContextCreated 事件
          **会被永久丢弃** —— 表现是：弹窗明明打开了，但 contexts() 里根本
          找不到它，后面所有针对弹窗的操作全部落空。
        """
        if not hasattr(self, "_ctxmap"):
            self._ctxmap = {}
        self.send("Runtime.enable")
        # ★ 不要等太久：contexts() 会被高频调用（每次操作前刷新），
        #   1 秒的固定等待会让整条流水线慢到超时。0.4s 足够收集事件。
        time.sleep(0.4)
        for e in self.events:
            if e.get("method") == "Runtime.executionContextCreated":
                c = e["params"]["context"]
                self._ctxmap[c["id"]] = c
            elif e.get("method") == "Runtime.executionContextDestroyed":
                self._ctxmap.pop(e["params"].get("executionContextId"), None)
        # 只裁剪不整体清空（裁剪也要留够长度，避免刚收到的事件被切掉）
        if len(self.events) > 600:
            self.events = self.events[-400:]
        out = []
        for cid, c in self._ctxmap.items():
            aux = c.get("auxData", {})
            if aux.get("isDefault") is False:
                continue
            txt = ""
            try:
                txt = self.evaluate("document.body?document.body.innerText.slice(0,300):''", cid) or ""
            except Exception:
                pass
            out.append({"id": cid, "frameId": aux.get("frameId", ""), "text": txt})
        return out

    def offsets(self):
        """frameId -> (x,y) 页面坐标偏移。递归处理嵌套 iframe。"""
        self.send("DOM.enable")
        doc = self.send("DOM.getDocument", depth=-1, pierce=True)
        root = doc["result"]["root"]
        res = {}

        def walk(node, ox, oy):
            for ch in node.get("children", []) or []:
                if ch.get("nodeName") == "IFRAME":
                    try:
                        bm = self.send("DOM.getBoxModel", nodeId=ch["nodeId"])
                        c = bm["result"]["model"]["content"]
                        if isinstance(c[0], (int, float)):
                            x, y = min(c[0::2]), min(c[1::2])
                        else:
                            x = min(p[0] for p in c)
                            y = min(p[1] for p in c)
                        nx, ny = ox + x, oy + y
                        fid = ch.get("frameId")
                        if fid:
                            res[fid] = (nx, ny)
                        cd = ch.get("contentDocument")
                        if cd:
                            walk(cd, nx, ny)
                    except Exception as e:
                        print(f"  [offsets] err {str(e)[:60]}")
                else:
                    walk(ch, ox, oy)

        walk(root, 0, 0)
        return res

    def ensure_dom(self):
        if not getattr(self, "_dom_ready", False):
            self.send("DOM.enable")
            self.send("DOM.getDocument", depth=-1, pierce=True)
            self._dom_ready = True

    def refresh_dom(self):
        """强制刷新 DOM 树缓存（iframe 被 React 重建后 nodeId 会失效）。"""
        self.send("DOM.enable")
        self.send("DOM.getDocument", depth=-1, pierce=True)
        self._dom_ready = True

    def _node_box(self, ctx_id, expr):
        # 注意：必须 returnByValue=False，否则拿不到 objectId，DOM.requestNode 无从下手
        r = self.send("Runtime.evaluate", expression=expr, contextId=int(ctx_id), returnByValue=False)
        oid = r.get("result", {}).get("result", {}).get("objectId")
        if not oid:
            return None
        try:
            nid = self.send("DOM.requestNode", objectId=oid).get("result", {}).get("nodeId")
        except Exception:
            return None
        if not nid:
            return None
        try:
            c = self.send("DOM.getBoxModel", nodeId=nid)["result"]["model"]["content"]
        except Exception:
            return None
        if isinstance(c[0], (int, float)):
            xs, ys = c[0::2], c[1::2]
        else:
            xs = [p[0] for p in c]
            ys = [p[1] for p in c]
        return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0

    def frame_of(self, ctx_id):
        """由 contextId 找 frameId（_ctxmap 由 contexts() 预热）"""
        c = getattr(self, "_ctxmap", {}).get(int(ctx_id))
        if not c:
            return None
        return c.get("auxData", {}).get("frameId")

    @staticmethod
    def _box_center(quad):
        """quad 可以是扁平数组 [x1,y1,x2,y2,...] 或点数组 [[x,y],...]"""
        if not quad:
            return (0.0, 0.0)
        if isinstance(quad[0], (int, float)):
            xs, ys = quad[0::2], quad[1::2]
        else:
            xs = [p[0] for p in quad]
            ys = [p[1] for p in quad]
        return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0

    def _node_box_raw(self, ctx_id, expr):
        """DOM.getBoxModel 的 content 顶点数组（可能是扁平 8 元素数组）"""
        # 注意：必须 returnByValue=False，否则拿不到 objectId
        r = self.send("Runtime.evaluate", expression=expr, contextId=int(ctx_id), returnByValue=False)
        oid = r.get("result", {}).get("result", {}).get("objectId")
        if not oid:
            return None
        try:
            nid = self.send("DOM.requestNode", objectId=oid).get("result", {}).get("nodeId")
        except Exception:
            return None
        if not nid:
            return None
        try:
            return self.send("DOM.getBoxModel", nodeId=nid)["result"]["model"]["content"]
        except Exception:
            return None

    def _rect_box(self, ctx_id, expr):
        """frame 内 getBoundingClientRect 的四点"""
        v = self.evaluate(
            "(()=>{const e=(%s); if(!e) return null; const r=e.getBoundingClientRect();"
            "if(r.width<=0 && r.height<=0) return null;"
            "return JSON.stringify([[r.x,r.y],[r.right,r.top],[r.right,r.bottom],[r.left,r.bottom]]);})()"
            % expr, ctx_id)
        if not v:
            return None
        try:
            return json.loads(v)
        except Exception:
            return None

    # ---------- 免坐标点击：JS 合成鼠标事件 ----------
    # 背景：getBoundingClientRect 是 frame 视口坐标，DOM.getBoxModel 常是文档坐标，
    # 两者在「有滚动 / 有弹层 / iframe 偏移」时口径会打架，实测同一元素两次测量能差 210px。
    # 与其去猜口径，不如直接绕过坐标：在元素**自己所在的 frame 内**派发真实事件序列。
    # 美团的 create-button-text 是普通 DOM（未 portal 到 body），事件冒泡到 React root，
    # React 的合成 onClick 能正常响应 —— 实测「新建套餐」100% 点中。
    # ★ scroll 必须默认关闭：scrollIntoView 会触发滚动，roo 下拉浮层随之关闭，
    #   点菜单项时一 scroll 就把浮层关掉了（表现为「点了没反应」）。
    JS_CLICK = """(()=>{
      let e=(%s); if(!e) return 'no-el';
      /* ★ 关键：按钮类元素要**点它内部的子元素**（span/a/svg）——
           直接在 <button> 上派发事件**不会触发** React 的 onClick
           （实测「+ 添加商品」直接点 button 无效，点内部 span 立刻弹出选择弹窗）。
           事件会从子元素冒泡到 button，行为等价且更可靠。 */
      try{
        if(e.tagName==='BUTTON'||e.tagName==='A'){
          const inner=e.querySelector('span, i, em, svg');
          if(inner) e=inner;
        }
      }catch(err){}
      if(%s) { try{ e.scrollIntoView({block:'center',inline:'nearest'}); }catch(err){} }
      else {
        /* ★ 默认不滚动，但**元素在视口外时必须滚进来**：
             合成事件派发给视口外的元素，浏览器不会触发它的交互
             （实测「组类型」下拉在视口外时点了完全没反应）。
             视口内的元素不滚动 —— 点下拉菜单项时一 scroll 就会把浮层关掉。 */
        try{
          const vr=document.documentElement.clientHeight||window.innerHeight;
          const vw=document.documentElement.clientWidth||window.innerWidth;
          const r0=e.getBoundingClientRect();
          if(r0.bottom<0||r0.top>vr||r0.right<0||r0.left>vw){
            e.scrollIntoView({block:'center',inline:'center'});
          }
        }catch(err){}
      }
      const r=e.getBoundingClientRect();
      const cx=Math.round(r.x+r.width/2), cy=Math.round(r.y+r.height/2);
      const mk=(t)=>new MouseEvent(t,{bubbles:true,cancelable:true,view:window,
          clientX:cx,clientY:cy,button:0,buttons:(t==='mousedown'||t==='pointerdown')?1:0});
      for(const t of ['pointerdown','mousedown','pointerup','mouseup','click']){
        try{ e.dispatchEvent(mk(t)); }catch(err){}
      }
      return 'SYNTH@'+cx+','+cy;
    })()"""

    def js_click(self, ctx_id, expr, scroll=False):
        """在目标 frame 内派发完整鼠标事件序列点击元素，返回结果字符串或 None。

        ★ 视口外的元素必须**先滚进视口、等滚动结束**再派发事件：
          合成事件派发给视口外的元素，浏览器不会触发它的交互
          （实测「组类型」下拉触发器在视口外时点了完全没反应）。
        """
        if not scroll:
            try:
                need = self.evaluate(
                    "(()=>{const e=(%s); if(!e) return 'NO'; const r=e.getBoundingClientRect();"
                    "const vr=document.documentElement.clientHeight||window.innerHeight;"
                    "const vw=document.documentElement.clientWidth||window.innerWidth;"
                    "return (r.bottom<0||r.top>vr||r.right<0||r.left>vw)?'YES':'NO';})()" % expr, ctx_id)
                if need == "YES":
                    self.evaluate(
                        "(function(){try{const e=(%s); if(e) e.scrollIntoView({block:'center',inline:'center'});}"
                        "catch(e){}})()" % expr, ctx_id)
                    time.sleep(0.7)
            except Exception:
                pass
        try:
            return self.evaluate(self.JS_CLICK % (expr, "true" if scroll else "false"), ctx_id)
        except Exception as e:
            return "err:%s" % str(e)[:80]

    def js_click_text(self, ctx_id, text, nth=-1, exact=True, visible_only=True, scroll=False):
        """按可见文本点击（默认最后一个匹配；nth=-1 取最后一个，>=0 取第 n 个）。

        返回 'CLICKED:<text>@<x>,<y>' 或 None。
        """
        js = """(()=>{
          const t=%s, exact=%s, nth=%d, vis=%s, scr=%s;
          const all=[...document.querySelectorAll('*')].filter(e=>{
            const s=(e.innerText||e.textContent||'').trim();
            if(!s) return false;
            return exact ? s===t : s.indexOf(t)>=0;
          });
          const list=all.filter(e=>{
            if(!vis) return true;
            const r=e.getBoundingClientRect();
            if(r.width<=0||r.height<=0) return false;
            const st=getComputedStyle(e);
            return st.display!=='none'&&st.visibility!=='hidden'&&st.opacity!=='0';
          });
          const e = nth>=0 ? list[nth] : list[list.length-1];
          if(!e) return null;
          if(scr) { try{ e.scrollIntoView({block:'center',inline:'nearest'}); }catch(err){} }
          const r=e.getBoundingClientRect();
          const cx=Math.round(r.x+r.width/2), cy=Math.round(r.y+r.height/2);
          const mk=(ty)=>new MouseEvent(ty,{bubbles:true,cancelable:true,view:window,
              clientX:cx,clientY:cy,button:0,buttons:(ty==='mousedown'||ty==='pointerdown')?1:0});
          for(const ty of ['pointerdown','mousedown','pointerup','mouseup','click']){
            try{ e.dispatchEvent(mk(ty)); }catch(err){}
          }
          return 'CLICKED:'+t+'@'+cx+','+cy;
        })()""" % (json.dumps(text), "true" if exact else "false", int(nth),
                    "true" if visible_only else "false", "true" if scroll else "false")
        try:
            return self.evaluate(js, ctx_id)
        except Exception as e:
            return None

    # 「frame 局部坐标 -> 页面绝对坐标」= 各级 iframe 在父文档中的偏移累加
    JS_FRAME_OFFSET = r"""(()=>{ try{
      let x=0,y=0, e=window.frameElement, d=0;
      while(e && d<6){
        const r=e.getBoundingClientRect();
        x+=r.x; y+=r.y;
        const p=e.parentElement;
        e=(p&&p.contentWindow)? p.contentWindow.frameElement : null;
        d++;
      }
      return JSON.stringify({x:x,y:y});
    }catch(e){ return null; }})()"""

    def _abs_correction(self, ctx_id, expr):
        """「frame 局部坐标 -> 页面绝对坐标」的修正量 = 各级 iframe 在父文档中的偏移。

        ★ 首选纯 JS 的 `window.frameElement` 链：在目标 frame 内逐层取
          父文档里 iframe 元素的 getBoundingClientRect 累加 —— 无歧义、不依赖
          DOM 树缓存、也不受 React 重建 iframe 影响。
          （旧实现靠 DOM.getFrameOwner / offsets() 遍历 DOM 树，会在 React 重建
            iframe 后失配，偏移算成 (0,0) 或少算一个层级，点击整体偏移 210px。）
        兜底：DOM.getFrameOwner -> getBoxModel，再兜底 offsets() 递归遍历。
        """
        try:
            v = self.evaluate(self.JS_FRAME_OFFSET, ctx_id)
            if v:
                d = json.loads(v)
                return (float(d["x"]), float(d["y"]))
        except Exception:
            pass
        fid = self.frame_of(ctx_id)
        if not fid:
            return (0.0, 0.0)
        try:
            owner = self.send("DOM.getFrameOwner", frameId=fid).get("result", {}).get("nodeId")
            if owner:
                c = self.send("DOM.getBoxModel", nodeId=owner)["result"]["model"]["content"]
                if isinstance(c[0], (int, float)):
                    xs, ys = c[0::2], c[1::2]
                else:
                    xs = [p[0] for p in c]
                    ys = [p[1] for p in c]
                return (float(min(xs)), float(min(ys)))
        except Exception:
            pass
        try:
            off = self.offsets().get(fid, (0, 0))
        except Exception:
            off = (0, 0)
        return (float(off[0]), float(off[1]))

    def _hit_ok(self, ctx_id, expr, lx, ly):
        """在自身 frame 内做命中检测，判断 (lx,ly) 处是否就是目标元素"""
        js = ("(()=>{const e=(%s); if(!e) return 'no-el';"
              "const h=document.elementFromPoint(%f,%f);"
              "if(!h) return 'null';"
              "if(h===e) return 'self';"
              "if(e.contains&&e.contains(h)) return 'child';"
              "if(h.contains&&h.contains(e)) return 'parent';"
              "return 'other:'+h.tagName+'.'+String(h.className).slice(0,30);})()"
              % (expr, lx, ly))
        try:
            return self.evaluate(js, ctx_id)
        except Exception:
            return "err"

    def page_coords(self, ctx_id, expr, scroll=True):
        """得到元素的页面绝对坐标（支持嵌套 iframe），并做命中校验。"""
        self.ensure_dom()
        if scroll:
            try:
                self.evaluate(
                    "(function(){ try{ const el=(%s); if(el && el.scrollIntoView){ el.scrollIntoView({block:'center',inline:'center'}); } }catch(e){} })()"
                    % expr, ctx_id)
                time.sleep(0.35)
            except Exception:
                pass

        R = self._rect_box(ctx_id, expr)
        if R is None:
            # DOM/上下文可能刚变，刷新后重试
            self.refresh_dom()
            time.sleep(0.4)
            R = self._rect_box(ctx_id, expr)
        if R is None:
            return None
        rc = self._box_center(R)
        off = self._abs_correction(ctx_id, expr)

        # 候选 1：局部 rect + iframe 偏移（永远可靠）
        cands = [(rc[0] + off[0], rc[1] + off[1])]

        # 候选 2：getBoxModel（可能是绝对坐标，也可能漏了偏移）
        G = self._node_box_raw(ctx_id, expr)
        if G:
            gc = self._box_center(G)
            if abs(gc[0] - rc[0]) < 4 and abs(gc[1] - rc[1]) < 4:
                cands.append((gc[0] + off[0], gc[1] + off[1]))   # G 是局部
            else:
                cands.append(gc)                                # G 已绝对

        # 命中检测：挑真正落在目标元素上的那个
        for c in cands:
            r = self._hit_ok(ctx_id, expr, c[0] - off[0], c[1] - off[1])
            if r in ("self", "child", "parent"):
                return c
        return cands[0]

    def page_coords_all(self, ctx_id, expr, scroll=True):
        """返回所有候选的页面绝对坐标（按可靠性排序）。

        实测存在两种坐标口径：
          - getBoundingClientRect 是 frame **视口**坐标（会减去 frame 内滚动量）
          - DOM.getBoxModel 通常是**文档**坐标
        谁对谁错取决于 frame 内部有没有滚动，所以两个都算出来，交给调用方点了再验证。

        另外「iframe 偏移」本身也可能算错（offsets() 依赖 DOM 树，React 重建 iframe 后会失配），
        因此这里输出 **4 种口径组合**的候选，把「加不加偏移」两个维度都覆盖：
            局部rect+偏移 / 局部rect / getBoxModel原值 / getBoxModel+偏移
        调用方逐个试、点了再验证，总有一个能命中。
        """
        self.ensure_dom()
        if scroll:
            try:
                self.evaluate(
                    "(function(){ try{ const el=(%s); if(el && el.scrollIntoView){ el.scrollIntoView({block:'center',inline:'center'}); } }catch(e){} })()"
                    % expr, ctx_id)
                # ★ 必须等滚动真正结束：默认 0.35s 常常不够（元素还在移动），
                #   后面读到的 rect 与点击时的位置对不上，点击就落空。
                time.sleep(0.75)
            except Exception:
                pass
        R = self._rect_box(ctx_id, expr)
        if R is None:
            self.refresh_dom()
            time.sleep(0.4)
            R = self._rect_box(ctx_id, expr)
        if R is None:
            return []
        rc = self._box_center(R)
        off = self._abs_correction(ctx_id, expr)

        cands = [(rc[0] + off[0], rc[1] + off[1])]      # 口径 A：局部rect + iframe偏移（理论最准）
        cands.append(rc)                                # 口径 B：局部rect 原值（偏移算错时的兜底）

        G = self._node_box_raw(ctx_id, expr)
        if G:
            gc = self._box_center(G)
            cands.append(gc)                             # 口径 C：getBoxModel 原值（可能已是绝对）
            cands.append((gc[0] + off[0], gc[1] + off[1]))  # 口径 D：getBoxModel + 偏移

        # 去重（保留顺序）
        uniq = []
        for c in cands:
            if not any(abs(c[0] - u[0]) < 1 and abs(c[1] - u[1]) < 1 for u in uniq):
                uniq.append(c)
        return uniq

    def local_point(self, ctx_id, expr, fx=0.5, fy=0.5):
        """取元素内 (fx,fy) 比例处的**页面绝对**坐标（fx=0 最左，0.5 中心）。
        用于避开被 overlay（addon-icon 等）遮住的输入框。
        返回 (abs_x, abs_y, local_x, local_y)。"""
        self.ensure_dom()
        R = self._rect_box(ctx_id, expr)
        if not R:
            return None
        xs = [p[0] for p in R]
        ys = [p[1] for p in R]
        lx = min(xs) + (max(xs) - min(xs)) * fx
        ly = min(ys) + (max(ys) - min(ys)) * fy
        off = self._abs_correction(ctx_id, expr)
        return (lx + off[0], ly + off[1], lx, ly)

    def click_xy(self, x, y):
        for t in ("mouseMoved",):
            self.send("Input.dispatchMouseEvent", type=t, x=x, y=y)
        self.send("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
        time.sleep(0.05)
        self.send("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)
        return (x, y)


def main():
    args = sys.argv[1:]
    text = args[0] if args else ""
    kw = ""
    nth = 0
    sel = None
    exact = True
    i = 1
    while i < len(args):
        if args[i] == "--kw":
            kw = args[i + 1]; i += 2
        elif args[i] == "--nth":
            nth = int(args[i + 1]); i += 2
        elif args[i] == "--sel":
            sel = args[i + 1]; i += 2
        elif args[i] == "--contains":
            exact = False; i += 1
        else:
            i += 1

    p = get_page()
    cdp = CDP(p["webSocketDebuggerUrl"])
    ctxs = cdp.contexts()
    cands = [c for c in ctxs if not kw or kw in c["text"]]
    if not cands:
        cands = ctxs
    offs = cdp.offsets()

    finder = sel or (
        "(() => { const t=%s, exact=%s; const list=[]; for(const e of document.querySelectorAll('*')){ "
        "const s=(e.innerText||'').trim(); if(!s||s.length>60) continue; "
        "if(exact ? s===t : s.includes(t)){ list.push(e); } } "
        "return list.length; })()" % (json.dumps(text), "true" if exact else "false")
    )
    rect_js_tpl = (
        "(() => { const t=%s, exact=%s; const list=[]; for(const e of document.querySelectorAll('*')){ "
        "const s=(e.innerText||'').trim(); if(!s||s.length>60) continue; "
        "if(exact ? s===t : s.includes(t)){ list.push(e); } } "
        "if(!list.length) return null; "
        "list.sort((a,b)=>(a.innerText||'').length-(b.innerText||'').length); "
        "const el=list[%d]; if(!el) return null; el.scrollIntoView({block:'center'}); "
        "const r=el.getBoundingClientRect(); return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height,txt:(el.innerText||'').trim().slice(0,30)}); })()"
    )
    if sel:
        finder = "(() => document.querySelectorAll(%s).length)()" % json.dumps(sel)
        rect_js_tpl = (
            "(() => { const l=document.querySelectorAll(%s); const el=l[%d]; if(!el) return null; "
            "el.scrollIntoView({block:'center'}); const r=el.getBoundingClientRect(); "
            "return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height,txt:((el.innerText||el.value||'')+'').trim().slice(0,30)}); })()"
            % (json.dumps(sel), nth)
        )

    for c in cands:
        try:
            n = cdp.evaluate(finder, c["id"])
        except Exception:
            continue
        if not isinstance(n, int) or n <= nth:
            continue
        rect_js = rect_js_tpl if sel else rect_js_tpl % (json.dumps(text), "true" if exact else "false", nth)
        r = cdp.evaluate(rect_js, c["id"])
        if not r:
            continue
        d = json.loads(r)
        ox, oy = offs.get(c["frameId"], (0, 0))
        px, py = d["x"] + ox, d["y"] + oy
        print(f"ctx={c['id']} frame={c['frameId'][:10]} rect={d} offset=({ox:.0f},{oy:.0f}) -> page=({px:.0f},{py:.0f})")
        res = cdp.click_xy(px, py)
        print("clicked", res)
        return
    print("NOT FOUND:", text, "in ctxs", [c["id"] for c in cands])


if __name__ == "__main__":
    main()
