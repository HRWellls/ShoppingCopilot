# TechJam 2026 — Shopping Copilot 题目分析与执行方案

> 题目：**Shopping Copilot: AI Conversational Search and Recommendations**  
> 当前阶段：选题已确定，目标是先完成 baseline → 理解 evaluator → 做出第一版可运行 Agent → 再围绕 TechnicalScore 持续优化。  
> 日期：2026-08-25

---

## 1. 先说结论：这个题目到底要我们做什么？

一句话：

> **做一个能够通过多轮自然语言对话，理解用户购买/浏览意图，并从 50,000 个 Amazon 商品中逐步缩小候选集，最终把用户真正会购买的商品排到前面，同时尽量用更少的对话轮数完成推荐的 Shopping Agent。**

它**不是**让我们做一个漂亮的电商网站，也不是让我们训练一个大模型。

真正的比赛核心是：

```text
用户对话
   ↓
理解当前意图
   ↓
维护用户当前需求状态
   ↓
选择 Buying / Browsing 路径
   ↓
从 50,000 商品中检索候选
   ↓
混合排序 / LLM Reranking
   ↓
判断是否已经足够确定
   ├── 是 → 推荐商品
   └── 否 → 主动追问
   ↓
下一轮对话
   ↓
更新状态并重新检索
   ↓
最终找到真实购买商品
```

因此，这道题本质上是：

**Conversational Search + Information Retrieval + Recommendation + Agent State Management + Ranking Optimization**

而不是传统意义上的“做一个聊天机器人”。

---

# 2. 比赛真正考察的核心

题目表面上有很多要求，但可以压缩成 4 个核心问题。

## 2.1 我应该搜什么？

对应：

**Intent Detection / Intent Routing**

用户可能说：

> I need black running shoes under $100.

这是一个非常明确的 **Buying Intent**。

也可能说：

> What should I wear for a summer wedding?

这是 **Browsing Intent**。

两者不能使用完全一样的搜索策略。

### Buying

重点：

- 价格
- 品类
- 颜色
- 尺码
- 品牌
- 材质
- 使用场景
- 明确排除条件

特点：

> **宁可少，也要精准。**

### Browsing

重点：

- 场景理解
- 语义扩展
- 跨类别匹配
- 多样性
- 推荐探索

特点：

> **宁可扩大候选集，也不要过早锁死。**

所以第一层架构应该是：

```text
                User Query
                    │
             Intent Router
              /           \
         Buying          Browsing
            │                │
     Hard Filter        Dense Retrieval
            │                │
            └──────┬─────────┘
                   ↓
             Hybrid Retrieval
                   ↓
              Re-ranking
```

---

# 3. 为什么题目特别强调 Multi-Turn？

因为它不是：

```text
用户：给我推荐跑鞋
Agent：xxx
```

而可能是：

```text
User:
I need shoes.

Agent:
What type of shoes are you looking for?

User:
Running shoes.

Agent:
Any budget?

User:
Under $100.

Agent:
Do you have a preferred color?

User:
Black. Actually, white is fine too.
```

这里 Agent 必须记住：

```json
{
  "category": "running shoes",
  "budget_max": 100,
  "color": "white"
}
```

更重要的是：

## 用户可能修改之前的信息

例如：

```text
User:
I want black shoes.

User:
Actually, make them white.
```

不能变成：

```json
{
  "color": ["black", "white"]
}
```

而应该变成：

```json
{
  "color": "white"
}
```

这就是题目所说的：

> Intent Override / slot erasure and rewriting

所以我们必须实现一个：

**Conversation State Machine**

---

# 4. 这道题最关键的一个机制：什么时候应该问用户？

这是我认为这道题非常值得重点做的地方。

例如：

```text
User:
I want some shoes.
```

候选商品可能有：

```text
running shoes
dress shoes
boots
sandals
sneakers
heels
...
```

如果 Agent 直接搜索并返回 Top 10，很可能非常差。

题目明确要求：

> Proactive Guidance

也就是说：

**当搜索空间太大时，不要继续盲搜，而应该主动提出一个最有价值的问题。**

例如：

> Are you looking for running shoes, casual shoes, or formal shoes?

而不是：

> Could you provide more details?

后者信息价值很低。

---

# 5. 我们应该把“追问”理解成 Information Gain

这是非常值得作为比赛亮点的方向。

