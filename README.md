# 外卖平台商品上传 折扣活动改价

> 备份时间：2026-10-29 建档，2026-11-07 更名并入淘宝闪购操作（原名「美团外卖商家后台·套餐上架自动化」，目录 meituan-套餐上架-2026-10-29）
> 实战对象：千户边湖北菜（经开万达店）· 美团门店ID `wmqhbh64296` / 闪购（饿了么）shopId `544924353`
> 后台地址：美团 `https://waimaie.meituan.com/#/gw/static_resource/product#/listView`；闪购 `https://melody.shop.ele.me`
> 成果：美团 4 个套餐上架 + 闪购 3 个固定套餐上架 + 双平台折扣/特价活动改价（详见文末「十三、2026-11-07 追加」）

---

## 一、这套方法解决什么

美团商家后台的「新建套餐」是一个**多层 iframe + React 受控表单**的复杂页面，纯人工点选要几十次鼠标操作，
而「分组可选套餐」还要在 4 个规格组里各勾 8/4/2/1 个菜，重复劳动极大。

本流程用 **CDP（Chrome DevTools Protocol）直连 Edge 远程调试端口**，把整个表单填写过程脚本化：

- 用 `DOM.getBoxModel` + **多口径候选坐标**（加不加 iframe 偏移 × 两种取值）+ 点后验证，绕开嵌套 iframe 的偏移换算
- 用 `Input.insertText` + 真实键盘事件填 React 受控输入（合成事件无效）
- 用**左侧分组树导航**勾商品（弹窗内搜索框不触发检索）
- 用**合成事件**点内部 `<span>` 触发 React onClick（组件库的 `<button>` 自身 `pointer-events:none`）
- **唤醒页面 + 推完入场动画**再操作弹窗（后台标签页会冻结 CSS 动画时钟，
  否则弹窗停在第 0 帧，表现为「按钮像被 disabled」）

**边界**：只做「填表 + 提交」，不碰价格策略、库存策略、促销配置。发布后仍需人工在顾客端抽查。

**验收状态**：`run_all.py --no-save` 全流程 8 步跑通（exit=0），
并从归档目录独立复跑一次同样通过 —— 见 `references/screenshots/11~13_*.png`。

---

## 二、目录结构

```
外卖平台商品上传-折扣活动改价/        # 原 meituan-套餐上架-2026-10-29/
├── README.md                       # ★ 本文件：完整可复现操作手册
├── 上架数据模板.json                # ★ 改这里就能上架下一个套餐（规格/价格/文案全在这里）
├── scripts/                        # 全部脚本（按执行顺序，文件名即顺序）
│   ├── run_all.py                  # ★★ 一键跑完整条流水线（--no-save 只填不提交）
│   ├── cfg.py                      # ★ 读取上架数据模板.json（三个搜索路径，找不到用内置默认值）
│   ├── clicktext.py                 # ★ CDP 核心：坐标探测、点击、context 管理、wake/finish_animations
│   ├── form.py                      # ★ 表单层：真实键盘输入、点击、下拉选择、purge_modals
│   ├── pick.py                      # 商品选择弹窗勾选（分组树导航）
│   ├── addgroup.py                  # 规格组构建：add <组名> <类型> <选N> <商品...>
│   ├── build_groups.py              # 批量建组（读模板里的 groups[]）
│   ├── fill_package.py              # 套餐名称 + 套餐类型 + 菜单分组
│   ├── img.py                       # 商品图片区（status / clear）
│   ├── crop_upload.py               # ★「上传图片」裁剪弹窗全流程（自包含幂等）
│   ├── nav_to_list.py               # 导航：回商品列表页
│   ├── nav_new.py                   # 导航：新建商品下拉 → 新建套餐
│   ├── open_form_and_upload.py      # 打开新建套餐表单 + 点开主图上传槽位（诊断用）
│   ├── fill_sell.py                 # 售卖信息：份量/价格/打包费/单位
│   ├── fill_desc.py                 # 套餐描述
│   ├── verify_groups.py             # 规格组内容核对
│   ├── pre_save.py                  # 关闭残留下拉 + 定位保存按钮
│   ├── save.py                      # 点「保存并返回」
│   ├── cancel_draft.py              # 放弃草稿
│   ├── open_group.py                # 打开「一人食套餐」分组并列出商品
│   ├── check_list.py                # 核验上架结果
│   ├── findlist.py                  # 定位商品列表所在 context
│   ├── state.py                     # 页面状态总览
│   ├── shot.py                      # 截图
│   ├── portion2.py                  # 套餐份量下拉选项枚举
│   ├── sellrows.py / sellrowhtml.py # 售卖信息区结构探查
│   ├── cdp_helper.py / mt.py / inspect.py  # 早期通用工具
│   └── _debug/                      # 调试脚本（复盘用，日常不用）
├── references/
│   ├── 踩坑记录.md                   # ★★ 25 个坑的完整复盘（症状→根因→解法）
│   ├── 控件选择器速查.md             # ★★ 所有关键控件的 JS 选择器 + 三层自查顺序
│   ├── logs/                       # ★ 两次全流程运行日志（可复现性证据）
│   │   ├── 2026-10-29_工作区全流程日志.log
│   │   └── 2026-10-29_归档目录独立复跑_全流程日志.log
│   └── screenshots/                 # 13 张过程证据图
└── assets/
    ├── 主图_原图_湖景木桌砂锅.jpg      # 用户指定原图 1672×941
    ├── 主图_上架用_650x650.jpg         # 裁剪成品 650×650（本次实际用的）
    └── 主图_上架用_650x650.png
```

