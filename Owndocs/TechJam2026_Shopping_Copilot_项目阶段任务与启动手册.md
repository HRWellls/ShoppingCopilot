# TechJam 2026 — Shopping Copilot 项目阶段任务与启动手册

> 目标：把比赛从“刚选完题目”推进到“最终提交”，明确每个阶段**要做什么、产出什么、什么时候进入下一阶段**。
>
> 本文**不规定具体算法、模型、检索策略或 Agent 逻辑**。这些属于后续团队讨论、实验和优化的内容。
>
> 题目：**Shopping Copilot: AI Conversational Search and Recommendations**

---

# 一、先看全局：整个项目分成哪些阶段？

建议把项目分成 **8 个阶段**：

```text
阶段 0：团队准备与任务分工
        ↓
阶段 1：获取官方代码 / 数据 / Evaluator，并跑通 Baseline
        ↓
阶段 2：理解比赛数据、接口和评分机制
        ↓
阶段 3：建立第一版可工作的 Agent
        ↓
阶段 4：系统化实验与问题分析
        ↓
阶段 5：方案优化与迭代
        ↓
阶段 6：最终版本冻结与全面测试
        ↓
阶段 7：提交材料、Demo、README、Devpost
        ↓
阶段 8：最终展示与答辩准备
```

其中：

- **阶段 1 是现在最应该立刻开始的阶段**
- **阶段 2 是阶段 1 完成后必须做的基础工作**
- 阶段 3 才开始真正进入“我们自己的方案”
- 阶段 4～5 才是比赛最主要的技术竞争阶段
- 阶段 6 以后尽量不要再大规模改变核心架构

---

# 二、阶段 0：团队准备与项目管理

## 目标

在开始写代码之前，让四个人：

1. 使用同一个代码仓库
2. 使用同一个开发环境规范
3. 知道官方代码在哪里
4. 知道数据在哪里
5. 知道如何运行 evaluator
6. 知道目前谁负责什么
7. 所有重要实验结果能够被记录

---

## 需要完成的事情

### 0.1 确定团队 GitHub 仓库负责人

四个人最好不要各自维护一份代码。

推荐：

```text
官方 Repository
       ↓
团队 Fork
       ↓
Team Repository
       ↓
4 个成员分别 Clone
```

### 推荐做法：Fork，而不是四个人分别直接 Clone 官方仓库

原因：

- 官方仓库作为 upstream 保留
- 团队有自己的 repository
- 四个人可以共同开发
- 可以建立 branch / Pull Request
- 后续可以同步官方更新
- 不会把团队修改直接混入官方仓库
- 最终公开 GitHub repository 时也比较自然

---

## 0.2 推荐的 GitHub 结构

理想情况：

```text
Official Repository
        │
        │ fork
        ↓
Team Repository
        │
 ┌──────┼──────┬──────┐
 ↓      ↓      ↓      ↓
A      B      C      D
clone  clone  clone  clone
```

例如：

```text
官方：
TechJam2026/techjam-conversational-search

团队：
YourTeam/techjam-conversational-search
```

四个人都：

```bash
git clone <团队仓库地址>
```

而不是：

```bash
git clone <官方仓库地址>
```

---

# 三、阶段 1：获取官方代码、数据和评测环境

> **这是你们现在最应该开始做的阶段。**

这一阶段的唯一核心目标：

> **不要急着优化。先确保四个人都能独立运行官方 starter agent 和 evaluator。**

---

# 3.1 先处理官方 GitHub Repository

题目提供：

- Participant repository
- Participant Kit Release

官方仓库：

urlTechJam2026/techjam-conversational-searchhttps://github.com/TechJam2026/techjam-conversational-search

Participant Kit：

urlParticipant Kit Releasehttps://github.com/TechJam2026/techjam-conversational-search/releases/tag/participant-kit

---

## 3.1.1 谁来 Fork？

推荐由：

> **团队中负责 GitHub / Integration 的成员**

创建团队 Fork。

如果你们四个人有 GitHub Organization，最好直接 Fork 到团队 Organization。