假设目前候选：

```text
10,000 products
```

我们可以选择问：

### 问题 A

> What color do you prefer?

可能从：

10,000 → 7,000

### 问题 B

> What type of shoes are you looking for?

可能：

10,000 → 1,500

那么显然：

**问题 B 更有价值。**

因此可以设计一个：

```text
Clarification Question Selector
```

目标：

> **选择最能减少候选空间的问题。**

可以把它理解成：

```text
Candidate Entropy
        ↓
选择一个 slot
        ↓
预计候选空间下降最多
        ↓
生成 clarification question
```

这同时会直接影响：

**MTTC（Mean Turns to Conversion）**

---

# 6. 评价指标到底意味着什么？

题目给了：

- Hit Rate@K
- MRR
- Top-K Hit Rate
- MTTC
- TechnicalScore

可以简单理解为：

## 6.1 Hit Rate@10

真实购买商品有没有进入 Top 10？

例如：

```text
Top 10:
A
B
C
D
E
F
G
H
I
J

真实购买商品 = G
```

那么：

```text
Hit@10 = 1
```

如果完全没有：

```text
Hit@10 = 0
```

---

## 6.2 MRR

真实商品排得越靠前越好。

例如：

```text
真实商品排名 #1
MRR = 1

排名 #2
MRR = 1/2

排名 #5
MRR = 1/5

排名 #10
MRR = 1/10
```

因此：

> **不仅要找到，还要把它排到最前面。**

---

## 6.3 MTTC

Mean Turns to Conversion。

核心是：

> **找到正确商品平均需要多少轮对话？**

例如：

方案 A：

```text
第 1 轮 → 找到
```

方案 B：

```text
第 1 轮 → 问
第 2 轮 → 问
第 3 轮 → 找到
```

显然 A 更优秀。

因此：

> **不能无限追问。**

---

# 7. 这意味着我们的优化目标不是单纯 Retrieval Accuracy

真正目标应该是：

```text
             ┌── Recall
             │
             ├── Precision
TechnicalScore
             │
             └── Conversation Efficiency
```

即：

> **正确 + 排名靠前 + 少问问题**

这也是为什么题目非常适合做 Agent。

---

# 8. 推荐的总体系统架构

我建议第一版直接按照下面的结构设计。

```text
                    ┌─────────────────┐
                    │  User Message   │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Intent Router   │
                    └────────┬────────┘
                             ↓
              ┌──────────────┴──────────────┐
              ↓                             ↓
        Buying Track                  Browsing Track
              ↓                             ↓
       Hard Constraints               Semantic Expansion
              ↓                             ↓
       Keyword Retrieval               Dense Retrieval
              └──────────────┬──────────────┘
                             ↓
                    Hybrid Candidate Pool
                             ↓
                    Candidate Filtering
                             ↓
                    Candidate Ranking
                             ↓
                     Confidence Check
                       /           \
                     High           Low
                      ↓              ↓
                 Recommend       Clarify
                      ↓              ↓
                 Conversation State
                         ↑
                         └──────────────
```

---

# 9. 第一阶段千万不要直接做“超级 Agent”

最重要的策略：

> **先跑通官方 baseline，再逐步替换模块。**

第一阶段目标不是拿高分，而是回答：

1. 项目怎么启动？
2. Agent API 是什么？
3. 输入是什么？
4. 输出是什么？
5. evaluator 怎么调用？
6. baseline 得分是多少？
7. 每个 session 的过程是什么？

---

# 10. 第一件事：拿到官方 Participant Kit

需要重点获取：

- Participant Repository
- Participant Kit Release
- 50,000 product catalog
- 200 public development sessions
- Starter Agent
- Local Evaluator
- API contract
- Evaluation configuration
- Baseline result
- SHA256 checksum

官方仓库：

https://github.com/TechJam2026/techjam-conversational-search

Participant Kit：

https://github.com/TechJam2026/techjam-conversational-search/releases/tag/participant-kit

---

# 11. 你们团队当前应该准备哪些技术资源？

## 11.1 必需资源

### 硬件

一台能够运行 Python 的电脑即可开始。

第一阶段：

- MacBook
- Linux
- Windows + WSL

都可以。

因为题目明确要求：

> in-memory

而数据规模只有：

```text
50,000 products
```

并不需要 GPU 集群。

---

## 11.2 Python 环境