---

## 三、前置条件

| 项 | 值 | 备注 |
|---|---|---|
| 浏览器 | Edge（Chromium 内核） | 必须以**远程调试端口**启动 |
| 启动参数 | `--remote-debugging-port=9222` | 见下方命令 |
| 登录态 | 浏览器里已登录美团商家后台 | 脚本不处理登录 |
| Python | 3.13.14 | 本机：`C:\Users\O\.workbuddy\binaries\python\envs\default\Scripts\python.exe` |
| 依赖 | `websocket-client` 1.9.2 | `pip install websocket-client` |
| 网络 | 直连即可 | 不走代理（美团是国内站） |

**启动带调试端口的 Edge**（先关掉已开的 Edge 窗口，否则端口会占用失败）：

```bash
"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  --remote-debugging-port=9222 \
  "https://waimaie.meituan.com/#/gw/static_resource/product#/listView"
```

验证端口通不通：

```bash
curl http://127.0.0.1:9222/json/list
```

---

## 四、美团套餐模型（动手前必须懂的 4 个概念）

搞混这四点，脚本会点错地方：

### 1. 入口是「新建商品」下拉的**第 4 项**

`商品管理 → 商品列表 → 右上角「＋ 新建商品」` 会弹出 4 项：

| 序号 | 菜单项 | 说明 |
|---|---|---|
| 1 | AI智能新建 | AI 帮你填 |
| 2 | 手动新建 | **单品**，不是套餐 |
| 3 | 复制新建 | 复制已有商品 |
| 4 | **新建套餐** | 副标题「搭配单品组成套餐」← **要选这个** |

> 第 4 项经常被截图裁掉/被误认成「手动新建」。认准副标题「搭配单品组成套餐」。

### 2. 套餐类型只有两种

- **固定搭配套餐** —— 一篮子菜固定组合（对应经典的"XX套餐"）
- **分组可选套餐** —— 多个规格组，每组 M选N（顾客在每组里各挑一个）

本次「楚味一人食·自选搭配」是**分组可选套餐**。

> ⚠️ radio 的 `checked` **HTML 属性不可信**（React 只改 DOM property）。
> 判断当前选中必须读 `.checked` 属性：
> `document.querySelectorAll('input.roo-radio-input')` → 逐个读 `r.checked`

### 3. 「分组可选套餐」的结构

```
分组（名称 maxlength=10）      [组类型: 可选商品/固定商品]   本组商品 8选   [选N 输入框]
  └─ 商品行：商品名 | 价格 | 份数 | 必选/推荐 | 加价 | 操作(移除)
```

- **组类型**下拉：`可选商品`（可勾选多选）或 `固定商品`（只能一个，且不显示"选N"）
- **选N 输入框**：在分组头右侧，`本组商品 8选` 文字旁边
- 「本组商品 8选」= 该组有 8 个候选，顾客选 1 个

### 4. 套餐里的菜**必须来自菜单已有商品**

规格组里能勾选的，都是**该门店菜单里已存在的单品**。想加新菜必须先建单品。
本次「加一份香米」在菜单里搜不到，改用「江汉平原香米」（¥3）承担。

---

## 五、完整操作流程

> 以下命令都在 `scripts/` 目录下执行。
> `PY` = `C:/Users/O/.workbuddy/binaries/python/envs/default/Scripts/python.exe`