如果没有 Organization：

```text
成员 A 的 GitHub
        ↓
Fork 官方仓库
        ↓
成为团队主仓库
        ↓
邀请 B / C / D 为 Collaborator
```

---

## 3.1.2 四个人应该怎么 Clone？

Fork 完以后：

**四个人全部 Clone 团队仓库。**

例如：

```bash
git clone https://github.com/YOUR_TEAM/techjam-conversational-search.git
```

然后：

```bash
cd techjam-conversational-search
```

---

## 3.1.3 不建议四个人分别 Fork

不推荐：

```text
官方
├── A fork
├── B fork
├── C fork
└── D fork
```

这样后面非常容易出现：

- 修改分散
- 合并麻烦
- 不知道哪个才是最新版本
- 实验结果无法对应代码版本

更推荐：

```text
官方
  ↓
一个团队 Fork
  ↓
四个人共同开发
```

---

# 3.2 建立 Git 分支规范

不要四个人直接往 `main` 里写。

建议：

```text
main
│
├── develop
│
├── feature/xxx
├── feature/xxx
├── experiment/xxx
└── fix/xxx
```

基本原则：

### main

只保存：

> 稳定、可以运行、准备提交的版本。

### develop

作为日常整合分支。

### feature/*

用于开发具体功能。

例如：

```text
feature/xxx
```

具体名称等你们确定实际工作内容后再定义。

### experiment/*

用于实验。

---

# 3.3 四个人第一次 Clone 后都要做什么？

每个人自己的电脑都需要：

```text
1. Clone repository
2. 创建 Python 环境
3. 安装官方依赖
4. 获取 Participant Kit
5. 检查数据
6. 运行 starter agent
7. 运行 evaluator
```

---

# 3.4 不要现在就修改代码

第一轮：

> **所有人都只运行，不修改。**

原因很简单：

如果一个人：

```text
改了代码
```

另一个人：

```text
环境没装好
```

第三个人：

```text
数据路径不对
```

第四个人：

```text
运行 evaluator 报错
```

那么你们还没有真正开始比赛，就已经不知道问题在哪里。

---

# 3.5 第一阶段需要确认的资源

你们应该找到并确认：

```text
[ ] 官方 repository
[ ] Participant Kit
[ ] Catalog
[ ] Public development sessions
[ ] Starter Agent
[ ] Local evaluator
[ ] API contract
[ ] Evaluation configuration
[ ] Baseline configuration
[ ] SHA256 checksum
```

不要只确认“文件下载成功”。

应该确认：

> **这些东西都能实际运行。**

---

# 3.6 数据完整性检查

题目提供 SHA256 checksum。

建议严格按照官方说明验证。

目的：

> 确保团队四个人拿到的是同一份数据。

尤其不要出现：

```text
A：catalog version A
B：catalog version B
C：catalog version A
D：catalog version C
```

否则之后实验结果没有意义。

---

# 3.7 第一次运行官方 Starter Agent

这一阶段不要研究：

- 为什么 BM25
- 怎么改 ranking
- 怎么加入 embedding
- 怎么加 LLM

只需要回答：

```text
官方代码如何启动？
        ↓
输入是什么？
        ↓
Agent 怎么被调用？
        ↓
输出是什么？
        ↓
Evaluator 怎么调用？
        ↓
最后得到什么指标？
```

---

# 3.8 第一次运行 Local Evaluator

这是阶段 1 的**最重要任务**。

你们必须知道：

```text
如何运行 evaluator
```

以及最终得到：

```text
Hit Rate@10
MRR
Top-K Hit Rate
MTTC
Efficiency
TechnicalScore
```

具体指标以官方 evaluator 实际输出为准。

---

# 3.9 建立 Baseline 记录

第一次成功运行后，不要只在终端看一眼。

必须把结果保存下来。

建议建立：

```text
experiments/
└── baseline/
    ├── README.md
    ├── result.txt
    └── config.*
```

至少记录：

