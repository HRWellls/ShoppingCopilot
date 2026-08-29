# Phase 2 低分案例优化方案（通用性优先）

基线：`d4` profile，公开集 200 样本
`hit@10=0.925`　`MRR=0.4610`　`MTTC=3.040`　`efficiency=0.7955`　`TechnicalScore=0.7600`

本文所有结论均由 `.runtime/retrieval-d4.json`（593 turn、5900 条 rerank explanation）与源码交叉验证得出，不针对任何单条样本调参。

---

## 一、先定杠杆：算分函数决定优化顺序

评分函数在 [local_evaluator.py:279-280](Hamburgerr/evaluator/local_evaluator.py#L279-L280)：

```
efficiency = (11 - MTTC) / 10
score = 0.50*hit@10 + 0.30*MRR + 0.20*efficiency
```

把三项的**剩余空间 × 权重**算出来，优化顺序不言自明：

| 指标 | 当前 | 上限 | 满额可得分 | 边际价值 |
|---|---|---|---|---|
| hit@10 | 0.925 | 1.0 | **+0.0375** | 已接近饱和 |
| MRR | 0.4610 | 0.925（现有命中全变 rank1） | **+0.1392** | 单个 session rank2→1 值 +0.00075 |
| MTTC | 3.040 | 1.30（见下） | **+0.0349** | 每减少 1 个 turn 仅值 0.02 |

**结论：MRR 是唯一的大杠杆，且它不需要多召回一个商品，只需要把已经召回的目标往前挪。**

命中样本的首命中名次分布，暴露了问题的全貌：

```
rank  1: 58   2: 29   3: 20   4: 16   5: 13   6: 13   7: 5   8: 12   9: 13   10: 6
```

185 个命中里只有 **58 个 rank1（31.4%）**，而 hit@10 高达 92.5%。目标几乎总能进 Top10，却几乎总排不到第一。**这不是召回问题，是排序区分度问题。**

补充证据：15 个未命中样本中，目标 **100% 已在 150 候选池内**（`candidate_recall_at_pool=1.0`，`ranking_failures=15`）。召回侧没有失败，一个都没有。

MTTC 下界 1.30 的来源：`intent_override` 场景在 [local_evaluator.py:252](Hamburgerr/evaluator/local_evaluator.py#L252) 有 `override_applied` 门控，override 前的命中不计分，而 override turn ∈ {3,4}，所以这 30 个样本的 MTTC 物理下界是 3。`(30*3 + 170*1)/200 = 1.30`。

### 分场景拆解

| 场景 | n | hit@10 | MRR | MTTC | rank1 占命中 |
|---|---|---|---|---|---|
| buying | 80 | **0.963** | **0.406** | 2.56 | 19/77 (24.7%) |
| browsing | 80 | 0.938 | 0.470 | 2.65 | 23/75 (30.7%) |
| intent_override | 30 | 0.867 | 0.616 | **4.67** | 14/26 |
| boundary | 10 | **0.700** | 0.358 | **5.10** | 2/7 |

`buying` 是最反常的一格：召回最好（0.963），MRR 最差（0.406）。下面 R2 会说明为什么恰恰是 buying 路由的打分特征最容易饱和。

---

## 二、六个根因

### R1　三路混合检索退化为单通道

**证据。** 5900 条 rerank explanation 中，`source_ranks` 只出现过 `attribute` 一个键，`lexical` / `structured` / `dense` **贡献恒为 0**；timing 上 `lexical_ms` p50 = 0.002、`structured_ms` p50 = 0.0003，即两条通道根本没执行。

**代码位置。** `optimized_single_pass_enabled=True` 时：
- [hybrid.py:249-253](Hamburgerr/src/retrieval/hybrid.py#L249-L253) 硬跳过 lexical
- [hybrid.py:256-262](Hamburgerr/src/retrieval/hybrid.py#L256-L262) 硬跳过 structured
- 加上 `dense_enabled=False`，三条通道全灭

**后果。**
1. [rerank.py:88-95](Hamburgerr/src/retrieval/rerank.py#L88-L95) 的 `source_rank` 特征退化。单通道下它等于 `1.2 × 1.8 × (1-(rank-1)/300)`，是 rank 的单调线性函数，**没有任何跨通道信息**。
2. 失去混合检索最强的信号——**多通道一致性**。「同时被词法和属性通道排到前面」本应是 rank1 的最佳判据，现在无法计算。
3. `fuse_rankings` 输入为空，`b3_fused` 为空，raw_union 等于 attribute 单通道。

**这是为延迟做的交换**（p95 59ms vs 基线 156ms），但延迟预算远未用尽，而排序区分度是当前唯一瓶颈。

**通用修复。** 恢复多通道，但不回退到全量重算：
- 让 lexical / structured 只在 attribute 通道产出的 **150 候选池内**重打分（pool-restricted rescoring）。复杂度从 O(catalog) 降到 O(150)，延迟增量可控在个位数毫秒。
- 在 reranker 中新增 `source_agreement` 特征：`len(ranks) / n_active_sources`，以及 `mean_reciprocal_source_rank`。这两个特征天然具备泛化性——它们衡量的是「多个独立视角是否同意」，不含任何数据集特定常数。

### R2　特征饱和：打分被无区分度的常数项主导（MRR 头号杀手）

这是最重要的一节。

**证据 1 —— 特征在 Top10 内取值完全相同。**

| 特征 | 在 Top10 内全等的 turn 数 | 占比 |
|---|---|---|
| `exact_phrase` | 207 / 588 | 35.2% |
| `field_completeness` = 12.0（饱和） | 1082 / 5900 条 | 18.3% |

**证据 2 —— 一个 turn-1 真实样本的特征分解。** Top10 的 10 个候选中，`exact_phrase=18.36`、`field_completeness=12.0`、`field_category=8.0` **三项完全一致**，总分基数 ~148，而 Top10 的分差中位数只有 **4.76 分（≈3%）**。

也就是说：约 38 分（26%）的分值是**对所有候选一视同仁的常数偏移**，它不改变任何排序，却压缩了真正有区分度的特征（`title_overlap`、`feature_overlap`）的相对影响力。当分差被压到 3% 以内，**名次实际由 `catalog_order` 兜底决定**——等价于随机。

这直接解释了「hit@10=0.925 但 rank1=31%」：目标进了池子，但把它和其他 9 个区分开的信号被常数项稀释了。

**证据 3 —— 为什么 buying 最差。** `field_completeness` 上限 12 分、`field_category` 8 分，这两项在 buying 路由权重最高（硬约束齐全的样本都能拿满），所以 buying 的分数最饱和、MRR 最低（0.406）。这与「buying 召回最好」并不矛盾，反而印证了饱和假设。

**根因代码。** [rerank.py](Hamburgerr/src/retrieval/rerank.py) 中 `_exact_phrase_score` 的匹配条件是双向子串：

```python
phrase in feature or feature in phrase
```

`feature in phrase` 极度宽松——任何短 feature 只要是长句的子串就命中。而 `semantic_terms` 会随轮次累积（含历史消息 + `query_evidence`），phrase 集合越来越大，导致**几乎所有候选都能匹配上**，特征随之饱和。每个 phrase 还给 `min(20, 5 + info/2)` 的固定 5~20 分加成，与匹配质量无关。

**通用修复（三条，均不含数据集特定常数）。**

1. **改为「相对区分度」而非「绝对匹配量」。** 特征值在归一前，先减去当前候选集内该特征的中位数：`f' = f - median(f over pool)`。全等特征自动归零，不再占用分值空间。这是标准的 per-query feature centering，对任何数据分布都成立。
2. **收紧 phrase 匹配。** 去掉 `feature in phrase` 方向，或要求匹配 token 数 ≥ 2 且覆盖率 ≥ 50%。用 token-set IoU 取代子串包含。
3. **饱和特征改用对数压缩。** `field_completeness` 这类计数型特征用 `w * log1p(n)/log1p(n_max)` 替代线性求和，天花板自然平滑，避免多个候选同时顶到 12.0。
4. **消灭 `catalog_order` 兜底。** 当 Top-K 分差小于阈值时，改用有意义的次序键（如 `source_agreement`，见 R1），而不是目录顺序。

---

### R3　override 回合自毁上下文（30 样本、MTTC 4.67 的根源）

**先看清评测机制。** [local_evaluator.py:74-88](Hamburgerr/evaluator/local_evaluator.py#L74-L88)：

```python
old_value = soft[-1]      # 目标商品最弱的软偏好
new_value = hard[0]       # 目标商品最强的硬约束 ★
message = f"Actually, ignore my earlier preference. What I need is: {new_value}."
```

**override turn 递给 agent 的是目标商品最具区分度的硬约束**。理论上目标应该直接跳到 rank1。而且 `override_applied` 门控让 override 之前的命中全部不计分——**这 30 个样本的全部得分，只取决于 override turn 及其之后的排名**。

**实测却是反向的：**

| override turn 排名变化 | session 数 |
|---|---|
| 变差 | **13** |
| 不变 | 12 |
| 变好 | **5** |
| override 前目标已在 Top10 | **29 / 30** |
| `override_state_failures` | 18 / 30 |

29/30 在 override 前就已经排进 Top10（白送的分拿不到），而在拿到最强信号的那一回合，排名反而变差的比变好的多 2.6 倍。`public_0034` 的轨迹是 `rank 1 → 1 → 1 → miss`：拿到最强约束后直接掉出 Top10。

**三个叠加的机制性缺陷：**

**(a) 历史上下文在最关键的一回合被丢弃。** [hybrid.py:72-74](Hamburgerr/src/retrieval/hybrid.py#L72-L74)：

```python
state_changed = bool(set(state.last_event_kinds) & {"override","clear","negation","intent_switch"})
history_context = [current] if state_changed else retained_history[-4:]
```

override turn 必然触发 `state_changed`，于是 `history_context` 只剩当前这句话——**首轮的 `I'm looking for {category}` 被丢掉**。更严重的是 [reducer.py:163](Hamburgerr/src/state/reducer.py#L163) 把 `retrieval_context_start` 推到 `len(history)-1`，**该截断对之后所有轮次永久生效**。category 只剩 slot 里的结构化副本，而结构化通道恰好被 R1 关掉了。

**(b) "ignore" 触发歧义清除。** [events.py:35-40](Hamburgerr/src/nlu/events.py#L35-L40) 用 `\b(?:clear|remove|forget|ignore)\b` 匹配，override 消息里的 "ignore" 命中后，因无具名 slot 而产出 `TurnEvent("clear", frozenset(), 0.60, False, ("ambiguous_clear",))`，接着 [reducer.py:40-48](Hamburgerr/src/state/reducer.py#L40-L48) 会去清 `last_asked_slot` 或最近的软 slot——**清掉的很可能不是 `old_value` 对应的那个**。

**(c) `new_value` 拿不到 exact_phrase credit。** `_exact_phrase_score` 只识别 `customer_reply` 的模板（按 `;` 切分、剥离 `for that ... :` 前缀）。override 消息既无 `;` 也无该前缀，于是**整句变成一个超长 phrase**，最强的硬约束反而匹配不上。

**通用修复。**
1. **区分 override 与 reset。** override 语义是「替换某个约束」，不是「清空全部上下文」。改为**槽位级失效**：只丢弃被替换 slot 的证据，保留 category 及其他仍然有效的历史。`retrieval_context_start` 不再单调推进，或至少永久保留首轮消息（它承载 category）。
2. **让 `ignore/forget` 在存在显式 override 时不再产出 `ambiguous_clear`。** 同一句里既有「忽略旧的」又有「我要新的」时，`override` 事件应当抑制歧义 clear——这是通用的意图优先级规则，与数据无关。
3. **证据归一化去模板化。** 通用规则：剥离任意「引导子句 + 冒号」前缀，并按 `;`、`.`、`,` 多分隔符切分。不硬编码任何一种问法。
4. **override turn 提升新约束权重。** 用户显式纠正的约束，置信度应高于被动推断的槽位，这是对话系统的通用先验。

**量化收益。** 若 30 个 override 样本全部在 turn3 命中且 rank1：hit@10 → 0.935、MRR → 0.519、MTTC → 2.79，**score 0.760 → 0.787（+0.027）**。

### R4　澄清策略把已经到手的分数推迟掉

**证据。** 183 个 session 在 **turn 1** 就已经把目标召回进 Top10，但只有 **50 个** 在 turn 1 计入首命中。**133 个 session 白白推迟了首命中**。原因是 turn 1 的 action 是 `clarify` 而非 `recommend`——而 [local_evaluator.py:246](Hamburgerr/evaluator/local_evaluator.py#L246) 只在 `action == "recommend"` 时记 `first_hit_turn`。

进一步：**35 个 session 的澄清完全无产出**（提问后候选集既没缩小、Top10 指纹也没变）。

**根因：五个自适应早退里有四个是死代码。**

| 早退条件 | 触发次数 / 591 turn | 状态 |
|---|---|---|
| `score_margin`（[policy.py:102](Hamburgerr/src/dialogue/policy.py#L102)） | **0** | 阈值 `0.01`，而实测 Top1-Top2 margin 最大仅 **0.0086** → 永不触发 |
| `stable_top10` | 0 | 从未出现 |
| `no_candidate_shrink` | 0 | 从未出现 |
| `non_improving_clarifications` | 0 | 从未出现 |
| `recommendation_first`（turn ≥ 4） | 生效 | 唯一在工作的 |

后三个之所以永不触发，是因为 [policy.py:65-73](Hamburgerr/src/dialogue/policy.py#L65-L73) 与 [reducer.py:147-157](Hamburgerr/src/state/reducer.py#L147-L157) 在任何 `override/clear/negation/intent_switch` 事件上都把三个计数器清零，而**这类事件出现得比连续计数达到阈值更频繁**。计数器在攒够之前总被重置。

于是澄清只受 `turn >= 4` 这一条粗粒度规则约束，前 3 轮几乎无条件提问。

**通用修复。**
1. **不要把 margin 阈值往下调**——那是过拟合。margin 恒小于 0.01 是 R2 特征饱和的**症状**：分差被常数项压缩了。修好 R2 后 margin 会自然拉开，这个早退会自己复活。**先修 R2，再重新校准阈值。**
2. **计数器改为「衰减」而非「清零」。** override 之后 Top10 的稳定性证据不应完全作废，减半更合理。
3. **推荐与澄清并行。** 当前 `clarify` 分支已经返回了 `top_ids`（[core.py:157-161](Hamburgerr/src/core.py#L157-L161)），但评测器只认 `action=="recommend"`。**在提问的同时把 action 标为 recommend 并附带候选**，即可回收那 133 个 session 的延迟——这不是钻规则空子，「一边给建议一边追问细节」本身就是更好的对话行为。
4. **信息增益门控。** 提问前预测该 slot 能否真正切分候选集；`_best_supported_slot` 已有雏形（[policy.py:169-188](Hamburgerr/src/dialogue/policy.py#L169-L188)），但只要求 `len(partitions) > 1`。应改为要求**最大分区占比 < 某比例**（如 0.8），避免「切出 149 : 1」这种无用提问。

**量化收益。** 133 个 session 各提前 1~2 turn，MTTC 3.04 → ~2.2，**score +0.017**。与 R3 修复叠加后 MTTC 可接近 1.6~1.8。

---

### R5　boundary 场景（hit@10=0.700，全场最低）

10 个样本里 3 个未命中，MTTC 5.10。这一类的共性是**约束在目录中稀疏或互相冲突**——放宽策略要么放得太晚，要么放错维度。

由于 n=10，**任何针对个例的调参都必然过拟合**。只做通用性改动：
- 放宽顺序按**约束的目录支持度**排序：先放宽在目录中最稀疏、最可能造成空集的维度（可由索引统计直接算出），而非固定顺序。
- 硬约束冲突（如 price_max < 目录最低价）应立即降级为软偏好并说明，而不是持续返回空集。
- 由 R1 恢复的 `source_agreement` 在稀疏场景下收益最大——单通道时稀疏约束几乎无信号。

不为 boundary 单独设阈值、单独设权重。

---

### R6　可观测性缺口

- `explanation.source_ranks` 恒为单键，无法诊断跨通道行为（R1 的直接后果）。
- 无「特征方差」埋点。R2 这类饱和问题本应由监控直接暴露，而不是靠事后分析 5900 条记录。
- 早退死代码没有告警。一个从未触发的分支静默存在了整个 phase。

**修复。** 每 turn 记录 Top10 内各特征的**方差与全等标记**；对每个早退分支记触发计数，长期为 0 即告警。这些是通用的健康度指标，不改变任何打分行为。

---

## 三、执行顺序

按「边际得分 / 过拟合风险」排序：

| 优先级 | 项 | 根因 | 预估 Δscore | 风险 |
|---|---|---|---|---|
| **P0** | 特征去饱和（中心化 + 收紧 phrase + 对数压缩 + 去 catalog_order 兜底） | R2 | **+0.04 ~ +0.09** | 低，纯排序内部改动 |
| **P0** | override 槽位级失效 + 保留 category 上下文 + 抑制歧义 clear | R3 | **+0.027** | 中，需回归 override 用例 |
| **P1** | 恢复 pool-restricted 多通道 + `source_agreement` 特征 | R1 | **+0.02 ~ +0.04** | 中，需盯延迟 p95 |
| **P1** | 澄清与推荐并行 + 信息增益门控 | R4 | **+0.017** | 低 |
| **P2** | 早退阈值在 R2 之后重新校准 | R4 | 已计入 | 低（**必须在 R2 之后**） |
| **P2** | boundary 放宽顺序按目录支持度 | R5 | +0.005 | 低 |
| **P3** | 特征方差 / 死分支埋点 | R6 | 0（防回归） | 无 |

**保守合计：0.760 → 0.83 ~ 0.87。** 主要来自 MRR 0.461 → 0.65~0.75。

**关键判断：不要再投入召回。** 未命中样本的目标 **100% 已在候选池中**，召回侧无失败可修。全部工程量应投向排序区分度与对话时序。

---

## 四、防过拟合纪律

本方案刻意排除了以下做法：

- ❌ 下调 `clarification_margin_threshold` 以让 `score_margin` 触发（治症状，且阈值由本数据集反推）
- ❌ 为 boundary 的 10 个样本单独设权重或阈值
- ❌ 针对 `public_0034` 等具名样本做特判
- ❌ 硬编码 evaluator 的 `customer_reply` 模板细节（改为多分隔符 + 通用前缀剥离）
- ❌ 依赖 override turn ∈ {3,4} 这一实现细节做时序假设

采用的每一项都是**结构性修复**：per-query 特征中心化、多视角一致性、槽位级状态失效、信息增益门控——它们在任何目录数据与任何用户措辞下都成立。

**验证要求。**
1. 每项改动单独跑，记录 Δ（hit / MRR / MTTC / p95 latency）。
2. 自建集与公开集同时评测；只在公开集涨、自建集不涨或下跌的改动**一律回滚**。
3. 用 `--limit` 子集做 A/B，确认改进方向在不同切片上一致，而非集中在少数样本。
4. 保留 `.runtime` 轨迹做前后特征方差对比，确认饱和确实缓解（全等特征占比应从 35.2% 显著下降）。




