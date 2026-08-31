# TikTok TechJam 2026 Shopping Copilot Demo 脚本（v8）

**日期**：2026-09-01
**版本说明**：本版按录制工作台的实际画面重写。段落 2 补齐了原本缺失的技术架构叙事（双轨、三项机制、六步闭环、能力覆盖）；全部旁白按 54 帧逐帧重排；技术说明按 `src/` 真实代码复核后修正；并在 Boundary 与 Evidence 之间预留一段开发编辑器实录，用于运行最终冻结版本的评测代码。

> Shopping Copilot demo script, v8
> Date: 2026-09-01. This version is rewritten against the actual screens of the recording workbench. Section 2 adds the technical architecture narrative that was missing (two tracks, three mechanisms, the six-step loop, capability coverage). All narration is re-laid out across 54 frames. Technical notes are corrected against the real code in `src/`. A live editor insert is reserved between Boundary and Evidence to run the evaluator from the final frozen project structure.

---

## TL;DR

- **产品结论**：Shopping Copilot 把一次性关键词搜索变成可修正的购物决策过程，在最多十轮内持续维护用户当前有效意图。
- **叙事主线**：Problem → Pain → Need → Insight → Solution → Demo → Reproduction → Evidence → Value，保留 Buying、Intent Override、Browsing、澄清和 Boundary 五个连续展示节点，并用一次真实代码运行把产品演示连接到量化证据。
- **技术重点**：Buying/Browsing 双轨是题目要求；真正的竞争力是槽位级状态更新、信息增益澄清和受控放宽的组合，以及可回放、可解释、可复现。
- **架构段新增内容**：双轨共享同一套状态、三项机制作用于同一状态、六步产品闭环、能力贯穿全部场景而不只是困难样本。
- **录制目标**：英文正式成片约 4:58，硬上限 5:00。54 个工作台帧之外增加一个约 10 秒的开发编辑器实录插段；技术说明用于屏幕展示和答辩，不逐字朗读。

> - **Product claim**: Shopping Copilot turns a one-off keyword search into a shopping decision process you can correct, maintaining the user's current valid intent within ten turns.
> - **Narrative spine**: Problem → Pain → Need → Insight → Solution → Demo → Reproduction → Evidence → Value, keeping Buying, Intent Override, Browsing, clarification and Boundary as five continuous beats and connecting the product demo to quantitative evidence with a real code run.
> - **Technical focus**: the Buying/Browsing tracks are a challenge requirement; the real edge is the combination of slot-level state update, information-gain clarification and controlled relaxation, plus replayable, explainable, reproducible behaviour.
> - **New in the architecture section**: two tracks sharing one state, three mechanisms acting on that state, the six-step product loop, and capability spanning every scenario rather than only the hard cases.
> - **Recording target**: approximately 4:58 in English, with a hard ceiling of 5:00. One roughly ten-second live editor insert sits outside the 54 workbench frames. Technical notes are for screen and Q&A, not read aloud.

---

## 0. 金字塔原理总览

### 顶层结论

> Shopping Copilot 是一个对话式购物搜索 Agent。它在最多十轮对话内，把用户动态变化的购物意图收敛为可信的商品结果。

> Shopping Copilot is a conversational shopping search agent. Within ten turns, it converges a dynamically changing shopping intent into trustworthy product results.

### 三个支撑

1. **基本面稳**：Buying 和 Browsing 采用不同策略，分别服务高精度购买和开放式探索。
2. **难点处理完整**：槽位级状态更新处理改口，信息增益澄清处理候选过宽，受控放宽处理空集和越界请求。
3. **价值可解释**：少重复描述、少无效搜索、结果不静默违约，最终对应用户"省事、敢信"。

> 1. **The basics hold**: Buying and Browsing use different strategies, serving high-precision purchase and open exploration respectively.
> 2. **The hard cases are covered**: slot-level state update handles revisions, information-gain clarification handles an over-broad candidate pool, controlled relaxation handles empty and out-of-bounds requests.
> 3. **The value is explainable**: less repetition, fewer wasted searches, no silent constraint violations, mapping to "less effort, more trust" for the shopper.

### 每段都回答四个问题

```text
用户说了什么
→ 系统理解成什么
→ 系统做了什么
→ 用户因此得到什么
```

> What the user said → what the system understood → what the system did → what the user gets from it.

---

## 1. 完整叙事链路