### 步骤 0 ★★ 一键跑（推荐）

全部数据来自 `上架数据模板.json`，一条命令跑完 8 步：

```bash
$PY run_all.py --no-save     # ★ 演练：填完所有字段但不提交（推荐先跑这个）
$PY run_all.py               # 正式：真的保存并上架
```

`--no-save` 跑完后表单停在待提交状态，可以用 `cancel_draft.py` 或浏览器后退放弃。
其它开关：

| 开关 | 作用 |
|---|---|
| `--no-save` | 只填表不提交 |
| `--skip-groups` | 跳过规格组构建（组已存在时） |
| `--skip-image` | 跳过主图上传 |

> ⚠️ **默认模式（不带 `--no-save`）会真的保存并上架。**

### 步骤 0 · 手动分步（等价于 `run_all.py` 内部做的事）

```bash
$PY nav_to_list.py       # 回商品列表页
$PY nav_new.py           # 点「新建商品」下拉 → 点第 4 项「新建套餐」
$PY fill_package.py      # 套餐名称 + 套餐类型 + 菜单分组
$PY build_groups.py      # 按模板建 4 个规格组（含类型 / 选N / 勾商品）
$PY addgroup.py show     # 核对规格组
$PY crop_upload.py "D:/工作/千湖边湖北菜/经开店套餐/上架用650/楚味一人食·自选搭配.jpg"
$PY img.py status        # 确认主图计数 = 1/5
$PY fill_sell.py         # 售卖信息
$PY fill_desc.py         # 套餐描述
$PY pre_save.py && $PY save.py   # 保存并返回
```

下面 步骤 1 ~ 11 是每一环的细节说明。

### 步骤 1 · 填套餐名称（弹窗内输入框）

```bash
$PY fill_package.py       # 名称 + 套餐类型 + 菜单分组 三件事一起做
```

底层等价于：

```bash
$PY -c "
import sys; sys.path.insert(0,'.')
from form import cdp_connect, find_ctx, type_into
cdp=cdp_connect()
c=find_ctx(cdp,'套餐名称',probe=\"(()=>document.querySelector('input.groupName_RJkgVI')?'YES':'')()\")
print(type_into(cdp,c['id'],\"document.querySelector('input.correctNameTooltip_j9rW4a')\",'楚味一人食·自选搭配'))
"
```

名称规范：`特色卖点+口味/做法+食材+品类名`，≤30 字。

### 步骤 2 · 切套餐类型为「分组可选套餐」

radio 的 `value="2"`。点 `span.custom-radio-label` 里文字为「分组可选套餐」的那个。
（`fill_package.py` 已包含这一步。）

### 步骤 3 · 建 4 个规格组（**最耗时的一步**）

```bash
# 批量（读 上架数据模板.json 的 groups[]）
$PY build_groups.py

# 或逐个手动（addgroup.py 的新签名：组名 / 组类型 / 选N / 商品列表）
$PY addgroup.py add "荤菜200ml二选一" "可选商品" 1 "荆味鱼香肉丝" "糖醋里脊" "土家酸辣鸡杂" "荆州小炒肉" "爆炒猪肝" "沔阳粉蒸肉" "洪湖农家糍粑鱼" "罗田板栗烧鸡"
$PY addgroup.py add "素菜300ml四选一" "可选商品" 1 "江汉平原时令蔬菜" "荆西酸辣土豆丝" "砂锅花菜" "砂锅扁豆"
$PY addgroup.py add "加料二选一"     "可选商品" 1 "荆楚农家水蒸蛋" "江汉平原香米"
$PY addgroup.py add "固定香米"       "固定商品" -  "江汉平原香米"
```

`addgroup.py add` 内部流程（一站式）：
`找/建组` → `填组名` → `设组类型` → `开商品弹窗按分组树勾选` → `点确定` → `设选N`。

- 组类型：可选商品 / **固定商品**（固定商品不显示「选N」，所以选N 传 `-`）
- 组名 `maxlength=10`，超了会被截断。「荤菜200ml二选一」正好 10 字。
- **勾商品靠左侧分组树导航，不靠搜索框**（弹窗内搜索框不触发检索）。

### 步骤 4 · 核对规格组

```bash
$PY addgroup.py show        # 或 verify_groups.py
```

输出每个组的：名称 / 类型 / `本组商品 N选` / 选N / 已勾商品列表。**提交前必须核对。**

> 组类型的判定读的是 **React fiber**（`memoizedProps.groupType`），
> 不是 `input.value` —— 后者有显示滞后，会误判。

