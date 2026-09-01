# Devpost Written Project Description

## English — Copy-ready Devpost Text

### Shopping Copilot

Shopping Copilot is a headless conversational product-search Agent that turns a static query into a shopping process users can correct. It was built for the TikTok TechJam 2026 Shopping Copilot challenge and works within the official ten-turn `reset/respond` protocol and read-only Amazon-derived catalog.

### Inspiration and problem

Real shoppers rarely express a complete, stable query. They start broad, add a budget, change a brand preference, switch between focused buying and open-ended browsing, or ask for a combination that does not exist. Traditional keyword search often forgets valid context or leaves an obsolete condition active. Our goal was to make each turn move the search closer to the shopper's current intent without silently breaking constraints.

### What it does

Shopping Copilot routes each turn into Buying or Browsing behavior while maintaining transactional session state. Buying protects hard eligibility and precise preferences; Browsing keeps scene context and result diversity. The Agent detects overrides, clears only the conflicting slot, retains every still-valid condition, filters catalog-ineligible products before ranking, asks one useful clarification when the candidate space is too broad, and applies controlled relaxation when no result remains. Budget and explicit exclusions are never silently relaxed. Every response is sanitized to at most ten unique, catalog-valid `parent_asin` values.

### How we built it

The official `starter.Agent` adapter delegates to a typed Python core. A deterministic parser and event detector feed a transactional state reducer. The resulting Buying/Browsing route plan drives hard filtering, local lexical/attribute retrieval and route-aware reranking. A dialogue policy chooses whether to clarify, safely relax or recommend, with late-turn protection to guarantee a legal response within the challenge limit.

The architecture includes opt-in boundaries for dense retrieval, a local intent classifier and a schema-bounded DeepSeek/OpenAI-compatible parser. These optional modules fail back to deterministic behavior. They were disabled in the frozen headline run, so the reported result used no external model calls.

### Results

On the organizer-released 200-session public development set, Shopping Copilot achieved HitRate@10 **0.9600**, MRR **0.606629**, MTTC **2.585**, Efficiency **0.8415**, and TechnicalScore **0.830289**. The official weak BM25 baseline scored 0.1250, 0.068034, 9.810, 0.1190, and 0.106710 respectively. That is an improvement of **83.50 percentage points** in HitRate@10, **53.86 points** in MRR, **72.25 points** in Efficiency, and **72.36 points** in TechnicalScore, while reaching the first hit **7.225 turns sooner** on average.

The frozen local run recorded p50 response latency of 27.248 ms, p95 of 48.044 ms, zero contract-compatible fallbacks and zero external model/API calls. These latency figures are feasibility measurements from one machine, not a production SLA.

### Development tools

We developed and tested the project with Python 3.12, VS Code, Git/GitHub, terminal tooling, browser developer tools and Python's `unittest` framework.

### APIs

No external API was used in the frozen evaluation. The repository supports an optional schema-bounded DeepSeek/OpenAI-compatible chat-completions parser, but it is disabled by default and safely falls back to deterministic rules. External API cost for the reported run was USD 0.

### Libraries and frameworks

The deterministic path uses Python and local in-memory indexes. Optional dense retrieval uses NumPy 2.5.2, FAISS CPU 1.12.0 and sentence-transformers 5.7.0. The browser walkthrough uses Python's standard-library HTTP server and a lightweight HTML/CSS/JavaScript frontend.

### Datasets and assets

The project uses the organizer competition package derived from Amazon Reviews 2023 by McAuley Lab at UCSD, category `Clothing_Shoes_and_Jewelry`: a read-only catalog of 50,000 products and 200 labeled public development sessions. Private evaluation sessions, raw reviews, user identifiers, model caches, API credentials and the full catalog are not published in our repository. The demo uses original text/UI assets and does not require third-party product images or logos.

### Challenges and what we learned

The hardest part was not retrieving more products; it was deciding which parts of conversation state remained valid after each update. Treating intent as transactional state made overrides, negation, clarification and safe relaxation composable. We also learned that optional model sophistication does not automatically improve end-to-end quality: every module must earn its place through the same evaluator, hard-constraint checks, latency budget and fallback behavior.

### Limitations and future work