| 环节 | 一句话内容 |
|---|---|
| **Problem** | 传统电商搜索把需求当作静态关键词，难以处理对话中的持续变化。 |
| **Pain** | 用户会省略条件、补充条件、改口、没有明确偏好，或提出目录中没有可行解的请求。 |
| **Need** | 把"理解 → 提问 → 筛选 → 推荐"串成连续的购物决策过程。 |
| **Insight** | 购物意图是持续变化的状态，不是一条一次性 query。 |
| **Solution** | 一套状态驱动框架，加上双轨策略、槽位更新、澄清和受控放宽。 |
| **Value** | 对用户是省事和敢信，对平台是更高的搜索效率和转化机会。 |

| Beat | One line |
|---|---|
| **Problem** | Conventional e-commerce search treats intent as static keywords and struggles with change across a conversation. |
| **Pain** | Users omit conditions, add conditions, change their minds, have no clear preference, or ask for something with no feasible answer in the catalog. |
| **Need** | Chain "understand → ask → filter → recommend" into one continuous shopping decision process. |
| **Insight** | Shopping intent is a continuously changing state, not a one-off query. |
| **Solution** | One state-driven framework, plus two-track strategy, slot updates, clarification and controlled relaxation. |
| **Value** | Less effort and more trust for the shopper; higher search efficiency and conversion opportunity for the platform. |

---

## 2. Maya 的购物旅程

**人物**：Maya，28 岁，产品经理。她需要买一双黑色跑鞋，同时想为夏日户外运动准备一套轻便、透气的运动服饰。

> Maya, 28, product manager. She needs black running shoes and wants lightweight, breathable sportswear for summer outdoor training.

| 时段 | 用户场景 | evaluator 场景 | 系统展示能力 |
|---|---|---|---|
| 早上 | 黑色跑鞋，预算 100 美元以内 | Buying | 硬约束优先，快速收敛 |
| 早上 | 先指定 Nike，随后改为任何品牌都可以 | Intent Override | 槽位级状态更新，局部重新检索 |
| 下午 | 夏日户外运动穿什么 | Browsing | 场景语义、软偏好和结果多样性 |
| 傍晚 | 只说"帮我看看鞋" | 候选过宽 | 信息增益澄清 |
| 晚上 | 五美元以内的 Nike 鞋 | Boundary | 空集检测、逐级放宽和受限响应 |

| Time | User scenario | Evaluator scenario | Capability shown |
|---|---|---|---|
| Morning | Black running shoes under $100 | Buying | Hard constraints first, fast convergence |
| Morning | Nike only, then any brand is fine | Intent Override | Slot-level state update, local re-retrieval |
| Afternoon | What to wear for summer outdoor training | Browsing | Scene semantics, soft preferences, result diversity |
| Evening | Just "show me shoes" | Over-broad candidates | Information-gain clarification |
| Night | Nike shoes under $5 | Boundary | Empty-set detection, staged relaxation, constrained response |

这条旅程不是五个孤立功能，而是同一个用户在不同意图状态下的连续决策过程。视频中每个场景开始前都新建会话并执行 `reset`。

> This is not five isolated features but one user's continuous decision process across different intent states. Each scenario starts a new session with `reset`.

---

## 3. 段落结构（对应录制工作台 54 帧）

| 段落 | 时间 | 帧数 | 内容 |
|---|---|---:|---|
| 1 Opening | 0:00-0:30 | 3 | 定义、承诺、难点 |
| 2 Product loop | 0:30-1:20 | 6 | 问题、洞察、双轨、三项机制、六步闭环、能力覆盖 |
| 3 Buying + Override | 1:20-2:35 | 15 | 三轮连续输入，重点展示只清除 brand |
| 4 Browsing | 2:35-3:10 | 10 | 两轮输入，场合保留，软偏好更新 |
| 5A Clarification | 3:10-3:35 | 10 | 一问一答，信息增益 |
| 5B Boundary | 3:35-3:55 | 5 | 空集、受控放宽、受限响应 |
| 5C Live evaluation | 3:55-4:05 | 1 个实录插段 | 从 Demo 界面切到开发编辑器，运行最终评测入口并显示真实输出 |
| 6 Evidence | 4:05-4:36 | 3 | 质量、泛化、可靠性 |
| 7 Value and roadmap | 4:36-4:58 | 2 | 用户价值、平台假设、路线图 |