### 步骤 5 · 设菜单分组

下拉选「一人食套餐」（或目标分组）。**没有的分组要先在左侧「+ 新建分组」建。**
（`fill_package.py` 已包含这一步。）

### 步骤 6 · 传主图

```bash
# crop_upload.py 是自包含的：清旧图 → 开裁剪弹窗 → 本地上传 → 保存 → 校验计数
$PY crop_upload.py "D:/工作/千湖边湖北菜/经开店套餐/上架用650/楚味一人食·自选搭配.jpg"

$PY img.py status        # 确认主图计数 = 1/5
```

**诊断用**（想单独看弹窗长什么样时）：

```bash
$PY open_form_and_upload.py   # 只点开主图上传槽位，不上传
```

图片规格：≥600×450px，≤5MB。上传位最多 5 张。

> ★ 这一步踩的坑最多（详见 `references/踩坑记录.md` 坑 1/3/7/12/20）：
> 后台标签页会冻结 CSS 动画 → 弹窗卡在入场第 0 帧 → 按钮 `pointer-events:none` 看起来像 disabled。
> `cdp_connect()` 已经内置 `wake()` 自动规避。

### 步骤 7 · 填售卖信息

```bash
$PY fill_sell.py
```

会填：套餐份量=`1人份`、套餐价格=`29.9`、打包费=`2`、单位=`每1份`。
脚本**先读当前值，已填的跳过**，可重复跑。

> ⚠️ 价格输入框中心被「套餐内单品原价总和」提示条盖住，**必须点最左侧**（脚本里 `fx=0.08`），
> 否则点击落在遮罩上，文字全丢。

### 步骤 8 · 填套餐描述

```bash
$PY fill_desc.py
```

上限 200 字。本次的文案在 `上架数据模板.json` 的 `description` 字段。

### 步骤 9 · 高级信息（保持默认）

`可售时间 = 全时段售卖`（默认即可）。`店内招牌`、`单点不送` 保持关闭。

### 步骤 10 · 保存

```bash
$PY pre_save.py      # 关闭残留下拉 + 定位保存按钮（确认页面底部）
$PY save.py          # 点「保存并返回」→ 截图核验
```

成功后 toast 出现**「保存成功」**，页面跳回商品列表。

### 步骤 11 · 核验

```bash
$PY open_group.py    # 打开「一人食套餐」分组，列出商品 + 截图
```

看到套餐名、外送价 ¥29.9、主图正确、操作栏显示「下架」（= 当前在售），即成功。

---

## 六、放弃草稿（不慎开错时的退出路径）

新建套餐表单的**底部按钮（保存并返回/取消）在表单尚未渲染完整时可能不存在**（短表单实测过：DOM 里根本没有这两个节点）。
可靠退出方式：

```bash
$PY cancel_draft.py     # 找「取消」按钮（长表单可用）
```

或直接后退（实测可靠，草稿自动丢弃）：

```bash
$PY -c "
import sys; sys.path.insert(0,'.')
from form import cdp_connect
cdp=cdp_connect()
for x in cdp.contexts():
    if '商家首页' in x['text']:
        cdp.evaluate('(()=>{history.back(); return 1;})()', x['id']); break
"
```

> 实测：开草稿 → 传图 → 后退 → 侧栏分组数不变，未产生多余商品。

---

## 七、本次上架数据（模板在 `上架数据模板.json`）

| 字段 | 值 |
|---|---|
| 套餐名称 | 楚味一人食·自选搭配 |
| 套餐类型 | 分组可选套餐（value=2） |
| 菜单分组 | 一人食套餐 |
| 套餐份量 | 1人份 |
| 套餐价格 | ¥29.9 |
| 库存 | 10000 / 10000 / 自动补足 |
| 打包费 | ¥2 / 每1份 |
| 高级信息 | 全时段售卖 |
| 主图 | 用户指定图，裁剪 650×650 |
| 套餐描述 | 157 字 |

**规格组**

| 组名 | 类型 | 选N | 候选商品（单价） |
|---|---|---|---|
| 荤菜200ml二选一 | 可选商品 | 1 | 荆味鱼香肉丝29 / 糖醋里脊26 / 土家酸辣鸡杂38 / 荆州小炒肉39 / 爆炒猪肝39 / 沔阳粉蒸肉45 / 洪湖农家糍粑鱼39 / 罗田板栗烧鸡58 |
| 素菜300ml四选一 | 可选商品 | 1 | 江汉平原时令蔬菜19 / 荆西酸辣土豆丝19 / 砂锅花菜23 / 砂锅扁豆28 |
| 加料二选一 | 可选商品 | 1 | 荆楚农家水蒸蛋6.6 / 江汉平原香米3 |
| 固定香米 | **固定商品** | — | 江汉平原香米3 ×1份 |

