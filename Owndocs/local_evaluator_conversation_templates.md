# Local Evaluator 对话输入规则说明

本文说明 `evaluator/local_evaluator.py` 如何生成客户对话输入，供产品与算法同学分析追问体验和后续调优方向。

## 结论

本地评测器不调用外部 API 或大模型来扮演客户。它是一个确定性的 Python 规则模拟器：给定同一条样本、同一份商品目录和同一串 Agent 输出，客户消息会完全一致。

`data/public_set.jsonl` 不保存预写的客户对话。它保存会话种子和公开标签；评测器在运行时结合目标商品目录信息生成每一轮客户消息。

## 输入生成链路

```text
public_set.jsonl
  sample_id + scenario_type + user_profile + ground_truth.parent_asin
                                      |
                                      v
catalog.jsonl 中目标商品的分类、features、details、描述和价格
                                      |
                                      v
生成隐藏 intent card（硬约束、软偏好）和场景行为
                                      |
                                      v
按固定话术模板生成首轮与后续客户消息
                                      |
                                      v
Agent.respond(session_id, user_message, turn, top_k)
```

Agent 在运行时只能收到：

- `reset()` 中的 `user_profile`
- `respond()` 中当前回合的 `user_message`

`ground_truth.parent_asin` 是公开集的本地调试标签，用于驱动模拟器并判定命中；正常的 Agent 逻辑不应读取或利用它。

## 客户话术模板

| 场景或条件 | 客户消息模板 | 动态内容 |
| --- | --- | --- |
| Buying 场景首轮 | `I'm looking for {category}. A key requirement is: {constraint}.` | 商品粗分类、首个硬约束 |
| Browsing 场景首轮 | `I'm looking for {category}, but I'm still exploring.` | 商品粗分类 |
| Boundary 场景首轮 | `I'm looking for {category}, but I'm still exploring.` | 商品粗分类 |
| Intent Override 场景首轮 | `I'm looking for {category}. {old_value}` | 商品粗分类、旧偏好 |
| Intent Override 改口 | `Actually, ignore my earlier preference. What I need is: {new_value}.` | 新硬约束 |
| Boundary 场景第一次有效追问 | `I don't have a preference for {attribute}; please use your judgment.` | Agent 的 `ask_attribute` |
| Agent 未提供 `ask_attribute` | `Those options are not quite right yet. Ask me about one specific attribute.` | 无 |
| 没有可披露的对应偏好 | `I don't have an additional preference for {attribute}.` | Agent 的 `ask_attribute` |
| 有可披露的对应偏好 | `For that, what matters is: {constraint1}; {constraint2}.` | 最多两个尚未披露的约束 |
| Intent Override 的兜底消息 | `Actually, please ignore my earlier preference.` | 无 |

## 变量从哪里来

### category

`category` 来自目标商品的 `categories`。评测器会：

1. 以逗号拆分目录分类字符串。
2. 删除 `Clothing`、`Clothing Shoes & Jewelry` 和 `Clothing, Shoes & Jewelry` 等顶层词。
3. 取剩余项的最后两级，用空格拼接。
4. 若没有结果，使用 `clothing item`。

例如：

```text
["Clothing, Shoes & Jewelry", "Boys", "Jewelry", "Necklaces"]
-> "Jewelry Necklaces"
```

### constraint

评测器会从目标商品生成隐藏的 intent card：

- 在 title、features、details、description、categories、store 中识别预设材质与颜色。
- 收集 `features` 和 `details` 的原始内容。
- 有价格时增加 `budget around ${price}`。
- 清洗空白字符，去重，并截断单项长度。
- 前两个值为 `hard_constraints`，之后最多两个为 `soft_preferences`。

约束的类型由关键词规则判定，支持：`budget`、`material`、`color`、`size`、`style`、`use_case` 和默认的 `feature`。

## 多轮回复规则

Agent 的自然语言问题不会被解析。评测器只读取结构化字段 `ask_attribute`，其允许值为：

```text
category, material, color, size, style, brand, budget, feature, use_case, other, null
```

当 Agent 提问某属性时，模拟客户会从尚未披露的硬约束和软偏好中，找出类型匹配的项目并最多透露两项。没有匹配项时，客户明确表示该属性没有更多偏好。

因此，完整对话取决于 Agent 每回合选择的 `ask_attribute`；但在该选择序列相同的情况下，对话是可复现的。

## 场景差异

- **Buying**：首轮直接给第一个硬约束。
- **Browsing**：首轮仅给粗分类，等待 Agent 发起结构化追问。
- **Intent Override**：先给旧偏好，再在固定的第 3 或第 4 回合切换到新硬约束。切换前即使推荐到目标商品也不会计为命中。
- **Boundary**：第一次带 `ask_attribute` 的追问会得到“没有偏好，请自行判断”；之后按一般规则回复。

Intent Override 的回合表面上从 `[3, 4]` 中随机选择，但随机种子由 `sample_id` 和 `scenario_type` 固定，因此对同一个样本始终一致。

## 对产品与调优的含义

- 用户话术覆盖面很窄且格式固定，重点是从商品原始字段中还原约束，而不是处理开放式自然语言。
- Agent 应始终返回合法的 `ask_attribute`；只写自然语言问题而不填写该字段，不会触发有用的信息披露。
- Browsing 场景应优先询问能有效缩小候选集的结构化属性。
- Boundary 场景第一次提问必然无信息增益，应能基于现有分类、画像和候选商品继续检索或改问。
- Intent Override 需要更新会话状态，丢弃旧偏好并优先处理改口后的新约束。
- 评测匹配只认可完全相等的 `parent_asin`；推荐项必须是目录中有效且去重后的前 10 个 ID。

## 代码位置

- `intent_card()`：从商品字段生成约束。
- `behavior_for()`：生成 Intent Override 的旧偏好、新约束和改口消息。
- `coarse_category()`：生成首轮消息使用的粗分类。
- `initial_message()`：生成首轮客户消息。
- `customer_reply()`：根据 `ask_attribute` 生成后续客户回复。
- `materialize_hidden_fields()`：补全隐藏字段，并以固定随机种子保证可复现。
- `evaluate()`：驱动 10 回合会话、调用 Agent 并评分。