```text
Date:
Code commit:
Dataset version:
Environment:
Starter Agent version:
Evaluator version:

Hit@10:
MRR:
MTTC:
Efficiency:
TechnicalScore:
```

---

# 3.10 阶段 1 的验收标准

只有下面全部完成，才算进入阶段 2：

```text
[ ] 团队 GitHub repository 已建立
[ ] 四个人都已经 Clone 团队 repository
[ ] 四个人都能安装环境
[ ] 四个人都能运行 starter agent
[ ] 四个人都能访问正确的数据
[ ] 四个人都能运行 evaluator
[ ] 至少一个人完整跑通全部 200 public sessions
[ ] Baseline 指标已经记录
[ ] 当前代码 commit 已记录
[ ] 数据版本 / checksum 已记录
```

---

# 四、阶段 2：理解比赛数据、接口和 Evaluator

这一阶段仍然：

> **先不急着设计自己的复杂方案。**

目标是：

> 把官方提供的比赛环境彻底搞懂。

---

## 4.1 理解 Catalog

需要搞清楚：

- 一个商品有哪些字段？
- ASIN 在哪里？
- 商品名称在哪里？
- category 如何表示？
- price 如何表示？
- description 是否存在？
- brand 是否存在？
- 其他 metadata 有哪些？

最终你们应该能够回答：

> “如果我要描述一个商品，官方数据到底给了我哪些信息？”

---

## 4.2 理解 Session

研究：

- 一个 session 如何表示？
- 用户每一轮输入是什么？
- Agent 每一轮应该输出什么？
- session 的结束条件是什么？
- target product 如何定义？
- public session 和 private session 有什么区别？
- 10-turn limit 如何体现？

---

## 4.3 理解 Agent Interface

必须搞清楚：

```text
Evaluator
    ↓
调用什么接口？
    ↓
输入什么？
    ↓
Agent 返回什么？
    ↓
Evaluator 如何继续下一轮？
```

这一步非常重要。

因为以后你们即使彻底重写内部代码，也不能破坏：

> **官方要求的 Agent Interface。**

---

## 4.4 理解评分机制

不要只知道“有 MRR”。

要知道：

> evaluator 到底在什么情况下给分？

例如：

- 商品进入 Top-K 是如何计算的？
- 多轮推荐如何计算？
- MTTC 如何确定？
- 超过 10 turns 会发生什么？
- Efficiency 如何参与最终分数？
- TechnicalScore 如何组合？

这些必须以官方 evaluator 的实际定义为准。

---

## 4.5 阶段 2 的产出

建议形成一份团队内部文档：

```text
docs/
├── competition.md
├── data_schema.md
├── agent_interface.md
└── evaluation.md
```

内容不需要写解决方案。

只记录：

> “比赛规定了什么。”

---

# 五、阶段 3：建立第一版可工作的 Agent

这一阶段才开始：

> **从官方 starter agent 出发，建立你们自己的第一版方案。**

注意：

第一版目标不是高分。

目标是：

> **结构完整、可以运行、可以评估、方便修改。**

---

## 这一阶段需要完成的事情

### 5.1 建立项目自己的代码结构

将项目逐渐组织成清晰模块。

---

### 5.2 保留官方接口

无论内部怎么变化：

```text
Evaluator
    ↓
Official Interface
    ↓
Your Agent
```

这个边界尽量稳定。

---

### 5.3 建立可配置的运行方式

以后实验会非常多。

因此应该能够方便改变：

- 参数
- 模块开关
- 模型
- retrieval 设置
- ranking 设置
- dialogue 设置

但具体哪些参数，现在不需要决定。

---

### 5.4 建立日志和实验记录机制

以后你们会有：

```text
V1
V2
V3
V4
...
```

必须知道：

> 某一次结果到底对应哪一版代码。

---

# 六、阶段 4：系统化实验与问题分析

这一阶段是比赛真正开始竞争的地方。

目标：

> 不再凭感觉改代码，而是根据 evaluator 和 public sessions 找问题。

---

## 6.1 建立统一实验流程

每次实验都应该：