**上架结果**（商品列表实拍，见 `references/screenshots/05_列表已上架.png`）

| 商品 | 外送价 | 原价 | 折扣 | 库存 | 自取价 | 状态 |
|---|---|---|---|---|---|---|
| **楚味一人食·自选搭配** | **¥29.9** | — | — | 10000 | 未录入 | 在售 |
| 楚味一人食·糍粑鱼套餐 | ¥29.9 | ¥61 | 4.9折 | 10000 | 未录入 | 在售 |
| 楚味一人食·糖醋里脊套餐 | ¥25.9 | ¥48 | 5.4折 | 10000 | 未录入 | 在售 |
| 楚味一人食·罗田板栗烧鸡套餐 | ¥26.9 | ¥60 | 4.48折 | 10000 | 未录入 | 在售 |

---

## 八、上架后必须做的两件事

### 1. 顾客端抽查（后台上架 ≠ 顾客端可见）

美团套餐上架后要等平台同步 + 审核，通常几分钟到几小时。
**只有归在「一人食套餐」这类菜单分组下的商品，才会出现在顾客端对应入口。**
顾客端搜不到时，先查：① 是不是分组归属错了 ② 是否还在同步中 ③ 是不是被平台下架。

### 2. 自取价

本次 4 个套餐的自取价都是「未录入」—— **和用户手工建的那 3 个保持一致**，属于本店现状，不是本次的遗漏。
如果店里要支持自取/到店取餐，需要单独在列表页「批量录入自取价」补上。

---

## 九、踩坑清单（速览，详见 `references/踩坑记录.md`）

按「症状 → 根因 → 解法」组织，共 25 条。带 ★★★ 的是最难定位的。

### A. 动画时钟 / 层级

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| ★★★ 1 | 弹窗明明开了，按钮 `pointer-events:none`、rect 全 0，像是 disabled | 标签页在后台 → Chrome **冻结 CSS 动画时钟** → 弹窗停在入场第 0 帧（遮罩 opacity=0、dialog `scale(0)`） | `cdp.wake()`（`Emulation.setFocusEmulationEnabled` + `Page.bringToFront`）+ `finish_animations()`；已内置进 `cdp_connect()` |
| ★★ 2 | 弹窗关了，后续所有坐标点击失效 | roo 离场动画结束后**遮罩节点不删除**（opacity=0 但铺满全屏） | `form.purge_modals()` |
| ★★ 3 | purge 脚本删不掉该删的遮罩 | 白名单按文本豁免，而离场残留 innerText 恰好命中白名单 | 按 **class 含 `motion-leave`** 判断（leave=该删，appear=要留） |
| ★ 4 | 下拉浮层挂在「+ 添加商品」上方，肉眼可见 | `roo-popup-motion-leave` 的 opacity 还是 1 | 同上，`purge_modals` 一并清 |

### B. CDP 协议层

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| ★★★ 5 | 弹窗开了，`contexts()` 里却找不到它 | `contexts()` 里 `self.events = []` 清空了事件 —— 而 CDP 事件**只在 `send()` 等待响应期间被读取**，新建 iframe 的 `executionContextCreated` 被永久丢弃 | 不清空 events，改为**裁剪**（>600 保留 400 条） |
| ★★★ 6 | 某段 JS 永远返回空，但逻辑人工跑是对的 | `Runtime.evaluate` 的 JS 异常/语法错误**被静默吞掉**返回 None，一律被当成「元素不存在」 | `evaluate(strict=True)` 抛 `JSError`；所有取列表的调用都开 strict |
| ★★ 7 | `Object reference chain is too long` | `returnByValue=True` 不能返回 DOM 元素 | JS 一律返回字符串 / 布尔 / 普通对象 |
| ★★ 8 | `setFileInputFiles` 成功但 input 立刻找不到 | 组件读走文件后 React 重渲染，input 被移除 —— **这是正常的** | 用「裁剪画布 `naturalWidth>0`」判定成功 |