| Section | Time | Frames | Content |
|---|---|---:|---|
| 1 Opening | 0:00-0:30 | 3 | Definition, promise, the hard part |
| 2 Product loop | 0:30-1:20 | 6 | Problem, insight, two tracks, three mechanisms, six-step loop, capability coverage |
| 3 Buying + Override | 1:20-2:35 | 15 | Three consecutive turns, focusing on clearing brand only |
| 4 Browsing | 2:35-3:10 | 10 | Two turns, occasion retained, soft preferences updated |
| 5A Clarification | 3:10-3:35 | 10 | One question, one answer, information gain |
| 5B Boundary | 3:35-3:55 | 5 | Empty set, controlled relaxation, constrained response |
| 5C Live evaluation | 3:55-4:05 | 1 live insert | Cut from the demo to the development editor, run the final evaluation entry point, and reveal its real output |
| 6 Evidence | 4:05-4:36 | 3 | Quality, generalization, reliability |
| 7 Value and roadmap | 4:36-4:58 | 2 | User value, platform hypotheses, roadmap |

---

## 4. 段落 2 详解（本版新增内容）

段落 2 原本只有一页架构图，缺少四个节点。v8 把它拆成六帧。

> Section 2 previously had a single architecture slide and was missing four nodes. v8 splits it into six frames.

### F1 · Problem 与 Pain

**屏幕上**：传统搜索"一次 query 一组结果"，对比真实购物行为的四个痛点：开头含糊、补充条件、改口、从购买转向浏览。

> On screen: traditional search "one query, one result list" against four real shopping behaviours: starts vague, adds constraints, changes mind, switches from buying to browsing.

**旁白**：Traditional search treats every request as a static query, so an old condition can quietly outlive its welcome.

### F2 · Insight

**屏幕上**：洞察面板，一句话点明"意图是变化的状态，不是静态查询"，差异在一套状态驱动框架。

> On screen: an insight panel stating that intent is a changing state rather than a static query, and that the difference sits in one state-driven framework.

**旁白**：We treat intent as a changing state and put the difference in one state-driven framework.

### F3 · 双轨

**屏幕上**：两张卡片。Buying 保护硬条件，Browsing 保护选择空间。两者跑在同一套状态和决策边界上。

> On screen: two cards. Buying protects hard constraints; Browsing keeps options open. Both run on the same state and decision boundary.

**旁白**：Buying protects your hard constraints. Browsing protects your options. Both run on the same state.

**答辩口径**：双轨是题目要求，不是我们宣称的创新。我们的贡献是让两条轨道共享同一套状态。

> Q&A line: the two tracks are a challenge requirement, not an innovation we claim. Our contribution is making both tracks share one state.

### F4 · 三项机制

**屏幕上**：三张卡片。槽位级状态更新、一个值得占用一轮的问题、受控放宽。

> On screen: three cards. Slot-level state update, a question that earns its turn, controlled relaxation.

**旁白**：Three mechanisms do the work: slot-level update, a question that earns its turn, and controlled relaxation.

**答辩口径**：三个机制不是三个功能，而是同一套状态的三种行为。

> Q&A line: these are not three features but three behaviours of one shared state.

### F5 · 六步产品闭环

**屏幕上**：六步流程全部点亮。路由 → 更新有效槽位 → 检索排序 → 校验硬约束 → 推荐/澄清/放宽 → 可验证结果与轨迹记录。

> On screen: all six steps lit. Route → update valid slots → retrieve and rank → verify hard constraints → recommend, clarify or relax → verifiable result and trace.

**旁白**：Route it, update the valid slots, retrieve, verify, then recommend, clarify, or relax, and keep the trace.

**注意**：最后一步"可验证结果与轨迹记录"是 v8 补上的，v7 版本只有五步。

> Note: the final step, "verifiable result and trace", is added in v8; v7 had only five steps.

### F6 · 能力覆盖

**屏幕上**：80/20 覆盖条。并说明三个机制贯穿全部 100% 场景，困难样本只是让价值最显眼。

> On screen: an 80/20 coverage bar, with a note that the three mechanisms span all 100% of scenarios and the hard cases only make the value most visible.

**旁白**：These are not patches for the hard cases. They run across every scenario, including the easy eighty percent.

**这句是整个叙事的关键**：如果评委觉得"你们只是困难场景做得还行"，叙事就塌了。

> This line is the hinge of the whole narrative: if judges leave thinking "they only handle the hard cases well", the story collapses.

---

## 5. 英文逐帧旁白

完整 54 帧旁白见同目录的 `tiktok-techjam-2026-narration-bilingual-2026-09-01.md`。这里是按段落聚合的版本。