The current catalog is static, the experience is text-only and single-process, and exact-item evaluation is narrower than real satisfaction. Rule-based understanding remains weaker on spelling noise, implicit long-tail preferences and complex comparisons. Next we would connect live inventory and pricing, add semantic assistance only behind quality/cost gates, improve multilingual and typo-tolerant understanding, and validate conversion and satisfaction through online experiments.


### Links

- GitHub: `https://github.com/HRWellls/ShoppingCopilot.git`
- Public demo video: `https://youtu.be/Ws1UAEZ1bV8`
- Devpost: `https://devpost.com/software/shoppingcopilot?ref_content=my-projects-tab&ref_feature=my_projects`

---

## 中文工作译文

### Shopping Copilot

Shopping Copilot 是一个无界面的对话式商品搜索 Agent。它把一次性的静态查询转化为用户可以持续修正的购物过程，并遵循比赛官方十轮上限、`reset/respond` 接口和只读商品目录。

### 问题与方案

真实购物者很少一次说清完整且稳定的需求。他们会从宽泛请求开始，追加预算，修改品牌偏好，在明确购买和开放浏览之间切换，或提出目录中不存在的组合。Shopping Copilot 把意图视为事务化状态：Buying 路径保护硬条件和精确偏好，Browsing 路径保留场景上下文与多样性；改口时只清除冲突槽位，过滤不合规商品后再排序，候选过宽时只问一个有价值的问题，空集时只放宽允许放宽的偏好。预算和明确排除项不会被静默放宽。

### 技术实现

官方 `starter.Agent` 适配层调用类型化 Python 核心。确定性解析器与事件检测器产生状态增量，事务化 reducer 更新会话状态，Buying/Browsing 路由驱动硬过滤、本地词法/属性检索和重排，策略层最终决定澄清、受控放宽或推荐。输出会被清洗为最多十个真实、唯一的 `parent_asin`。

系统还保留可选 Dense、意图分类器和 DeepSeek/OpenAI-compatible 结构化解析边界，但冻结成绩关闭了这些模块，因此没有外部模型调用。

### 结果

在组织方公开的 200 个开发会话上，Shopping Copilot 达到 HitRate@10 **0.9600**、MRR **0.606629**、MTTC **2.585**、Efficiency **0.8415**、TechnicalScore **0.830289**。相对官方 weak BM25 baseline，HitRate@10 提升 **83.50 个百分点**、MRR 提升 **53.86 个百分点**、Efficiency 提升 **72.25 个百分点**、TechnicalScore 提升 **72.36 个百分点**，平均首次命中减少 **7.225 轮**。

冻结本地运行的响应 p50 为 27.248 ms、p95 为 48.044 ms，fallback 为 0，外部模型/API 调用为 0。这些延迟是单机可行性数据，不是生产 SLA。

### 工具、API、库与数据

- 开发工具：Python 3.12、VS Code、Git/GitHub、终端工具、浏览器开发工具和 `unittest`。
- API：冻结评测未调用外部 API；代码支持可选 DeepSeek/OpenAI-compatible 解析器。
- 库：可选 Dense 路径使用 NumPy 2.5.2、FAISS CPU 1.12.0、sentence-transformers 5.7.0。
- 数据：Amazon Reviews 2023 衍生的比赛数据，品类为 `Clothing_Shoes_and_Jewelry`，包括 50,000 个只读商品和 200 个公开开发会话。
- 素材：原创文字与 UI 素材，不依赖第三方商品图片或商标。

### 局限与后续工作

当前目录是静态的，系统仅支持文本和单进程，精确商品命中也不能完全代表真实满意度。规则对拼写噪声、隐式长尾偏好和复杂比较仍有限。后续将接入实时库存与价格，仅在质量/成本门禁通过后增加语义辅助，并用在线实验验证转化和满意度。

### 团队贡献与链接

- 团队：`BurgerKing`
- GitHub：`https://github.com/HRWellls/ShoppingCopilot.git`
- 视频：`https://youtu.be/Ws1UAEZ1bV8`
- Devpost：`https://devpost.com/software/shoppingcopilot?ref_content=my-projects-tab&ref_feature=my_projects`