建议：

```text
Python 3.11+
```

推荐使用：

```text
uv
```

或者：

```text
conda
```

项目环境建议：

```text
Python
├── pandas
├── numpy
├── scikit-learn
├── rank_bm25
├── sentence-transformers
├── torch
├── transformers
└── official evaluator dependencies
```

具体依赖必须以官方 participant kit 为准，不要现在提前锁版本。

---

# 12. 向量模型怎么选？

题目允许：

- dense retrieval
- local models
- external APIs

第一版不要急着调用昂贵的 API。

建议先测试：

```text
Sentence Transformers
```

例如：

```text
all-MiniLM-L6-v2
```

或者更强的 embedding model。

不过最终选择应该基于：

```text
Recall@10
+
latency
+
memory
```

而不是只看模型榜单。

---

# 13. 是否需要 LLM？

答案：

**不一定。**

官方明确说：

> A paid LLM is not required.

所以不要一开始就认为：

```text
GPT-5 = 高分
```

这很可能是错误路线。

LLM 最适合放在：

```text
Intent Understanding
Slot Extraction
Semantic Ranking
Clarification Generation
```

而不是让 LLM 直接：

```text
从 50,000 商品里凭感觉挑一个
```

---

# 14. 推荐的 LLM 使用方式

如果团队有 API：

可以让 LLM 输出结构化状态：

```json
{
  "intent": "buying",
  "category": "running shoes",
  "budget_max": 100,
  "color": "black",
  "gender": null,
  "brand": null
}
```

而不是：

```text
User: ...
LLM: I think this user probably wants...
```

结构化输出更容易：

- Debug
- Evaluation
- Override
- Slot update
- Reproduce

---

# 15. Product Catalog 应该怎么处理？

50,000 products 不算大。

建议预处理成：

```text
Product
├── ASIN
├── title
├── description
├── category
├── price
├── brand
├── features
└── searchable_text
```

然后生成：

```text
searchable_text =
title
+ category
+ brand
+ description
+ features
```

再建立：

### BM25 Index

用于：

```text
精准关键词
```

### Vector Index

用于：

```text
语义搜索
```

---

# 16. 为什么必须 Hybrid Retrieval？

假设用户：

> Nike Air Max black running shoes

BM25 很强。

因为：

```text
Nike
Air Max
black
running shoes
```

都是重要关键词。

但如果用户说：

> shoes for a beach vacation

这时候 exact keyword 不一定能找到最好的结果。

Vector search 更适合：

```text
beach vacation
↓
sandals
↓
lightweight shoes
↓
water-friendly footwear
```

所以应该：

```text
BM25
 +
Vector Search
 +
Category Filter
 +
Metadata Filter
```

然后融合。

---

# 17. 推荐的 Retrieval Score

可以先做一个简单版本：

```text
score =
    w1 * bm25_score
  + w2 * vector_score
  + w3 * category_score
  + w4 * metadata_match
```

例如：

```text
Buying:

BM25              0.35
Vector            0.25
Category          0.20
Hard constraints  0.20
```

Browsing：

```text
BM25              0.20
Vector            0.50
Category          0.15
Metadata          0.15
```

注意：

> 这些权重只是起点，不是最终答案。

真正应该通过 200 个 public sessions 做实验。

---

# 18. 一个非常重要的优化：Hard Constraints 不应该只是加分

例如：

```text
User:
under $100
```

价格应该是：

```text
price <= 100
```

而不是：

```text
price <= 100 → score + 0.2
```

因为用户说的是：

> **硬约束**

违反就应该直接淘汰。

所以：

```text
Hard Filter
      ↓
Soft Ranking
```

比：

```text
所有东西一起加权
```

更合理。

---

# 19. Intent Router 怎么实现？

可以从简单到复杂。

## Version 1

规则：

```python
if explicit_buying_signals:
    intent = "buying"
else:
    intent = "browsing"
```

例如：

Buying：

- under $X
- I need
- buy
- looking for
- size
- color
- brand
- budget

Browsing：

- recommend
- ideas
- what should I wear
- show me
- something for
- options

---

## Version 2

用小模型 / embedding classifier。

---

## Version 3

让 LLM 做 structured classification。

最终可以：

```text
Rule
+
LLM
+
Conversation State
```

共同决定 intent。

---

# 20. Conversation State 应该怎么设计？

建议：

