# -*- coding: utf-8 -*-
"""打开弹窗后立刻检查 contexts() 里能不能看到它。"""
import sys, time
sys.path.insert(0, '.')
from form import cdp_connect
from pick import Modal, modal_ctx, group_names, list_names
from addgroup import grp_additem_expr, form_ctx

cdp = cdp_connect()
form = form_ctx(cdp)
cid = form['id']
print('form ctx', cid)

expr = grp_additem_expr(0)
print('js_click:', cdp.js_click(cid, expr))
time.sleep(3.0)

print()
print('--- contexts() ---')
for x in cdp.contexts():
    try:
        u = cdp.evaluate('location.href', x['id'])
    except Exception as e:
        u = '(err)'
    print('  ctx %s | %s' % (x['id'], str(u)[:80]))

print()
m = modal_ctx(cdp, tries=3)
print('modal_ctx:', m['id'] if m else None)
md = Modal(cdp)
print('Modal.cid:', md.cid, 'alive:', md.alive())
if md.cid:
    print('groups:', group_names(cdp, md.cid))
    print('names :', list_names(cdp, md.cid))