> The full 54-frame narration is in `tiktok-techjam-2026-narration-bilingual-2026-09-01.md` in the same folder. This is the version grouped by section.

### Segment 1 · Opening

> Shopping Copilot is a conversational shopping search agent. It turns a one-off query into a shopping process you can correct.
>
> Within ten turns, it converges changing shopping intent into trustworthy product results.
>
> The hard part is not finding more products. It is that users keep adding, revising, and contradicting what they asked for.

### Segment 2 · Product loop

> Traditional search treats every request as a static query, so an old condition can quietly outlive its welcome.
>
> We treat intent as a changing state and put the difference in one state-driven framework.
>
> Buying protects your hard constraints. Browsing protects your options. Both run on the same state.
>
> Three mechanisms do the work: slot-level update, a question that earns its turn, and controlled relaxation.
>
> Route it, update the valid slots, retrieve, verify, then recommend, clarify, or relax, and keep the trace.
>
> These are not patches for the hard cases. They run across every scenario, including the easy eighty percent.

### Segment 3 · Buying + Override

> Maya asks for black running shoes under one hundred dollars.
>
> The system reads that as Buying and writes three hard constraints.
>
> Category, colour, and budget become conditions every result must satisfy.
>
> It filters first, retrieves and ranks, then verifies before anything is shown.
>
> Only results that clear every hard constraint reach her.
>
> Then she adds one condition: Nike only.
>
> Brand joins the state. Nothing else is touched.
>
> She keeps every constraint she already gave.
>
> The tighter state triggers a fresh retrieval.
>
> Now only legal Nike candidates come back.
>
> Then she changes her mind: any brand is fine.
>
> The system catches the no-preference signal on brand.
>
> It clears brand only. Category, colour, and budget survive.
>
> Stale results are dropped, and retrieval runs again.
>
> One condition changed. She did not have to say the rest again.

### Segment 4 · Browsing

> Maya explores summer outdoor training instead.
>
> Scene language routes this to Browsing.
>
> The occasion is kept as context, not a hard filter.
>
> It retrieves, ranks, and diversifies.
>
> Tops, shorts, and breathable layers all stay in play.
>
> She asks for lighter, less fitted options.
>
> The route stays Browsing.
>
> Style updates. The occasion stays put.
>
> Soft preferences reweight the ranking without excluding anything.
>
> The direction changes. She can still explore before narrowing.

### Segment 5A · Clarification

> Maya starts with a broad request.
>
> The system reads it as Buying.
>
> The category is too broad.
>
> It scores the useful gaps.
>
> So it asks one useful question.
>
> She answers: running shoes.
>
> The route holds.
>
> Category narrows from broad to specific.
>
> Retrieval resumes.
>
> One question, real convergence.

### Segment 5B · Boundary

> Maya asks for Nike shoes under five dollars.
>
> The system reads this as Buying.
>
> Budget is locked. Brand can give way.
>
> Nothing matches, so it relaxes brand and holds the budget.
>
> No legal match exists, so it explains rather than cheats.

### Segment 5C · Live evaluation insert

> Now we leave the demo and run the evaluator from the project itself. The evidence that follows comes from this reproducible execution.

**切屏位置**：`S05B-T01-P05` 的 Boundary 响应停留结束后，在 `3:55` 从 Demo 全屏硬切到开发编辑器。不要在 Buying、Browsing 或 Boundary 流程中途切走，否则会打断 Maya 的连续购物旅程。

> **Cut point**: after the `S05B-T01-P05` Boundary response has finished, hard-cut from the full-screen demo to the development editor at `3:55`. Do not leave the demo during Buying, Browsing or Boundary; that would interrupt Maya's continuous shopping journey.

**预留镜头（约 10 秒，最终项目结构冻结后再填具体内容）**：

1. `3:55-3:58`：开发编辑器已经打开最终评测入口附近的代码，只展示与 Agent 调用、数据集加载和指标汇总直接相关的区域。
2. `3:58-4:00`：焦点移到编辑器内置终端，输入并执行 `[待定：最终可复现评测命令]`。
3. `4:00-4:05`：剪掉纯等待时间后显示真实完成输出，停留在 `[待定：最终指标摘要]`；画面角落标注 `Evaluation completed · idle wait removed`，避免把跳剪误解为即时运行。
4. `4:05`：从终端输出切回 Demo 工作台的 `S06-F01`，开始解释与刚才输出一致的 Evidence。