```text
修改
 ↓
Commit
 ↓
运行 public evaluator
 ↓
保存结果
 ↓
分析变化
 ↓
决定下一步
```

---

## 6.2 建立实验记录

例如：

```text
Experiment ID
Code commit
Changed component
Hypothesis
Dataset
Metrics
Result
Conclusion
Next step
```

---

## 6.3 做错误分析

重点研究：

```text
哪些 session 找不到？
为什么找不到？
哪些 session 找到了但排名很低？
为什么需要很多 turns？
哪些对话导致 Agent 状态出错？
```

这一步应该由团队共同参与。

---

## 6.4 建立问题分类

后续可以逐渐形成：

```text
Retrieval Problem
Ranking Problem
Intent Problem
Dialogue Problem
State Problem
Efficiency Problem
```

具体分类和定义由你们后续确定。

---

# 七、阶段 5：方案优化与迭代

这一阶段才是：

> **大量实验、比较不同方案、逐渐确定最终架构。**

---

## 主要任务

### 7.1 比较不同方案

例如：

```text
方案 A
vs
方案 B
```

---

### 7.2 做 Ablation

回答：

> “这个模块真的有用吗？”

例如：

```text
完整版本
↓
去掉某模块
↓
重新评估
↓
比较
```

---

## 7.3 同时关注多个指标

不能只看一个：

```text
Hit@10
```

应该同时关注：

```text
Recall
Precision
MRR
MTTC
Efficiency
TechnicalScore
```

---

## 7.4 关注泛化

public sessions 是开发数据。

最终还有：

```text
800 private sessions
```

因此不要无限针对 public sessions 做特殊优化。

---

# 八、阶段 6：最终版本冻结与全面测试

当你们已经确定最终方案后：

> **停止无休止地改架构。**

---

## 6.1 冻结候选版本

建议保留：

```text
Final Candidate
Backup Candidate
```

万一最后版本出现问题，可以回退。

---

## 6.2 全面测试

至少检查：

```text
[ ] 新环境能否安装
[ ] 新机器能否运行
[ ] 数据路径是否正确
[ ] evaluator 是否正常
[ ] 10-turn limit
[ ] 异常输入
[ ] 长对话
[ ] session 独立性
[ ] 运行速度
[ ] 内存使用
```

---

## 6.3 Reproducibility Test

最好找一个没有参与主要开发的人：

> 从一个干净环境重新运行项目。

如果他能按照 README：

```text
安装
↓
下载 / 准备数据
↓
运行
↓
得到结果
```

说明项目已经比较成熟。

---

# 九、阶段 7：比赛提交材料

题目要求三个主要交付物。

---

## 7.1 Devpost Written Description

需要准备：

```text
Problem
Solution
Architecture
Development Tools
APIs
Libraries
Dataset
Results
Innovation
Limitations
```

不要等到最后一天才写。

---

## 7.2 Public GitHub Repository

最终必须保证：

```text
README
Source Code
Setup
Installation
Usage
Reproduction
Results
Limitations
Future Work
Team Contributions
```

同时：

```text
不要上传 API Keys
不要上传 secrets
不要上传不应该公开的数据
```

---

## 7.3 Demo Video

题目允许 backend/NLP 项目使用：

> API usage / inference examples / result analysis

所以你们不需要为了视频专门做大型 UI。

最终视频应该让评委看到：

```text
Input
 ↓
Agent
 ↓
Multi-turn interaction
 ↓
Retrieval / Recommendation
 ↓
Final result
 ↓
Evaluation
```

---

# 十、阶段 8：最终展示与答辩准备

如果进入 Final Event：

需要准备的不只是 Demo。

---

## 8.1 讲清楚 Problem

回答：

> 为什么传统 keyword search 不够？

---

## 8.2 讲清楚 Insight

回答：

> 你们真正发现了什么问题？

---

## 8.3 讲清楚 Solution

回答：

> 你们是如何解决的？

---

## 8.4 讲清楚 Results

回答：

> 和 baseline 相比提高了多少？

---

## 8.5 讲清楚 Trade-off

例如：