```python
class SessionState:
    intent
    slots
    history
    candidates
    last_query
    turn_count
    confidence
```

slots：

```python
{
    "category": None,
    "brand": None,
    "price_min": None,
    "price_max": None,
    "color": None,
    "size": None,
    "material": None,
    "occasion": None,
    "gender": None
}
```

---

# 21. Slot Update 是整个项目的核心之一

例如：

```text
Turn 1:
I need running shoes.
```

状态：

```json
{
  "category": "running shoes"
}
```

Turn 2：

```text
Under $100.
```

变成：

```json
{
  "category": "running shoes",
  "price_max": 100
}
```

Turn 3：

```text
Actually, make it Nike.
```

变成：

```json
{
  "category": "running shoes",
  "price_max": 100,
  "brand": "Nike"
}
```

Turn 4：

```text
Actually, any brand is fine.
```

必须：

```json
{
  "category": "running shoes",
  "price_max": 100,
  "brand": null
}
```

这就是：

**Slot Override**

---

# 22. Slot Decay 可以作为进阶创新

题目明确提到：

> slot decay over time

可以设计：

```text
slot confidence
```

例如：

```text
recent preference      1.0
one turn ago           0.8
two turns ago          0.6
three turns ago        0.4
```

但要注意：

**明确的 hard constraint 不应该随便 decay。**

例如：

```text
My budget is definitely under $100.
```

不能因为过了几轮就忘掉。

因此可以区分：

```text
Hard Constraint
Soft Preference
Contextual Preference
```

---

# 23. Candidate Pool 应该动态变化

不要每轮：

```text
50,000 → Search → 50,000
```

而应该：

```text
Turn 1
50,000
   ↓
8,000

Turn 2
8,000
   ↓
1,500

Turn 3
1,500
   ↓
200

Turn 4
200
   ↓
Top 20
```

这样：

- 速度更快
- ranking 更稳定
- LLM 成本更低

---

# 24. 但不要过早截断

这是一个重要 trade-off。

如果第一轮就：

```text
50,000 → Top 10
```

那么真实商品如果没进 Top 10：

> 后面再怎么优化都救不回来。

所以建议：

```text
Retrieval Recall Stage
    Top 100~500

       ↓

Filtering

       ↓

Ranking

       ↓

Top 10
```

即：

> **Recall stage 要宽，ranking stage 要精。**

---

# 25. Reranking 应该怎么做？

最终 candidate：

```text
Top 100
```

然后再进行：

```text
Semantic Reranking
```

可以使用：

### 方法 A

规则评分。

### 方法 B

Cross Encoder。

### 方法 C

LLM ranking。

### 方法 D

Hybrid。

如果算力允许，我更建议：

```text
BM25 + Dense
       ↓
Top 100
       ↓
Cross Encoder / lightweight reranker
       ↓
Top 20
       ↓
LLM / rule-based final ranking
       ↓
Top 10
```

---

# 26. LLM 不应该直接处理 50,000 商品

这是一个非常重要的工程原则。

错误：

```text
50,000 products
        ↓
LLM
```

正确：

```text
50,000
 ↓
BM25 / Vector
 ↓
500
 ↓
Filter
 ↓
100
 ↓
Rerank
 ↓
20
 ↓
LLM
 ↓
10
```

这样才能控制：

- token
- latency
- cost
- reliability

---

# 27. Proactive Clarification 怎么实现？

我们可以定义：

```python
if candidate_count > threshold:
    ask_question()
```

例如：

```text
candidate_count > 1000
```

触发 clarification。

但更好的版本：

```text
candidate_count
+
candidate entropy
+
slot missingness
+
ranking confidence
```

共同决定是否追问。

---

# 28. Clarification Question 选择

可以计算：

```text
Question Value
=
Expected Candidate Reduction
/
Conversation Cost
```

例如：

```text
Question: What color?
Reduction = 20%

Question: What's your budget?
Reduction = 70%

Question: Which brand?
Reduction = 10%
```

那么应该问：

> What's your budget?

这就是可以在比赛 presentation 里重点讲的：

**Information-Gain-driven Conversational Search**

---

# 29. 最值得做的创新方向

如果我们是一个普通 hackathon 团队，我不会建议同时做十几个复杂模块。

我更建议集中做：

## “Information-Gain Conversational Retrieval Agent”

核心卖点：

