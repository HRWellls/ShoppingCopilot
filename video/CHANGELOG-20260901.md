# Shopping Copilot 录制工作台修改日志

**日期**：2026-09-01
**文件**：`video/index.html`、`video/verify.ps1`、`video/export-assets.ps1`、`demo/06-视频录制布局与路演画面设计.md`
**备份**：`video/index.html.bak-20260901-0500`（修改前的原始版本）

> Recording workbench change log
> Date: 2026-09-01. Files changed: `video/index.html`, `video/verify.ps1`, `video/export-assets.ps1`, and the frame runbook. A pre-change backup is kept at `video/index.html.bak-20260901-0500`.

---

## 一、这轮改了什么

本轮把工作台从"技术自检流水线"改成"场景级产品叙事"，并对照 `src/` 真实代码复核了画面上每个技术标签。

> This round turns the workbench from a technical self-check pipeline into scenario-level product storytelling, and checks every technical label on screen against the real code in `src/`.

修改分六块：帧结构、旁白、缺失的叙事节点、技术准确性、画面减法、视觉设计。

> The changes fall into six areas: frame structure, narration, missing narrative nodes, technical accuracy, removing on-screen clutter, and visual design.

---

## 二、帧结构：S02 从 5 帧扩到 6 帧

脚本段落 2 讲的技术架构（双轨、三项机制、产品闭环），在工作台里原本没有画面出口。S02 从 5 帧扩到 6 帧补上这些内容。

> The technical architecture described in script section 2 (two tracks, three mechanisms, the product loop) had no place on screen. S02 grows from 5 frames to 6 to make room for it.

| 帧 | 时间 | 内容 | Frame | Time | Content |
|---|---|---|---|---|---|
| F01 | 0:30-0:38 | 静态 query 与真实购物行为的对比 | F01 | 0:30-0:38 | Static query vs. real shopping behaviour |
| F02 | 0:38-0:46 | 核心洞察：意图是变化的状态 | F02 | 0:38-0:46 | Insight: intent is a changing state |
| F03 | 0:46-0:54 | 双轨：Buying 与 Browsing | F03 | 0:46-0:54 | Two tracks: Buying and Browsing |
| F04 | 0:54-1:02 | 三项机制 | F04 | 0:54-1:02 | Three mechanisms |
| F05 | 1:02-1:11 | 六步产品闭环 | F05 | 1:02-1:11 | The six-step product loop |
| F06 | 1:11-1:20 | 能力覆盖 80/20 | F06 | 1:11-1:20 | Capability coverage, 80/20 |

总帧数从 53 变为 54，总时长保持 295 秒（4:55）。

> Frame count goes from 53 to 54. Total runtime stays at 295 seconds (4:55).

---

## 三、旁白：54 帧全部重写

按 v7 脚本重写，语速控制在 2.6 词/秒以内（实测 1.00 到 2.50）。

> All 54 narrations are rewritten from the v7 script, kept under 2.6 words per second (measured range 1.00 to 2.50).

叙事结构上做了三件事：

> Three things changed in the narrative structure:

**开头结论先行。** 第一屏就给出定义、承诺和难点，不从背景铺陈开始。

> **The opening leads with the conclusion.** The first screen gives the definition, the promise, and the hard part, rather than starting with background.

**每帧讲一个价值点。** 每个场景的结果帧都回答"这对用户意味着什么"。

> **Every frame carries one value point.** The result frame of each scenario answers "what this means for the user".

**结尾做业务升维。** 从用户价值（省事、敢信）升到平台假设（效率、转化、放弃率），再到 roadmap。

> **The ending lifts to the business level.** It moves from user value (less effort, more trust) to platform hypotheses (efficiency, conversion, abandonment) and then to the roadmap.

---

## 四、技术准确性：对照代码纠正的 7 处

复核了 `src/` 下的 `events.py`、`rules.py`、`router.py`、`resolver.py`、`schema.py`、`models.py`、`overrides.py`、`policy.py`、`hybrid.py`、`core.py`、`config.py`。以下 7 处画面标签与代码不符，已修正。

> I reviewed `events.py`, `rules.py`, `router.py`, `resolver.py`, `schema.py`, `models.py`, `overrides.py`, `policy.py`, `hybrid.py`, `core.py` and `config.py` under `src/`. Seven on-screen labels did not match the code and have been corrected.

### 1. FSM 状态名

代码只认 5 种事件，状态名按技术文档的 9 状态。画面原来用的 `WAITING`、`RESPOND`、`DONE` 两头都不沾，已改成技术文档的状态名。

