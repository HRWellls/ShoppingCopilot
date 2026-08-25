# 🛒 Shopping Copilot: AI Conversational Search and Recommendations
**Technical Workshop Webinar: 28 Aug, 4:00–4:45pm**  
[Join the webinar](https://example.com)

---

## 1. Background
Traditional e-commerce search engines rely on static keyword matching and fail to capture the fluid dynamics of consumer psychology, especially the distinction between open-ended browsing and high-intent purchasing. In modern conversational commerce, an intelligent agent that leverages dynamic context programming is essential to bridge ambiguous user queries with complex product catalogs. Solving this directly impacts core industrial metrics.

---

## 2. Problem Statement
Participants are challenged to architect a next-generation shopping agent that handles real-world customer dynamics. The system must demonstrate:
- Deep cognitive understanding
- Runtime architectural agility
- Commercial efficiency

The solution must be built upon the following **four core pillars**:

### 2.1 Core Architecture: Intent Routing & Hybrid Pipeline
- **Dual-Track Routing**: Instantly detect intent —
  - `Buying` → high-precision filter track (hard constraints)
  - `Browsing` → diverse dense retrieval track (cross-category matching)
- **Pipeline Base**: In-memory data stream: `Multi-Route Retrieval → LLM Semantic Ranking` (keyword + category + vector similarity)

### 2.2 Dialog Strategy: Multi-Turn Scenario Evolution
- **Dynamic State Machine**: Handle Information Accumulation (incremental slots) and Intent Override (slot erasure/rewriting)
- **Proactive Guidance**: Trigger retrieval cutoff under Over-Generality and generate structured clarification prompts to guide user convergence

### 2.3 Self-Evolution: Dynamic Context Programming
- **Runtime Adaptation**: Perform Personalized Context Distillation from dialog history; update short-term session states and long-term user profiles
- **Adaptive Orchestration**: Use dynamic Context Programming for runtime workflow re-orchestration and strategy alignment

### 2.4 Evaluation Matrix: Product & Efficiency Metrics
Based on the final purchased record in the Amazon dataset, performance is quantified across three dimensions:
- **Coverage (Hit Rate@K)**: Catalog recall during retrieval
- **Precision (MRR / Top-K Hit Rate)**: LLM accuracy in ranking the exact purchased item at the top
- **Efficiency (MTTC - Mean Turns to Conversion)**: Reward systems that minimise interaction rounds; penalise unnecessary cognitive load

---

## 3. Constraints & Scope

| Category | Details |
|----------|---------|
| **In Scope** | - Intent detection for Buying/Browsing routing<br>- Heterogeneous retrieval routing (weights, truncation, slot decay)<br>- Runtime-adaptive memory layers for context distillation<br>- Prompt tuning or local scoring logic for LLM ranking |
| **Out of Scope** | - UI/UX development (backend/headless only)<br>- Full-parameter fine-tuning of foundation LLMs<br>- External vector DB clusters (must run in-memory)<br>- Multi-modal processing (text only) |
| **Limits** | - Max 10 turns per session (hard cap; zero score if exceeded)<br>- Amazon catalogue is strictly read-only |
| **Allowed Assumptions** | - Inputs are pre-cleaned text (no spelling/ASR noise)<br>- Catalogue, pricing, category trees are static<br>- Single-user isolated sessions (no concurrency) |

---

## 4. Available Resources & Data

### Competition Data
- **50,000 products** from Amazon Reviews 2023 `Clothing_Shoes_and_Jewelry`
- **200 labelled public development sessions** for local testing
- **800 private sessions** for final evaluation
- Public and private sessions use separate users and target products

### Participant Resources
- Weak BM25 starter Agent (Python)
- Deterministic local evaluator (Hit Rate@10, MRR, MTTC, Efficiency, TechnicalScore)
- Published Python Agent interface and API contract
- Evaluation config, baseline results, data docs, submission rules
- SHA256 checksum file for catalogue verification

> Participants may modify or replace the starter Agent.  
> The kit supports: keyword retrieval, rule-based methods, dense retrieval, hybrid retrieval, reranking, local models, and external model APIs.  
> The organiser does **not** provide hosted model access, API keys, or credits. A paid LLM is **not required**. Teams using external services are responsible for their own credentials and costs.

### Links
- Repository: https://github.com/TechJam2026/techjam-conversational-search
- Participant Kit Release: https://github.com/TechJam2026/techjam-conversational-search/releases/tag/participant-kit
- Original Data Source: https://amazon-reviews-2023.github.io/

---

## 5. Deliverables

### 5.1 Written Project Description (via Devpost)
- How your solution addresses the problem
- Development tools used (e.g., VSCode, Colab, Jupyter)
- APIs used (e.g., OpenAI GPT-4o, Google Maps API)
- Libraries & frameworks (e.g., Hugging Face, PyTorch, scikit-learn, pandas)
- Datasets & assets used (e.g., Google Local Reviews, manually labelled data)

### 5.2 Public Code / GitHub Repository
- Well-structured, commented code covering all components
- README must include:
  - Project overview
  - Setup & installation instructions
  - Steps to reproduce results
  - Reflection on limitations and future improvements
  - Team member contributions (if applicable)

### 5.3 Demo Video (YouTube, public)
- End-to-end walkthrough (inference, API usage, result analysis, etc.)
- Link included in Devpost description
- No third-party trademarks or copyrighted content without permission

---

## 6. Judging Criteria

| Criterion | Definition | Weight |
|-----------|------------|--------|
| **Technical Execution** | Strong engineering fundamentals, reliable demo, thoughtful architecture, effective API/model use | 35% |
| **Innovation & Problem Insight** | Originality, clarity of problem framing, directness of solution | 20% |
| **Impact & Relevance** | Real-world value, tangible benefit, relevance beyond the hackathon | 20% |
| **Feasibility & Practicality** | Buildable beyond prototype, sustainable resource usage, grounded architecture | 15% |
| **Presentation & Communication** *(Final Event Only)* | Clear storytelling, depth in Q&A, genuine project understanding | 10% |