> **Reserved shot, about ten seconds; fill the specifics only after the final project structure is frozen**:
>
> 1. `3:55-3:58`: the development editor is already positioned near the final evaluation entry point, showing only the code directly related to Agent invocation, dataset loading and metric aggregation.
> 2. `3:58-4:00`: move focus to the integrated terminal and run `[TBD: final reproducible evaluation command]`.
> 3. `4:00-4:05`: remove idle waiting in the edit, then reveal the genuine completed output and hold on `[TBD: final metric summary]`. Add `Evaluation completed · idle wait removed` in a corner so the jump cut is not mistaken for an instant run.
> 4. At `4:05`, cut from the terminal back to `S06-F01` in the demo workbench and explain the Evidence that matches the output just shown.

**冻结后必须同步的内容**：评测入口文件、终端命令、数据集名称、样本数、指标字段、运行配置和 Evidence 三帧中的全部数字。这里不提前绑定当前目录结构，也不预写可能变化的命令。

> **Items that must be synchronized after the freeze**: evaluation entry file, terminal command, dataset name, sample count, metric fields, runtime configuration, and every number in the three Evidence frames. This placeholder deliberately does not bind to the current directory structure or pre-write a command that may change.

### Segment 6 · Evidence

> On the latest 200-session public set, HitRate at ten is 0.9600, MRR is 0.606629, mean first-hit turn is 2.585, and the composite score is 0.830289.
>
> On the same catalog, HitRate is 0.880 on 100 self-built sessions and 0.854 on 500. These test transfer, not headline.
>
> The public run recorded zero fallbacks, p95 at 48.044 milliseconds, and no external model calls.

### Segment 7 · Value and roadmap

> For shoppers: less repetition, local correction, results you can trust, and no quietly broken constraints.
>
> For a platform these are hypotheses worth testing: efficiency, conversion, fewer hand-offs. The roadmap starts with a live catalog.

---

## 6. 技术说明（按 src/ 代码复核）

以下说明用于屏幕展示和答辩，不逐字朗读。v8 按真实代码修正了七处。

> These notes are for screen and Q&A, not read aloud. v8 corrects seven items against the real code.

### 6.1 状态机

设计层定义了九个状态：`START → UNDERSTAND → RETRIEVE → ASSESS → CLARIFY / RELAX → RECOMMEND → LIMIT_RECOMMEND`，另有 `ERROR_FALLBACK`。实现把这套状态拍平成一次 `respond()` 调用里的线性管道，代码里没有同名的状态枚举类。答辩时说"设计上的状态机"即可。

> The design defines nine states: `START → UNDERSTAND → RETRIEVE → ASSESS → CLARIFY / RELAX → RECOMMEND → LIMIT_RECOMMEND`, plus `ERROR_FALLBACK`. The implementation flattens this into a linear pipeline inside one `respond()` call; there is no state enum class with those names in the code. Say "the designed state machine" in Q&A.

### 6.2 事件检测

代码只识别五种事件：`override`、`clear`、`negation`、`no_preference`、`intent_switch`。不在其中会直接报错。

> The code recognises only five event kinds: `override`, `clear`, `negation`, `no_preference`, `intent_switch`. Anything else raises an error.

### 6.3 槽位

合法槽位共十个：价格上下限、品牌、颜色、材质、品类、尺码、场合、风格、用途。没有"合身度"这个槽位。

> There are ten legal slots: price min and max, brand, colour, material, category, size, occasion, style, use case. There is no "fit" slot.

硬槽位只有价格上下限和尺码，其余是软槽位。但品类、颜色、品牌同样参与硬过滤：不满足就直接淘汰，不会被语义相关度抵消。

> Only price bounds and size are hard slots; the rest are soft. Category, colour and brand still take part in hard filtering: anything that fails is dropped outright and is not rescued by semantic relevance.

### 6.4 检索路径

当前 d4 配置关闭了 dense、LLM 和意图模型。检索先做硬过滤得到合法子集，再在子集内做属性检索和属性重排。词法通道在 d4 的单次优化开关下不执行。

> The current d4 config disables dense, LLM and the intent model. Retrieval first hard-filters to a legal subset, then runs attribute retrieval and attribute reranking within it. The lexical channel does not execute under d4's single-pass optimisation switch.

### 6.5 澄清

候选数超过 10 才考虑提问。系统会检查候选分布，给每个缺失槽位打分，选出信息增益最高的那个，每轮只问一个属性。

> Questioning is considered only when the candidate count exceeds ten. The system inspects the candidate spread, scores each missing slot, picks the one with the highest information gain, and asks one attribute per turn.