> The code recognises only five event kinds, and state names follow the nine states in the technical document. The old labels `WAITING`, `RESPOND` and `DONE` matched neither, and now use the document's state names.

修正后：`START → UNDERSTAND → RETRIEVE → ASSESS → CLARIFY / RELAX → RECOMMEND → LIMIT_RECOMMEND`

> After the fix: `START → UNDERSTAND → RETRIEVE → ASSESS → CLARIFY / RELAX → RECOMMEND → LIMIT_RECOMMEND`

### 2. 事件名

代码里 `EVENT_KINDS` 只允许 5 种：`override`、`clear`、`negation`、`no_preference`、`intent_switch`，不在集合内会直接报错。画面原来写的 `specific_request`、`add preference`、`explore scene` 等全部是杜撰的，已删除。只保留真实存在的 `no_preference`。

> `EVENT_KINDS` in the code allows only five kinds: `override`, `clear`, `negation`, `no_preference`, `intent_switch`. Anything else raises an error. The old labels such as `specific_request`, `add preference` and `explore scene` were invented and are removed. Only the real `no_preference` remains.

### 3. 意图来源字段

代码里 `source` 的真实取值是 `rule`、`stable`、`continue`、`model`、`event`。画面原来写的 `strong rule`、`stable rule` 是把来源和原因混在一起编的，已改成 `rule` 和 `stable`。

> The real values of `source` in the code are `rule`, `stable`, `continue`, `model` and `event`. The old labels `strong rule` and `stable rule` mixed source with reason and were invented; they are now `rule` and `stable`.

### 4. 删除 fit 槽位

代码允许的槽位共 10 个：价格上下限、品牌、颜色、材质、品类、尺码、场合、风格、用途。没有"合身度（fit）"这个槽位。已把"less fitted"并入 `style`。

> The code allows ten slots: price min and max, brand, colour, material, category, size, occasion, style, use case. There is no `fit` slot. "less fitted" now folds into `style`.

### 5. 执行链去掉 lexical

d4 配置下 `optimized_single_pass_enabled=true`，会让 lexical 通道直接返回空。真实路径是硬过滤到合法子集，再属性检索，再属性重排。画面原来写的 "lexical retrieval" 在 d4 下并不执行，已改。

> Under the d4 config, `optimized_single_pass_enabled=true` makes the lexical channel return empty. The real path filters to a legal subset, then retrieves by attribute, then reranks. The old label "lexical retrieval" does not run under d4 and has been changed.

### 6. 澄清阈值

配置里的 `clarify_count_threshold=100` 在代码中从未被引用。真实触发条件是候选数超过 10。已改。

> `clarify_count_threshold=100` in the config is never referenced in the code. The real trigger is more than ten candidates. Corrected.

### 7. 轮次保护提前到第 4 轮

脚本一直讲第 8 轮和第 10 轮保护。代码里 `recommendation_with_clarification_enabled` 打开时，第 4 轮起就不再追问。已按真实行为改为第 4 轮。

> The script talks about turn 8 and turn 10 protection. In the code, when `recommendation_with_clarification_enabled` is on, questioning stops from turn 4. Changed to match the real behaviour.

---

## 五、画面减法

用户反馈：不要在页面上堆技术说明，这是 5 分钟的介绍，哪怕技术上不严谨也没关系，要聚焦 storytelling。据此做了 5 处减法。

> Feedback received: stop piling technical notes onto the screens. This is a five-minute introduction; technical looseness is acceptable and the focus should be storytelling. Five removals follow from this.

1. 去掉 Intent 帧的"State change"技术标签栏。
2. 证据标签去掉技术前缀（`buy_action: need` 改为 `need`）。
3. 执行步骤从 4 到 5 步压到 3 步。
4. 价值链（4 步链）改为一句价值点，标签为 "Why it matters"。
5. 配置披露条从 S02 每帧显示，改为只在收尾帧显示一次。

> 1. Removed the "State change" technical label from the Intent frame.
> 2. Stripped technical prefixes from evidence labels (`buy_action: need` becomes `need`).
> 3. Compressed execution steps from four or five down to three.
> 4. Replaced the four-step value chain with a single value line labelled "Why it matters".
> 5. The configuration strip now appears once on the closing frame instead of on every S02 frame.

---

## 六、视觉设计

### 方向

暖中性底 + 深青蓝主色 + 衬线标题。避开默认的冷灰蓝配系统字体。

> Warm neutral background, deep teal as the primary colour, serif headings. This avoids the default cool grey-blue paired with system fonts.

### 配色逻辑

收拢为两个色族，靠纯度分级拉开层次，不再堆四个互不相干的色相。