### C. React / DOM 事件模型

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| ★★★ 9 | 对 `<button>` 派发合成事件**完全没反应** | roo 的 button 自身 `pointer-events:none`，真正可点的是内部 `<span>` | 点内部 `span`（事件冒泡到 button 触发 onClick） |
| ★★ 10 | `input.value = x` 后 React 没反应 | 受控 input 的 value tracker 被污染 | `focus()` + `select()` + `Input.insertText` |
| ★★ 11 | 数字被填进了别的框（组名变成「加料二选一1」） | `Input.insertText` 只看**当前焦点**，定位失败后仍继续插字 | 定位失败**立即中止**，绝不 insertText |
| ★ 12 | 组类型明明设了「固定商品」，读出来还是「可选商品」 | `input.value` 显示滞后 | 读 **React fiber** 的 `memoizedProps.groupType`（0=固定 / 1=可选） |
| ★★ 13 | hover 出删除按钮后点了 8 次，一张没删 | hover 弹出的 `roo-tooltip` 正好盖住按钮，`elementFromPoint` 命中的是 tooltip | 用**合成事件**点 closeIcon（不走 hit-test） |

### D. iframe / 坐标

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| ★★★ 14 | 弹窗里可能同时挂着多个 `selectProduct` iframe | React 重建 iframe 时旧的**不销毁** | 挑**分组树条目数最多**的那个；判据要够严（表单里也有 `span.custom-checkbox`） |
| ★★ 15 | `Cannot find context with specified id` | iframe 被 React 重建，contextId 失效 | 所有弹窗操作走 `pick.Modal` 封装，操作前 `refresh()` |
| ★ 16 | 坐标算出来点不中 | `getBoundingClientRect` 是视口坐标、`getBoxModel` 是文档坐标 | 输出 **4 种口径候选**，逐个试、点了再验证 |

### E. 业务逻辑层

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| ★★★ 17 | 弹窗内搜索框打字/回车**完全没反应** | 商品选择弹窗的搜索框不触发检索 | 改走**左侧分组树导航**（`pick.find_groups_for` + `pick.pick_auto`） |
| ★★ 18 | 「清空」后弹窗行为异常 | 会弹二次确认，按钮文字是「确 定」（半角空格）；且新开弹窗本来就是 0 | `/^(确\s*定|确定)$/` 比较；只在已选非空时才清 |
| ★★ 19 | 视口外元素（如组类型下拉）点了没反应 | 视口外元素不参与命中测试 | 先 `scrollIntoView` 并**等 0.7s** 再派发 |
| ★ 20 | 菜单分组选完浮层一直挂着 | 下拉离场残留 | `purge_modals` |
| ★ 21 | 找不到「新建套餐」入口 | 在下拉**第 4 项**；且 `<button>` 要点内部 span | `nav_new.py` + `js_click` |
| ★ 22 | 出现「门店内存在同名商品」 | 是**提示**不是拦截 | 脚本能识别，别误判成失败 |
| ★ 23 | 保存后分组数还是 (0) | 列表页统计不实时刷新 | 以 toast + 刷新后列表为准 |
| ★ 24 | 短表单时找不到「保存并返回」 | 底部按钮未渲染 | 正常流程填完会出现；放弃草稿用后退 |
| ★ 25 | `label[for=xxx]` 查不到 input | for 是 label 关联，input 没有 id | 结构定位 `label[for=x].closest('.form-group').querySelector(...)` |

### F. 环境侧

| # | 现象 | 解法 |
|---|---|---|
| ★ 26 | Bash 里 `ls`/`head` 全部 command not found | PortableGit 的 PATH 默认是空的，命令前先 `export PATH=...` |
| ★ 27 | npm 生成的 `.cmd` shim 挂死 | 最后一行 `title%COMSPEC%` 在无控制台环境会卡住；直接用 `node <入口文件>` |
| ★ 28 | 桌面路径不对 | `C:\Users\O\Desktop` 是残留壳子，真实桌面在 `E:\O1776\OneDrive\Desktop` |

---

## 九之二、一句话排查心法

> **DOM 里读得到 ≠ 点得动；点得动 ≠ 业务生效。**

分层取证，别猜选择器：

```
1. 元素不在？   → wake() + finish_animations()，再看 offsetWidth
                   → evaluate(strict=True) 拿真实 JS 错误
2. 在但点不动？ → 是 <button>？改点内部 span
                   → 在视口外？先 scrollIntoView 等 0.7s
                   → 有残留遮罩？purge_modals() 再试
                   → 在另一个 context？逐个查 contexts()
3. 点了没生效？ → 读 React fiber（不是 input.value）
                   → contextId 失效？refresh 弹窗 context
```