> Agent doesn't just search.  
> It decides **what to search, when to search, and what to ask next.**

整个系统：

```text
Understand
    ↓
Retrieve
    ↓
Measure uncertainty
    ↓
Ask highest-value question
    ↓
Update state
    ↓
Retrieve again
    ↓
Convert
```

这比：

> “我们用了 GPT + vector DB + BM25”

有明显更强的故事性。

---

# 30. 比赛评分标准下，我们应该怎么分配精力？

评分：

| 指标 | 权重 | 我们应该做什么 |
|---|---:|---|
| Technical Execution | 35% | 架构、代码、稳定性、Evaluator |
| Innovation | 20% | Information Gain / Dynamic Agent |
| Impact | 20% | 电商转化价值 |
| Feasibility | 15% | 本地运行、低成本、可复现 |
| Presentation | 10% | Demo / Story |

因此：

### 第一优先级

**Technical Execution**

### 第二优先级

**Evaluation Score**

### 第三优先级

**Innovation**

不要为了“看起来很 AI”而牺牲实际分数。

---

# 31. 推荐团队分工

如果是 3~4 人团队，可以这样：

## A — Retrieval Engineer

负责：

- BM25
- Vector Search
- Hybrid Retrieval
- Candidate filtering
- Reranking
- Index optimization

---

## B — Agent / LLM Engineer

负责：

- Intent Router
- Slot Extraction
- State Machine
- Slot Override
- Clarification
- LLM prompt

---

## C — Evaluation / Research

负责：

- evaluator
- baseline
- ablation
- metric tracking
- error analysis
- parameter tuning

---

## D — Integration / Demo

负责：

- Agent architecture
- API
- logging
- reproducibility
- README
- Demo video
- Devpost
- final presentation

如果只有 3 人：

```text
A: Retrieval
B: Agent
C: Evaluation + Integration
```

---

# 32. 第一阶段项目目录建议

建议：

```text
techjam-shopping-copilot/
│
├── data/
│   ├── catalog/
│   └── sessions/
│
├── src/
│   ├── agent.py
│   ├── router.py
│   ├── state.py
│   ├── retrieval/
│   │   ├── bm25.py
│   │   ├── dense.py
│   │   └── hybrid.py
│   │
│   ├── ranking/
│   │   ├── rules.py
│   │   └── reranker.py
│   │
│   ├── dialogue/
│   │   ├── clarification.py
│   │   └── slot_manager.py
│   │
│   └── utils/
│
├── experiments/
│   ├── baseline/
│   ├── hybrid/
│   ├── reranking/
│   └── ablation/
│
├── scripts/
│   ├── build_index.py
│   └── evaluate.py
│
├── tests/
│
├── README.md
├── requirements.txt
└── config.yaml
```

具体接口以官方 starter agent 为准。

---

# 33. 第一周建议怎么推进？

## Day 1 — 完全理解官方代码

目标：

```text
能运行 baseline
```

任务：

- clone repository
- 安装环境
- 下载 participant kit
- checksum verification
- 跑 starter agent
- 跑 evaluator
- 记录 baseline

输出：

```text
Baseline:
Hit@10 = ?
MRR = ?
MTTC = ?
TechnicalScore = ?
```

---

## Day 2 — 分析数据

重点研究：

```text
catalog schema
session schema
conversation format
target product
```

回答：

> 用户每一轮输入到底长什么样？

> evaluator 怎么知道正确商品？

> 最终购买记录如何定义？

---

## Day 3 — 建立 Error Analysis

对 200 public sessions 分类：

```text
Failure Type
├── Retrieval miss
├── Wrong intent
├── Wrong slot extraction
├── Wrong filtering
├── Wrong ranking
├── Too many turns
└── Clarification failure
```

这是非常重要的一步。

---

# 34. Day 4 — Hybrid Retrieval

实现：

```text
BM25
+
Dense Retrieval
```

先不做复杂 Agent。

比较：

```text
BM25
Dense
Hybrid
```

分别测试：

```text
Recall@10
Recall@50
Recall@100
MRR
```

如果 Hybrid 没有提升：

> 不要继续堆模型，先分析为什么。

---

# 35. Day 5 — Intent Routing

实现：

```text
Buying
Browsing
```

然后比较：

```text
single pipeline
vs
dual pipeline
```

这就是一个非常好的 ablation。

---