> The palette collapses into two colour families, with depth created by tints and shades rather than by adding unrelated hues.

**主色族：深青蓝**，承载主流程、信息、主按钮。

> **Primary family: deep teal.** Carries the main flow, information and primary actions.

| 级别 | 值 | 用途 | Level | Value | Use |
|---|---|---|---|---|---|
| 900 | `#0b3745` | 底栏、最深文字 | 900 | `#0b3745` | Footer, darkest text |
| 700 | `#12556b` | 主色 | 700 | `#12556b` | Primary |
| 600 | `#1a6b85` | 强调边框、说明条左边线 | 600 | `#1a6b85` | Emphasis borders, note rule |
| 300 | `#8fbccb` | 边框、未激活节点顶线 | 300 | `#8fbccb` | Borders, inactive node caps |
| 100 | `#dceaf0` | 激活态浅底 | 100 | `#dceaf0` | Active tint |
| 050 | `#eef5f8` | 最浅底、辅助信息底 | 050 | `#eef5f8` | Lightest tint, note fill |

**辅助族：暖橙**，只用于需要跟主色拉开差异的地方：20% 困难场景、放宽分支、Browsing 的品类切换。

> **Accent family: warm amber.** Used only where a contrast against the primary is needed: the 20% hard cases, the relaxation branch, Browsing category shifts.

| 级别 | 值 | 用途 | Level | Value | Use |
|---|---|---|---|---|---|
| 800 | `#8a4710` | 深强调 | 800 | `#8a4710` | Deep accent |
| 600 | `#b8621b` | 强调主色 | 600 | `#b8621b` | Accent |
| 300 | `#dfb98c` | 边框 | 300 | `#dfb98c` | Borders |
| 100 | `#f7e9d9` | 浅底 | 100 | `#f7e9d9` | Tint |

**语义色取自同族邻近色**，不引入新色相：成功用墨绿 `#3d6b52`（青蓝的邻近），警示用陶土 `#9c4a33`（暖橙的邻近）。

> **Semantic colours come from neighbouring hues within the same families**, not new hues: success uses sage `#3d6b52` (neighbour of teal), warning uses clay `#9c4a33` (neighbour of amber).

**中性色略带主色色调**，避免中性灰与彩色打架。

> **Neutrals carry a trace of the primary hue** so greys sit with the colours instead of fighting them.

| 用途 | 值 | Use | Value |
|---|---|---|---|
| 主文字 | `#1c272b` | Ink | `#1c272b` |
| 次级文字 | `#43565c` | Secondary text | `#43565c` |
| 弱化文字 | `#74878d` | Muted | `#74878d` |
| 边框 | `#cddade` | Line | `#cddade` |
| 底色 | `#f1f5f6` | Background | `#f1f5f6` |
| 卡片 | `#fdfefe` | Card | `#fdfefe` |

### 第二轮修正

首轮上线后按反馈改了四处。

> Four fixes applied after reviewing the first pass.

1. **架构追踪文字整体放大。** 底部说明栏从 12px 提到 17px，节点标题 13 到 15px，副文本 10 到 12px，标签 12 到 14px。
2. **FSM 那一栏去掉深蓝底。** 原先是纯深色块配白字，在浅色页面里很跳。改为浅青底加青蓝描边，内部盒子改为白底卡片。
3. **流程节点从 5 列改 3 列。** 原先 6 个节点排成上 5 下 1，视觉失衡；现在 3 乘 2 排布。
4. **状态链说明与流程节点拉开距离。** 原先紧贴，现在留 22px 间距，并改为虚线边框的辅助信息样式，不再抢主内容。

> 1. **Architecture trace text enlarged.** Bottom note goes from 12px to 17px, node titles 13 to 15px, sub-text 10 to 12px, label 12 to 14px.
> 2. **The FSM row loses its dark slab.** It was a solid dark block with white text that jumped off the light page. It is now a pale teal row with a teal outline and white inner cards.
> 3. **Flow nodes move from 5 columns to 3.** Six nodes previously laid out as five on top and one below, which looked unbalanced; they now form a 3 by 2 grid.
> 4. **The state-chain note is spaced away from the flow nodes.** It was touching them; it now has 22px of gap and reads as a dashed auxiliary note rather than competing with the main content.

### 字体

标题改用衬线（Iowan Old Style、Palatino、Georgia 依次回退），正文用 Aptos 与 Segoe UI Variable。衬线用于标题、洞察文案、双轨标题和覆盖说明，让叙事部分有人味；技术数据保持无衬线，保证清晰。