---

## 十、适用边界

**能做的**：新建套餐表单的字段填写、规格组构建、图片上传、提交保存、列表核验。

**没做的（需人工）**：
- 登录 / 验证码 / 短信验证
- 单品（菜品）的创建与定价
- 促销、优惠券、满减配置
- 批量改价、批量传图（后台有「批量新建/传图/修改」入口，未自动化）
- 顾客端效果验证

**风险提示**：
- 脚本直接操作线上后台，**执行前请确认当前表单内容**（本流程会真实覆盖字段并提交）
- `run_all.py` **默认会真的保存并上架**；演练必须加 `--no-save`
- `addgroup.py add` 会**新建**一个组并立即勾选，重复跑会多建组 —— 用 `build_groups.py`（读模板）避免
- 已上架的套餐用 `编辑` 进表单修改，`保存并返回` 会覆盖线上数据
- `crop_upload.py` 会**先清掉已有主图再传**，避免重复上传变成多张（传同一张请加 `--keep`）

---

## 十一、下一套套餐怎么上架

1. 复制 `上架数据模板.json`，改这几处：
   - `package.name` / `package.type` / `package.menu_group`
   - `package.main_image`（本机绝对路径）
   - `package.description`（≤200 字）
   - `sell.*`（份量 / 价格 / 库存 / 打包费 / 单位 / 时段）
   - `groups[]`（组名 ≤10 字、类型、pick_n、items 商品名必须**与菜单里完全一致**）
2. 确认这些菜**已经在门店菜单里**（规格组只能勾已存在的单品）
3. 跑 `$PY run_all.py --no-save`，看日志里「步骤3 规格组核对」是否全对
4. 核对无误后 `$PY run_all.py` 真正提交
5. `$PY open_group.py` 核验列表

> 商品名要与菜单里**一字不差**（脚本靠精确匹配找商品）。
> 找不到时先在后台确认全名，再改模板。

---

## 十二、验收记录（可复现性证据）

同一份脚本、同一份模板，**两个不同位置各跑一遍**，结果完全一致：

| # | 运行位置 | 命令 | 耗时 | 结果 |
|---|---|---|---|---|
| 1 | 工作区 `C:\Users\O\WorkBuddy\2026-10-29-14-10-32` | `run_all.py --no-save` | 约 5 min | **exit=0**，8 步全过 |
| 2 | 归档 `…\外卖平台商品上传-折扣活动改价\scripts`（更名前 `meituan-套餐上架-2026-10-29`） | `run_all.py --no-save` | 3 min 23 s | **exit=0**，8 步全过 |

两次的核对输出逐字相同：

```
[0] 名称='荤菜200ml二选一' 类型='可选商品' '本组商品 8选' 选N=1 商品=[8 个]
[1] 名称='素菜300ml四选一' 类型='可选商品' '本组商品 4选' 选N=1 商品=[4 个]
[2] 名称='加料二选一'     类型='可选商品' '本组商品 2选' 选N=1 商品=[2 个]
[3] 名称='固定香米'       类型='固定商品' None       选N=None 商品=['江汉平原香米']

主图：0 -> 1 /5
售卖：份量=1人份  价格=29.9  库存=10000/10000  打包费=2 每1份
描述：157 字
```

日志原文见 `references/logs/`。

> 第 2 次（从归档目录独立跑）是**归档可信度的硬证据** ——
> 证明归档里的脚本 + 模板不依赖工作区里的任何残留文件。

---

## 十三、2026-11-07 追加：淘宝闪购上传 3 套餐 + 双平台折扣活动改价

本节把操作范围从「美团单平台」扩展到「美团 + 淘宝闪购（饿了么）双平台」，并新增「折扣活动改价」链路。详细过程记录见工作区日志 `.workbuddy/memory/2026-10-29.md`（本主题主记录）与 `2026-11-07.md`。

### 13.1 闪购上传 3 个固定套餐（经开区万达·千户边店，shopId 544924353）

| 套餐 | 构成（闪购侧单品价） | 定价（=加总） |
|---|---|---|
| 糍粑鱼套餐 | 洪湖农家糍粑鱼¥39 + 荆西酸辣土豆丝¥19 + 江汉平原香米¥3 | ¥61 |
| 糖醋里脊套餐 | 糖醋里脊¥28 + 江汉平原时令蔬菜¥19 + 江汉平原香米¥3 | ¥50 |
| 鱼香肉丝套餐 | 荆味鱼香肉丝¥29 + 砂锅扁豆¥28 + 江汉平原香米¥3 | ¥60 |