# 36. Day 6 — State Machine

实现：

```text
slot extraction
slot update
slot override
history
turn count
```

重点测试：

```text
A → B
A → B → A
A → remove A
A → change A
```

---

# 37. Day 7 — Clarification

先做简单版本：

```text
if candidate_count > threshold:
    ask clarification
```

然后升级：

```text
choose missing slot with maximum expected reduction
```

---

# 38. 第二周应该做什么？

进入：

**Optimization**

主要做：

### Experiment 1

BM25 vs Dense vs Hybrid

### Experiment 2

不同 embedding model

### Experiment 3

不同 candidate size：

```text
Top 50
Top 100
Top 200
Top 500
```

### Experiment 4

不同 reranker

### Experiment 5

是否使用 LLM

### Experiment 6

不同 clarification strategy

### Experiment 7

不同 intent router

### Experiment 8

slot decay / override

所有实验都记录：

```text
Hit@10
MRR
MTTC
TechnicalScore
Latency
```

---

# 39. 建议建立实验表

例如：

| Version | Retrieval | Reranker | Intent | Clarification | Hit@10 | MRR | MTTC |
|---|---|---|---|---|---:|---:|---:|
| V0 | BM25 | None | None | None | | | |
| V1 | Dense | None | None | None | | | |
| V2 | Hybrid | None | Rule | None | | | |
| V3 | Hybrid | CrossEncoder | Rule | None | | | |
| V4 | Hybrid | CrossEncoder | LLM | Rule | | | |
| V5 | Hybrid | CrossEncoder | LLM | InfoGain | | | |

最终：

> **不要凭感觉决定最终方案。**

让 evaluator 决定。

---

# 40. 最容易踩的坑

## 坑 1：一开始就做 UI

题目明确：

> UI/UX Development out of scope

所以：

**不要花大量时间做网页。**

Demo 可以做 CLI / API walkthrough。

---

## 坑 2：一开始就训练模型

题目不要求：

> full-parameter fine-tuning

也没有必要。

优先级：

```text
Retrieval
>
State
>
Ranking
>
Clarification
>
LLM
>
Fine-tuning
```

---

## 坑 3：直接让 LLM 选商品

这是典型的：

```text
LLM hallucination
```

应该：

```text
retrieval → candidate set → ranking
```

---

## 坑 4：只优化 MRR

如果真实商品根本没进入 candidate pool：

> Reranker 再强也没用。

所以先：

**Recall**

再：

**Ranking**

---

## 坑 5：问太多问题

MTTC 会变差。

Agent 应该：

> ask only when expected information gain is worth the extra turn.

---

# 41. 最终 Demo 应该怎么展示？

由于这是 backend/NLP track：

> 不需要 UI。

推荐 Demo：

```text
Terminal / API

User:
I need running shoes.

Agent:
Are you looking for a specific budget range?

User:
Under $100.

Agent:
Any preferred brand?

User:
Nike.

Agent:
Here are the best matches...
```

同时显示：

```text
Turn: 3
Intent: Buying
Candidates: 137
Top result: ASIN XXXXX
Confidence: 0.94
```

然后展示 evaluator：

```text
Hit@10: 0.xx
MRR: 0.xx
MTTC: x.xx
TechnicalScore: xx.xx
```

这样比单纯展示聊天界面更符合题目。

---

# 42. Demo 最好展示一个“失败 → 优化”的故事

例如：

### Baseline

```text
BM25
Hit@10 = 0.61
MRR = 0.34
MTTC = 4.1
```

### Our system

```text
Hybrid Retrieval
+
Intent Routing
+
State Tracking
+
Information Gain

Hit@10 = 0.78
MRR = 0.56
MTTC = 2.7
```

这会非常有说服力。

注意：

**上面的数字只是演示格式，不能当成实际结果。**

---

# 43. 你们现在最应该准备的资源清单

## 必须马上准备

- [ ] GitHub Participant Repository
- [ ] Participant Kit
- [ ] 50,000 product catalog
- [ ] 200 public sessions
- [ ] Starter Agent
- [ ] Local evaluator
- [ ] API contract
- [ ] Evaluation config
- [ ] Baseline result
- [ ] SHA256 checksum

---

## Python / ML

- [ ] Python 环境
- [ ] pandas
- [ ] numpy
- [ ] scikit-learn
- [ ] BM25 implementation
- [ ] sentence-transformers
- [ ] PyTorch（如使用本地 embedding/reranker）
- [ ] 可选 LLM API