> Headings move to a serif stack (Iowan Old Style, Palatino, Georgia as fallbacks) while body text uses Aptos and Segoe UI Variable. Serif is applied to headings, the insight line, track titles and the coverage line so the narrative reads with a human voice; technical figures stay sans-serif for clarity.

### 字号

主标题 68 到 76px，副标题 42 到 48px，引导语 29 到 31px，证据数字 28 到 34px 并启用等宽数字对齐。

> Display title 68 to 76px, section title 42 to 48px, lead 29 to 31px, evidence figures 28 to 34px with tabular numerals enabled.

---

## 七、同步修改的其他文件

| 文件 | 修改 | File | Change |
|---|---|---|---|
| `verify.ps1` | 帧数 53 改 54（2 处）；修复 runbook 与 mirror 路径多套一层 Hamburgerr 的问题 | `verify.ps1` | Frame count 53 to 54 (two places); fixed runbook and mirror paths that nested an extra Hamburgerr |
| `export-assets.ps1` | 帧数 53 改 54；修复 mirror 路径 | `export-assets.ps1` | Frame count 53 to 54; fixed the mirror path |
| `demo/06-视频录制布局与路演画面设计.md` | 逐帧表重建为 54 行并恢复 8 个分段标题；预览图 53 改 54 | runbook | Frame table rebuilt to 54 rows with the eight segment headings restored; previews 53 to 54 |

---

## 八、校验结果

| 项目 | 结果 | Item | Result |
|---|---|---|---|
| 帧数 | 54 | Frames | 54 |
| 总时长 | 295 秒（4:55） | Runtime | 295s (4:55) |
| 时间线连续性 | 0 处断裂 | Timeline gaps | 0 |
| 语速 | 1.00 到 2.50 词/秒（上限 2.6） | Narration rate | 1.00 to 2.50 w/s (limit 2.6) |
| runbook 对齐 | 54 行全部一致 | Runbook alignment | all 54 rows match |
| 预览图 | 54 张 | Previews | 54 |
| 禁用词 | 0 命中 | Banned phrases | 0 hits |

---

## 九、两处需要你拍板

### 1. 事件栏在多数帧显示 "none"

8 个动作里只有 1 个（改口清除品牌）会触发真实事件，其余 7 个在代码里不产生任何事件。如实显示的结果，就是 7 帧的"Detected event"显示 none。

> Only one of the eight actions triggers a real event; the other seven produce none in the code. Showing this honestly means the "Detected event" field reads none on seven frames.

选项：保持如实显示 none；或者把这一栏整个删掉，不再占用画面。

> Options: keep showing none honestly, or remove the field from the screen entirely.

### 2. 第 4 轮保护与脚本口径不一致

代码真实行为是第 4 轮起就不再追问，v7 脚本讲的是第 8 轮和第 10 轮。我按代码改成第 4 轮，但这样画面上的数字（turn 4）和脚本正文（turn 8）对不上。

> The code stops questioning from turn 4, while the v7 script talks about turn 8 and turn 10. I matched the code and show turn 4, which means the screen no longer matches the script text.

选项：按代码显示第 4 轮（准确，但与脚本不一致）；或者改回第 8 轮（与脚本一致，但与代码不符）；或者同时写两行，注明第 4 轮起不再追问、第 10 轮强制出结果。

> Options: show turn 4 to match the code (accurate, diverges from the script); revert to turn 8 to match the script (diverges from the code); or show both lines, noting that questioning stops from turn 4 and a result is forced at turn 10.

---

## 十、临时脚本说明

`video/` 下新增了几个一次性脚本，用于批量重建与校验，不属于交付物，可在确认后删除：`rebuild-all.js`、`sync-runbook.js`、`sync-previews.js`、`apply-design.js`、`fix-narration.js`、`slim-actions.js`、`rebuild-runbook.js`、`rebuild-runbook2.js`、`verify-mirror.js`、`export-assets-node.js`。

> Several one-off scripts were added under `video/` for bulk rebuild and verification. They are not deliverables and can be deleted after review: `rebuild-all.js`, `sync-runbook.js`, `sync-previews.js`, `apply-design.js`, `fix-narration.js`, `slim-actions.js`, `rebuild-runbook.js`, `rebuild-runbook2.js`, `verify-mirror.js`, `export-assets-node.js`.

其中 `verify-mirror.js` 是 `verify.ps1` 的等价校验，因为 PowerShell 在本环境不回显输出，用它来确认一致性。

> `verify-mirror.js` reproduces the checks in `verify.ps1`, because PowerShell does not echo output in this environment and it is needed to confirm consistency.
