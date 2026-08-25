# Shopping Copilot 纯 Agent 技术选型

> 基于 random-consensus-architecture 的多方案收敛结果。本文只设计 Agent 内核，不设计后端服务、数据库集群或 UI。

## 1. 项目上下文与假设

- Python 单进程 Agent，遵守官方 `reset/respond` 接口。
- 50,000 个静态 Amazon Clothing、Shoes and Jewelry 商品；目录只读，检索索引全部驻内存。
- 每个会话最多 10 轮，场景包括 Buying、Browsing、Intent Override、Boundary。
- 每轮最多返回 10 个 `parent_asin`；核心目标是 `0.50*HitRate@10 + 0.30*MRR + 0.20*Efficiency`。
- 不依赖必须联网的模型或服务。外部 LLM 只能作为可插拔增强，必须有本地/规则 fallback。
- 由于每个会话是隔离单用户交互，长期记忆只保留接口和摘要设计，不做跨会话持久化。

## 2. 提案轨道与候选方案

两轮独立提案共覆盖以下 7 类方案：

| 方案 | 核心编排 | 主要优点 | 主要问题 |
|---|---|---|---|
| A FSM-Hybrid | 显式状态机：意图→槽位→检索→重排→询问/推荐 | 可控、可复现、Override 清晰 | 复杂策略需要显式规则 |
| B Planner-Executor | LLM 生成 JSON 计划，执行器校验并重规划 | 运行时编排灵活 | 计划漂移、token 和延迟更高 |
| C ReAct Tool Loop | LLM 自由选择搜索、过滤、澄清工具 | 原型快、工具可扩展 | 不稳定，难以保证 10 轮内收敛 |
| D Multi-Agent | Intent/Constraint/Search/Critic/Dialogue 专家协作 | 场景隔离、边界鲁棒 | 调用次数与协调复杂度过高 |
| E Policy/Bandit | 用候选熵、槽位完整度选择询问或推荐动作 | 直接优化 MTTC | 依赖调参，公开集过拟合风险 |
| F Reflective RAG | 推荐后由 Verifier/Critic 校验并修复 | 降低硬约束和 ASIN 错误 | 额外调用，收益需实验证明 |
| G Graph Workflow | 可组合技能图，条件边支持回滚 | 可插拔、易做策略实验 | 初始建图和条件管理成本高 |

## 3. 归一化频率

将 state-machine、planner、graph、policy 统一为显式工作流；将 cross-encoder、LLM rerank 统一为受限重排；将 slot、event、blackboard 统一为会话记忆。

| 组件标签 | 频率 | 结论 |
|---|---:|---|
| 混合检索（BM25/词法 + dense + metadata） | 7/7 | 高共识，默认采用 |
| 会话槽位/状态记忆 | 7/7 | 高共识，默认采用 |
| 结构化意图路由 | 6/7 | 高共识，默认采用 |
| 显式状态机/工作流 | 6/7 | 高共识，默认采用 |
| LLM 或 Cross-Encoder 受限重排 | 7/7 | 高共识，Top-N 后采用 |
| Typed、确定性工具 | 6/7 | 高共识，默认采用 |
| Override 回滚与槽位重写 | 5/7 | 高价值，必须采用 |
| 熵/信息增益澄清 | 4/7 | 候选组件，采用 |
| 事件轨迹与离线回放 | 3/7 | 候选组件，建议首版加入 |
| 单次 Verifier/Critic | 3/7 | 低频但有价值，作为保护开关 |
| 多 Agent 专家投票 | 1/7 | 暂缓 |
| 在线 Bandit 探索 | 1/7 | 暂缓，仅做离线调参 |
| 跨会话长期画像 | 2/7 | 不符合当前评测边界，暂缓 |

## 4. 加权决策

评分公式：`0.30*frequency + 0.25*feasibility + 0.20*project_fit + 0.15*(1-migration_risk) + 0.10*platform_value`。

| 方案 | 频率 | 可行性 | 项目适配 | 综合分 | 决策 |
|---|---:|---:|---:|---:|---|
| A FSM-Hybrid | 0.86 | 0.95 | 0.98 | **0.90** | 核心 |
| E Policy/Bandit（离线） | 0.57 | 0.82 | 0.90 | 0.82 | 吸收信息增益策略 |
| B Planner-Executor | 0.71 | 0.70 | 0.78 | 0.79 | 仅在低置信场景局部启用 |
| G Graph Workflow | 0.71 | 0.68 | 0.80 | 0.77 | 用轻量 StateGraph 实现 |
| F Reflective RAG | 0.43 | 0.70 | 0.82 | 0.73 | 单次校验开关 |
| C ReAct | 0.43 | 0.55 | 0.65 | 0.68 | 暂缓 |
| D Multi-Agent | 0.29 | 0.45 | 0.50 | 0.60 | 暂缓 |

## 5. 最终 Agent 架构