---

## 工程工具

- [ ] Git
- [ ] GitHub
- [ ] VSCode
- [ ] Python virtual environment
- [ ] pytest
- [ ] experiment logging

---

## 如果使用外部 LLM

- [ ] API Key
- [ ] 费用预算
- [ ] rate limit
- [ ] timeout
- [ ] fallback strategy

**不要把 API key 上传 GitHub。**

---

# 44. 我建议你们不要一开始花钱买很多 API

第一版完全可以：

```text
BM25
+
Local Embedding
+
Rule-based Intent
+
Rule-based State
+
Rule-based Ranking
```

先跑：

```text
200 public sessions
```

然后找到瓶颈。

只有当：

```text
Retrieval 已经不错
```

但是：

```text
Intent / Ranking / Clarification
```

明显成为瓶颈时，再加入 LLM。

---

# 45. 最终推荐技术路线

我建议最终目标是：

```text
                ┌───────────────────┐
                │   User Message    │
                └─────────┬─────────┘
                          ↓
                ┌───────────────────┐
                │ Intent + Slot     │
                │ Extraction        │
                └─────────┬─────────┘
                          ↓
                ┌───────────────────┐
                │ Conversation      │
                │ State Manager      │
                └─────────┬─────────┘
                          ↓
               ┌────────────────────┐
               │ Buying / Browsing  │
               │ Router             │
               └─────────┬──────────┘
                         ↓
            ┌───────────────────────────┐
            │ Hybrid Retrieval          │
            │ BM25 + Dense + Metadata   │
            └─────────────┬─────────────┘
                          ↓
                  Candidate Pool
                          ↓
             ┌────────────────────────┐
             │ Hard Constraint Filter │
             └────────────┬───────────┘
                          ↓
                   Top 100~200
                          ↓
             ┌────────────────────────┐
             │ Semantic Reranking     │
             └────────────┬───────────┘
                          ↓
                      Top 20
                          ↓
                Confidence Check
                    /          \
                   /            \
                High             Low
                 ↓                ↓
            Recommend       InfoGain Question
                 ↓                ↓
                 └──────→ Next Turn
```

---

# 46. 最值得包装成比赛亮点的三个点

## Highlight 1 — Dual-Track Search

不是所有用户都应该用同一个 search pipeline。

```text
Buying → Precision
Browsing → Diversity
```

---

## Highlight 2 — Information-Gain Clarification

Agent 不会无意义地问问题。

它会：

```text
分析候选集
↓
判断不确定性
↓
寻找最有价值的 missing slot
↓
主动提问
```

---

## Highlight 3 — Runtime Adaptive Memory

Agent 会持续更新：

```text
Current Session State
+
User Preference
+
Intent
+
Constraints
```

并能够：

```text
add
modify
remove
decay
```

这些信息。

---

# 47. 最终不要把项目讲成“一个电商聊天机器人”

建议把项目定位为：

> **An adaptive conversational retrieval agent that learns what to search and what to ask next.**

中文可以说：

> **一个能够动态决定“搜什么、怎么搜、什么时候问用户”的智能购物检索 Agent。**

这个定位比：

> AI Shopping Assistant

更符合题目，也更有技术深度。

---

# 48. 你们现在的具体行动顺序

不要同时做所有事情。

严格按照：

```text
STEP 1
↓
拿官方代码和 Participant Kit

STEP 2
↓
跑通 Starter Agent

STEP 3
↓
跑通 Local Evaluator

STEP 4
↓
记录 Baseline

STEP 5
↓
理解 catalog / session schema

STEP 6
↓
分析 200 个 public sessions

STEP 7
↓
BM25 baseline

STEP 8
↓
Dense Retrieval

STEP 9
↓
Hybrid Retrieval

STEP 10
↓
Intent Router

STEP 11
↓
Conversation State

STEP 12
↓
Slot Override

STEP 13
↓
Reranker

STEP 14
↓
Clarification

STEP 15
↓
Information Gain

STEP 16
↓
Ablation + Optimization

STEP 17
↓
Final Agent

STEP 18
↓
Demo + README + Devpost
```

---

# 49. 今天就应该完成什么？

如果你们今天刚确定这个题目，我建议**不要今天就开始写复杂算法**。