轮次保护：打开"推荐优先"开关时，第 4 轮起就不再追问；第 8 轮进入晚轮保护；第 10 轮必须给出合法响应。

> Turn protection: with the "recommend first" switch on, questioning stops from turn 4; turn 8 enters late-turn protection; turn 10 must return a legal response.

### 6.6 受控放宽

硬过滤为空时按 brand、color/material、category synonym 三级依次尝试。预算和明确排除项全程不参与放宽。放宽只在 Buying 路由发生。

> When hard filtering returns empty, it tries brand, then colour or material, then category synonyms. Budget and explicit exclusions never take part in relaxation. Relaxation happens only on the Buying route.

---

## 7. 录制检查

- [ ] 每个场景开始前新建会话并执行 `reset`。
- [ ] 1080p、浏览器缩放 100%、按 `F` 进入 clean capture。
- [ ] 正式录制不用自动播放，主视频只录 Segment 1 到 7。
- [ ] `3:55` 在 Boundary 完整结束后切到开发编辑器，`4:05` 从真实评测输出切回 `S06-F01`。
- [ ] 冻结项目结构后替换 Live evaluation 中的全部 `[待定]`，并确认终端输出与 Evidence 三帧逐项一致。
- [ ] 只剪掉无信息的等待时间；保留执行动作和真实结果，并明确标注 `idle wait removed`。
- [ ] 逐帧旁白按工作台底部的 voiceover 念，不即兴发挥。
- [ ] 画面上"Why it matters"、指标 trace、底部配置不念，交给评委看。
- [ ] 不展示 API key、`api.env`、私有路径、ground truth、完整目录和调试堆栈。
- [ ] 改完 HTML 后跑 `export-assets.ps1` 和 `verify.ps1`，通过才继续。

> - [ ] Start each scenario with a new session and run `reset`.
> - [ ] 1080p, browser zoom 100%, press `F` for clean capture.
> - [ ] No autoplay in the formal recording; record Segments 1 to 7 only.
> - [ ] At `3:55`, cut to the development editor only after Boundary is complete; at `4:05`, return from the genuine evaluator output to `S06-F01`.
> - [ ] After the project structure is frozen, replace every `[TBD]` in Live evaluation and verify that the terminal output matches all three Evidence frames field by field.
> - [ ] Remove only idle waiting; preserve the execution action and genuine result, and label the edit `idle wait removed`.
> - [ ] Read the voiceover at the bottom of the workbench frame by frame; do not improvise.
> - [ ] Do not read the on-screen "Why it matters" line, the metric trace or the bottom configuration; let judges read them.
> - [ ] Never show API keys, `api.env`, private paths, ground truth, the full catalog or debug stacks.
> - [ ] After changing the HTML, run `export-assets.ps1` and `verify.ps1` and only proceed if they pass.

---

## 8. 答辩优先回答三句

1. 购物意图是持续变化的状态，不是静态查询；这是我们设计状态驱动框架的起点。
2. Buying/Browsing 双轨是题目要求；我们的差异化在于槽位级状态更新、信息增益澄清、受控放宽，以及可复现的组合实现。
3. 三个机制贯穿全部场景，不只是那 20% 的困难样本；当前路径是离线、确定性和可复现的。

> 1. Shopping intent is a continuously changing state, not a static query; that is where our state-driven framework starts.
> 2. The Buying/Browsing tracks are a challenge requirement; our differentiation is slot-level state update, information-gain clarification, controlled relaxation, and a reproducible combination.
> 3. The three mechanisms span every scenario, not just the hard 20%; the current path is offline, deterministic and reproducible.

---

## 9. 数据来源

- `runresult/829_0912/test-public.json`（200 会话，headline）
- `runresult/829_0912/test-own.json`（100 会话，泛化）
- `runresult/829_0912/test-own2.json`（500 会话，泛化）
- `技术文档.md`（FSM 设计）
- `video/index.html`（录制工作台，54 帧）
- `demo/06-视频录制布局与路演画面设计.md`（逐帧 runbook）

> - `runresult/829_0912/test-public.json` (200 sessions, headline)
> - `runresult/829_0912/test-own.json` (100 sessions, generalization)
> - `runresult/829_0912/test-own2.json` (500 sessions, generalization)
> - `技术文档.md` (FSM design)
> - `video/index.html` (recording workbench, 54 frames)
> - `demo/06-视频录制布局与路演画面设计.md` (per-frame runbook)