入口：`melody.shop.ele.me` → 商品管理 →「新建套餐」，表单在 `napos-goods-pc.faas.ele.me/package` iframe。脚本 `%TEMP%/ele/packlib.py` + `ele_create_pack.py`。核验：「经典套餐」分组 8→11、全部 tab 55→58。

闪购侧关键坑（与美团完全不同的组件体系，antd + ngoods）：
1. 「添加商品」是 div（index_addBtn）不是 button；首点弹「套餐类型说明」引导，点「知道了」后要**再点一次**。
2. 选品弹窗不是 `.ant-modal`，按「选择店内商品」文本向上找含「取 消」的容器。
3. 搜索框 `input.ngoods-input`：native setter 写值 + input 事件 + Enter 触发；勾选按行文本 `startsWith(菜名)`（防误选同名套餐行）。
4. ⚠️ 最大坑：`input.ant-input-number-input` 前几个是**份数框**不是价格框。套餐价格=当前为空值那个 index，打包费=最后一个（留空报「不得为空」）。
5. 平台给新套餐自动加「楚味一人食·」前缀；封面自动智能拼图无需传图。
6. 校验规则：套餐价不得超过店内全部商品原价总和——按加总定价正好压线合法。

### 13.2 闪购「商品活动·特价」= 美团折后价 + 3

路径：营销中心 → marketing-center/single「商品活动」卡 `div.create-btn` → iframe `napos-activity-pc.faas.ele.me`：
- step1 基础信息默认即合规（全部顾客/优惠类型=特价 SKU_LOCK_PRICE/外卖/全天）；下一步弹《营销智推服务协议》选「**不开启**」。
- step2 `chooseGoods?benefitType=SKU_LOCK_PRICE`：商品直接内嵌列表，左分组「经典套餐」→ 勾行 →「确 定」→ 三商品特价不同，点「跳过，去单个设置」。
- 每行「创建规则」drawer：特价输入框 = `input.ant-input` 且 placeholder 含「表示特价」→ native setter 填值 →「确 定」。
-「提交活动」→ URL 到 `createSuccess` 即成功；「匿名问卷」modal 点「残忍拒绝」。
- 验收只看活动侧：商品管理页**只显示原价**，别拿它当折扣验收依据。

### 13.3 双平台折扣价下调（11-07 16:4x）

扰动指令「美团 -3、闪购 -5」，改后闪购比美团高 1 元：

| 套餐 | 美团折后价 | 闪购特价 |
|---|---|---|
| 糍粑鱼 | 35.9 → **32.9** | 38.9 → **33.9** |
| 糖醋里脊 | 29.9 → **26.9** | 32.9 → **27.9** |
| 鱼香肉丝 | 31.9 → **28.9** | 34.9 → **29.9** |

**美团改价**：活动中心·自营销活动（`wmact/pc` iframe）→「折扣商品」→ `myList.html?actType=17` → 行内「修改」进 `createEditAct.html?operateType=edit&actId=…` → `input[type=number][placeholder=输入折后价]` native setter 填值 →「确定修改」。
**坑**：操作列「详情/修改/删除」是独立列容器、与商品行不同 `tr` —— 必须按商品名叶子元素的 `getBoundingClientRect().y` 找最近「修改」链接；点「修改」后 iframe context 重建，旧 cid 立刻失效，重扫 frame + `evaluate("'ok'", cid)` 探活轮询。

**闪购改价**：我的活动 `my-food-activity`（melody-activity-index，status=ACTIVATED）→「查看详情」→ `singleShopDetail?activityId=` →「修改规则」→ SPA 进 `commodityActivities?activityId=…`（人群/类型/日期锁定）→「表示特价」input 填值 →「提交活动」→ 回 singleShopDetail 即成功。
**坑**：每次点击后 frame URL 变、context 重建可达 3~6s，轮询提到 40 次；JS 表达式必须带尾部 `()`（漏了就是 IIFE 没执行，点了没反应）。

**通用配方（双平台都适用）**：
```js
const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
mod.focus(); setter.call(mod, '26.9');
mod.dispatchEvent(new Event('input',  { bubbles: true }));
mod.dispatchEvent(new Event('change', { bubbles: true }));
mod.dispatchEvent(new Event('blur',   { bubbles: true }));
```
**铁律**：改价只动活动/折扣价，商品原价一律不碰。