```text
Accuracy
vs
Latency

Recall
vs
Precision

More clarification
vs
MTTC
```

评委很可能会问这些。

---

# 十一、四个人建议怎么分阶段工作？

不要一开始把四个人完全隔离。

建议：

## 阶段 1～2

**四个人一起完成。**

因为所有人都必须理解：

```text
代码
数据
接口
Evaluator
```

---

## 阶段 3～5

开始分工：

```text
成员 A
→ Retrieval / Search

成员 B
→ Agent / Dialogue

成员 C
→ Evaluation / Experiment

成员 D
→ Integration / Engineering / Documentation
```

但每个人不要只懂自己的部分。

至少：

> 四个人都应该知道整个系统如何运行。

---

## 阶段 6～8

重新合并：

```text
全员
 ↓
Final Integration
 ↓
Testing
 ↓
Demo
 ↓
Presentation
```

---

# 十二、建议建立的项目文件结构

第一阶段可以先非常简单：

```text
techjam-conversational-search/
│
├── README.md
│
├── src/
│
├── tests/
│
├── experiments/
│
├── docs/
│
├── scripts/
│
├── data/                 # 如果官方要求不要提交，则加入 .gitignore
│
├── requirements.txt      # 或官方使用的环境文件
│
└── .gitignore
```

后续再根据官方 starter agent 的结构调整。

**不要为了“看起来专业”现在就大规模重构官方代码。**

---

# 十三、Git 工作方式建议

四人团队最重要的是：

> **不要让 Git 成为比赛本身的敌人。**

建议：

```text
main
  ↑
develop
  ↑
feature branch
```

开发：

```text
创建 branch
↓
开发
↓
测试
↓
commit
↓
push
↓
Pull Request
↓
至少一人 review
↓
merge
```

---

## Commit 建议

不要：

```text
update
test
fix
aaa
```

建议：

```text
add baseline logging
fix evaluator integration
update experiment config
add documentation for dataset schema
```

这样以后查实验结果会非常方便。

---

# 十四、当前最重要的 Git 问题：Fork 还是 Clone？

## 推荐答案

### 官方仓库

作为：

> **Upstream**

### 团队仓库

作为：

> **Origin**

关系：

```text
Official Repository
       ↑
     upstream
       │
       │
       ↓
Team Repository
       ↑
     origin
       │
 ┌─────┼─────┐
 A     B     C     D
```

实际开发：

```text
四个人 → Team Repository
```

不是：

```text
四个人 → Official Repository
```

---

# 十五、如果没有 GitHub Organization 怎么办？

完全没问题。

由其中一个人：

```text
Fork official repository
```

然后：

```text
Settings
→ Collaborators
→ Add people
```

把另外三个人加入。

最终：

```text
A = repository owner
B = collaborator
C = collaborator
D = collaborator
```

已经足够完成比赛。

---

# 十六、一个容易忽略的问题：最终提交仓库怎么办？

题目要求：

> Public Code/GitHub Repository

所以最终你们需要有一个：

> **公开的团队代码仓库。**

最简单的方式就是：

```text
Team Fork
      ↓
开发全过程
      ↓
最终保持 Public
      ↓
Devpost 提交这个 URL
```

如果你们中途希望保持 private：

```text
Private development repository
        ↓
Final public repository
```

也可以，但需要额外处理历史和公开内容。

对于这次比赛，我更推荐：

> **从一开始就建立一个干净、可公开的团队仓库，并严格管理 secrets。**

---

# 十七、现在不要做什么？

你们刚开始阶段，以下事情都可以先放一放：

```text
❌ 不要马上确定最终模型
❌ 不要马上设计复杂 Agent
❌ 不要马上做 UI
❌ 不要马上买 API
❌ 不要马上训练模型
❌ 不要马上重构整个官方项目
❌ 不要马上做最终 Demo
❌ 不要为了“创新”加入大量模块
```

现在最重要的是：

```text
官方代码
+
数据
+
接口
+
Evaluator
+
Baseline
```

---

# 十八、你们现在的实际行动清单