```text
reset(session)
  -> SessionState / ProfileDistiller

每轮 respond(message)
  -> IntentRouter + SlotExtractor (typed JSON)
  -> OverrideResolver / ConstraintState
  -> Buying Track 或 Browsing Track
       Buying: hard filter -> BM25 -> dense 补召回
       Browsing: dense -> BM25 -> category/metadata 补召回
  -> RRF/加权融合 -> Top 30~50
  -> Cross-Encoder；可选低温 LLM Top 20 重排
  -> Hard-constraint Verifier
  -> DialoguePolicy:
       候选过宽/低置信 -> 信息增益最高的单槽询问
       候选稳定/高置信 -> 返回 Top 10
  -> TraceRecorder + 官方响应适配器
```

### 5.1 状态与记忆

每个槽位保存 `value、kind(hard/soft/context)、confidence、source、turn_seen、ttl`。显式新值覆盖旧值；`actually/instead/change` 触发冲突槽清除和重检索；硬约束不因 TTL 自动衰减。会话摘要只保留当前目标、已确认偏好、已问属性和失败原因。

### 5.2 意图与槽位抽取

采用“规则先验 + 小模型/外部 LLM 结构化抽取 + schema 校验”三层 fallback。LLM 不直接选择 ASIN。Buying 侧优先识别预算、品类、尺码、颜色、品牌等硬约束；Browsing 侧保留场景语义和多样性。路由置信度低时保持原路由，明确意图覆盖时才切换。

### 5.3 驻内存检索

- 商品文本：`title`、`category`、`brand/store`、`features`、`description` 分字段拼接，title/category 加权。
- 词法：`rank_bm25` 或现有内存 FTS；dense：`sentence-transformers`（优先 bge-small-en-v1.5，无网络时使用 MiniLM），向量矩阵用 NumPy/FAISS `IndexFlatIP`。
- Buying 初始硬过滤，空集时按“尺寸/预算/品类”优先级渐进放宽；Browsing 不做过硬过滤。
- RRF 或归一化加权融合。起始权重：Buying lexical/filter `.45`、dense `.25`、category `.20`、profile `.10`；Browsing dense `.45`、lexical `.30`、category `.15`、profile `.10`。
- 重排只处理 Top 30~50，硬约束违规施加大负分；LLM 超时或 JSON 无效时回退本地排序。

### 5.4 对话策略

候选数大于 100 或候选熵高时立即澄清；候选数 10~100 时询问一个信息增益最高的缺失槽；候选数小于 10 或置信度足够时直接推荐。第 8~10 轮只问最关键缺口，并始终返回候选，避免为了解释耗尽轮数。

### 5.5 工具边界

工具固定为 `parse_query`、`update_slots`、`filter_catalog`、`search_bm25`、`search_dense`、`fuse_candidates`、`rerank`、`verify_recommendations`、`ask_attribute`。每个工具使用 typed schema、输入上限、超时和结果校验；不开放任意代码执行或自由工具循环。

## 6. 分阶段落地

1. **MVP**：保持官方接口，完成 Catalog 预处理、SessionState、规则路由、BM25、Top10 输出。
2. **双轨检索**：加入 dense 向量、RRF、Buying 硬过滤与渐进放宽、Browsing 多样性。
3. **对话收敛**：加入结构化槽位抽取、Override 回滚、候选熵/信息增益询问、10 轮保护。
4. **精度保护**：Top50 Cross-Encoder；低置信时启用一次 Verifier；失败则降级澄清，不重复反思。
5. **实验闭环**：记录每轮路由、槽位变更、候选数、目标 rank、询问字段、延迟和 token；在 200 公共集分 Buying/Browsing/Override/Boundary 调权重和阈值，保留验证切分。
6. **可选增强**：仅在低置信轮局部使用 Planner JSON 重规划；Bandit 只离线选择阈值，不做在线探索；多 Agent 暂不引入。

## 7. 风险与取舍

- 过硬过滤会损失 Hit@10：采用空集检测和渐进放宽，并把当前显式约束权重高于画像。
- LLM 抽取延迟或格式错误：schema 校验、超时、规则 fallback；LLM 不参与全目录搜索。
- dense 语义偏移和字段噪声：title/category 优先，限制描述长度并做同义词归一化。
- Cross-Encoder CPU 成本：只重排 Top 30~50，缓存重复 query。
- 公开集过拟合：分层验证、固定实验记录，不针对单 session 写规则。
- 反思/规划增加 MTTC：只在低置信触发，最多一次；任何情况下不超过 10 轮。

## 8. 实现检查清单

- [ ] 官方 `reset/respond` 与 JSON contract 全部通过
- [ ] 每个 session 独立，状态不会泄漏到下一会话
- [ ] Buying/Browsing 路由、Intent Override、否定与槽位清除有测试
- [ ] 硬约束过滤、空集放宽、Top10 去重和合法 ASIN 校验完成
- [ ] BM25、dense、RRF、重排均可单独开关并记录版本
- [ ] 候选熵触发澄清且每轮最多询问一个属性
- [ ] 第 10 轮仍返回推荐，永不依赖第 11 轮
- [ ] 记录 Hit@10、MRR、MTTC、Efficiency、TechnicalScore 及分场景指标
- [ ] 运行无外部模型时仍有可复现 fallback
- [ ] 不提交 API key、私有评测数据或不可恢复的模型缓存