今天的目标只有 5 个：

### ① 把官方 repo 跑起来

```text
git clone
↓
install
↓
run
```

### ② 找到 Agent 的入口

搞清楚：

```text
input
→
agent
→
output
```

### ③ 跑官方 evaluator

得到：

```text
Baseline Score
```

### ④ 把数据 schema 搞明白

尤其：

```text
catalog
session
target product
```

### ⑤ 全队统一理解架构

最终每个人都应该能解释：

```text
User
 ↓
Intent
 ↓
State
 ↓
Retrieval
 ↓
Ranking
 ↓
Clarification
 ↓
Conversion
```

---

# 50. 明天开始的第一份实验报告

建议建立：

```text
experiments/baseline.md
```

内容：

```text
## Baseline

Model:
BM25 starter agent

Catalog:
50,000 products

Sessions:
200 public sessions

Results:

Hit@10:
MRR:
MTTC:
TechnicalScore:

Failure Analysis:

1.
2.
3.

Next Experiment:

Hybrid Retrieval
```

之后每一次修改都记录。

---

# 51. 一个非常重要的比赛策略

你们最终面对的是：

```text
800 private sessions
```

所以：

> **不要针对 200 public sessions 过拟合。**

如果发现：

```text
某个规则让 public score +10%
```

但这个规则只是针对某一类 query：

> 要非常谨慎。

更好的方法：

```text
public sessions
      ↓
development
      ↓
ablation
      ↓
general principles
      ↓
final system
```

而不是：

```text
看到一个 case
↓
写一个 if
↓
score +
↓
继续写 if
```

否则最后会变成：

```python
if query == "...":
    ...
```

这不是一个可泛化的 Agent。

---

# 52. 最后给你们团队的核心建议

这个题目我认为**非常适合用“工程 + 算法 + Agent”路线来做**。

不要把重点放在：

> “我们用了什么最强模型？”

而应该放在：

> **“我们如何让有限的检索、排序和对话轮次共同服务于最终转化？”**

真正值得优化的是：

```text
                    Conversion
                        ↑
          ┌─────────────┼─────────────┐
          │             │             │
       Recall        Ranking       Dialogue
          │             │             │
       Search        Precision     MTTC
          │             │             │
       BM25/Dense    Reranker     Clarification
          │             │             │
          └─────────────┼─────────────┘
                        │
                 Adaptive Agent
```

最终的核心目标可以浓缩成一句话：

> **Find the right product, rank it high, and ask only the questions that are worth asking.**

---

# Appendix A — 我建议的最终技术栈

| 层 | 推荐方案 |
|---|---|
| Language | Python |
| Retrieval | BM25 + Dense |
| Embedding | Sentence Transformers |
| Filtering | Metadata / rule-based |
| Intent | Rule → lightweight model → LLM |
| State | Python State Machine |
| Ranking | Hybrid score + reranker |
| Clarification | Information Gain |
| LLM | 可选，不是必须 |
| Vector DB | 不需要 |
| UI | 不需要 |
| Evaluation | 官方 Local Evaluator |
| Version Control | Git + GitHub |
| Demo | CLI / API walkthrough |

---

# Appendix B — 最终交付物

你们最终至少需要：

## 1. Devpost Written Description

包括：

- Problem
- Solution
- Architecture
- Tools
- APIs
- Libraries
- Dataset
- Results
- Innovation

## 2. Public GitHub Repository

包括：

- 完整代码
- README
- 安装方式
- 运行方式
- reproduce steps
- limitations
- future improvements
- team contributions

## 3. YouTube Demo Video

重点展示：

```text
真实对话
→
Agent 理解
→
候选检索
→
追问
→
状态更新
→
最终推荐
→
Evaluator Result
```

不需要为了 Demo 额外开发复杂前端。

---

# Appendix C — 我建议你们的 MVP

如果时间紧，最低可行版本应该是：

```text
MVP

BM25
+
Dense Retrieval
+
Buying/Browsing Router
+
Slot State
+
Hard Constraint Filter
+
Simple Reranker
+
Clarification
+
Official Evaluator
```

然后再做：

```text
MVP
 ↓
Information Gain
 ↓
Adaptive Memory
 ↓
LLM Reranking
 ↓
Advanced Optimization
```

**先保证“能跑、能评估、能提升”，再追求“复杂”。**