## 今天：第一阶段启动

### GitHub

- [ ] 确定团队 GitHub 仓库负责人
- [ ] Fork 官方 repository
- [ ] 添加另外三名成员为 Collaborator
- [ ] 四个人 Clone 团队 repository
- [ ] 确认四个人都能 push / pull
- [ ] 约定 main / branch 使用规则

### Environment

- [ ] 阅读官方 README
- [ ] 安装官方要求的环境
- [ ] 安装依赖
- [ ] 确认 Python / package 版本
- [ ] 确认运行方式

### Competition Kit

- [ ] 获取 Participant Kit
- [ ] 获取 catalog
- [ ] 获取 public sessions
- [ ] 获取 evaluator
- [ ] 获取配置文件
- [ ] 检查 SHA256

### Baseline

- [ ] 运行 Starter Agent
- [ ] 运行 Local Evaluator
- [ ] 得到 Baseline
- [ ] 保存 Baseline
- [ ] 记录 Git commit
- [ ] 记录环境版本

---

# 十九、第一阶段完成后的“团队会议”

等四个人都跑通以后，再开一次短会。

这次会议不要讨论：

> “我们应该用什么最强模型？”

而只讨论：

### 问题 1

```text
数据是什么？
```

### 问题 2

```text
Session 是什么？
```

### 问题 3

```text
Evaluator 怎么工作？
```

### 问题 4

```text
Starter Agent 做了什么？
```

### 问题 5

```text
Baseline 有多强？
```

### 问题 6

```text
我们目前不知道什么？
```

---

# 二十、整个项目的阶段验收表

| 阶段 | 目标 | 必须产出 |
|---|---|---|
| 0 | 团队准备 | GitHub、分工、开发规范 |
| 1 | 跑通官方环境 | Starter Agent + Evaluator + Baseline |
| 2 | 理解比赛 | Data Schema + Interface + Evaluation 文档 |
| 3 | 第一版 Agent | 可运行、可评估的自有版本 |
| 4 | 问题分析 | 实验记录 + Error Analysis |
| 5 | 方案优化 | 多版本实验 + Ablation + 最终候选方案 |
| 6 | 最终冻结 | Final Agent + 全面测试 |
| 7 | 提交 | GitHub + Devpost + YouTube Demo |
| 8 | 决赛准备 | Pitch + Demo + Q&A |

---

# 二十一、最重要的项目管理原则

整个比赛可以一直遵循下面这个循环：

```text
Understand
    ↓
Implement
    ↓
Evaluate
    ↓
Analyze
    ↓
Improve
    ↓
Evaluate again
```

而不是：

```text
想一个很酷的方案
        ↓
写两天代码
        ↓
最后才跑 evaluator
```

---

# 二十二、你们现在真正的“第一步”

如果现在让我把所有事情压缩成一句话：

> **先 Fork 官方仓库，建立一个四人共同使用的 Team Repository；四个人各自 Clone，并严格按照官方说明把 Participant Kit、Starter Agent 和 Local Evaluator 全部跑通，然后记录第一份 Baseline。**

在这一步完成以前：

> **先不要决定你们最终采用什么算法。**

完成 Baseline 后，你们才真正拥有一个可以比较的“起点”。

---

# 二十三、当前阶段的最终状态

你们现在应该从：

```text
“我们选了 Shopping Copilot 这个题目”
```

进入：

```text
“我们已经拥有一个可以运行和评估的官方 Baseline”
```

然后再进入：

```text
“我们知道 Baseline 为什么不够好”
```

最后才是：

```text
“我们设计自己的方案来解决这些问题”
```

整个比赛的节奏建议保持为：

```text
官方 Baseline
      ↓
理解
      ↓
测量
      ↓
发现问题
      ↓
提出方案
      ↓
实验
      ↓
验证
      ↓
优化
      ↓
最终版本
```

**你们现在只需要关注最前面的两步：**

```text
① 建立团队 GitHub 仓库
② 跑通官方 Baseline
```

后面的技术路线暂时不要锁死。
