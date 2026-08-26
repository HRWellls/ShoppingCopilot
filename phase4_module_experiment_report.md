# Phase 4 Dense、LLM 与 NLI 模块组合测评报告

生成时间：2026-08-27（Asia/Shanghai）

## 1. 结论摘要

本轮使用 `evaluator/local_evaluator.py` 的原始 `load_jsonl()`、`catalog_index()` 和 `evaluate()`，对 `data/public_set.jsonl` 的 200 个会话进行了五组 Dense/LLM 完整实验，并合并此前完成的 NLI 离线分类实验与 B/C/D/E 端到端消融。由于原评估器命令行不能注入 AgentConfig，实验入口只负责构造显式配置、记录延迟与模块调用状态，评分逻辑没有修改。

最终结论：

1. **B3（规则 + BM25）仍是当前推荐组合**，TechnicalScore 为 `0.331459`。
2. 默认 Dense 融合显著回退，TechnicalScore 降至 `0.268276`，不应直接启用。
3. 10% 低权重 Dense 将 Hit@10 从 `0.380` 提高到 `0.385`，Intent Override Hit@10 从 `0.433333` 提高到 `0.466667`；但 MRR、TechnicalScore 和 p95 均差于 B3，仍未达到发布条件。
4. LLM 开关完成了 200 会话回退实验，但当前环境没有 DeepSeek API Key：所有调用均为 `E_MODEL_UNAVAILABLE`，成功推理和 token 均为 0。因此只能证明回退安全，**不能评价 DeepSeek 的真实准确率**。
5. NLI v2 两阶段分类器的离线 Macro-F1 达到 `0.995495`，但 Active 端到端 TechnicalScore 只有 `0.309576`，低于 B3，并使 Intent Override Hit@10 从 `0.433333` 降至 `0.233333`。
6. NLI Shadow 不改变准确率，但 p95 从 `104.955 ms` 增至 `168.647 ms`；Active 未通过最终发布门禁，模型模式应保持 `off`。
7. 当前不建议默认启用 Dense、LLM 或 Active NLI。真实 LLM 实验必须在提供有效凭证后重新执行。

## 2. 实验环境

| 项目 | 值 |
|---|---|
| Python | 3.12.10 |
| 数据集 | `data/public_set.jsonl`，200 会话 |
| 商品目录 | `data/catalog.jsonl`，50,000 商品 |
| Dense/LLM 五组中的 NLI | `off`（所有组合一致） |
| NLI 模型 | `cross-encoder/nli-deberta-v3-xsmall`，`model_quint8_avx2` |
| NLI 运行时 | ONNX Runtime INT8，CPUExecutionProvider |
| NLI 假设/策略 | `shopping-intent-v2` / `two_stage` |
| NumPy | 2.4.1 |
| FAISS | 1.12.0 |
| sentence-transformers | 5.2.0 |
| Dense 模型 | `sentence-transformers/all-MiniLM-L6-v2` |
| Dense 索引 | `.runtime/indexes/catalog-all-MiniLM-L6-v2.faiss` |
| Dense 索引 SHA-256 | `5B32247DE01B64967DE6DDBFE212193BC3B213B56237C65A63272190921B8D29` |
| DeepSeek 模型配置 | `deepseek-v4-flash` |
| DeepSeek 超时 | 600 ms |
| API Key | 不可用（无环境变量、无 `api.env`） |

`requirements.txt` 固定的是 NumPy 2.5.2 和 sentence-transformers 5.7.0，本次机器实际版本如上。Dense 索引成功加载并完成全部查询，但严格复现时仍应使用 requirements 中的固定版本重新确认结果。

## 3. 固定 B3 基础配置

所有组合都启用以下 B3 模块：

```python
multiturn_state_enabled = True
intent_routing_enabled = True
intent_policy_enabled = True
intent_model_mode = "off"
```

本轮五组实验只改变 `dense_enabled`、`llm_enabled` 和 Dense 融合权重。NLI B/C/D/E 消融在相同 B3 基础上改变 `intent_model_mode` 和 `intent_model_switch_enabled`。所有实验均未修改 `starter/agent.py` 或 `src/config.py` 的默认行为。

## 4. 组合与模块状态

| 组合 | Dense | LLM | Dense 实际查询 | LLM 成功/尝试 | 模块结论 |
|---|---:|---:|---:|---:|---|
| B3 控制组 | 关 | 关 | 0 | 0/0 | 有效控制组 |
| B3 + LLM | 关 | 开 | 0 | 0/1460 | LLM 全部不可用回退 |
| B3 + Dense（默认权重） | 开 | 关 | 1525 | 0/0 | Dense 真实生效，零失败 |
| B3 + Dense + LLM | 开 | 开 | 1525 | 0/1525 | Dense 生效，LLM 全部回退 |
| B3 + 10% Dense | 开 | 关 | 1460 | 0/0 | Dense 真实生效，零失败 |

默认权重经过有效源归一化后，Dense 大约占 Buying 的 35.7%、Browsing 的 60%。低权重实验统一使用 BM25 90%、Dense 10%。

## 5. 总体测评结果

| 组合 | Hit@10 | MRR | MTTC | TechnicalScore | p50 | p95 | 初始化 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **B3 控制组** | **0.380** | **0.266196** | 7.920 | **0.331459** | 24.937 ms | **105.200 ms** | 34.243 s |
| B3 + LLM（全回退） | 0.380 | 0.266196 | 7.920 | 0.331459 | 25.488 ms | 104.811 ms | 34.776 s |
| B3 + Dense（默认权重） | 0.325 | 0.172585 | 8.300 | 0.268276 | 26.570 ms | 132.825 ms | 42.256 s |
| B3 + Dense + LLM（LLM 全回退） | 0.325 | 0.172585 | 8.300 | 0.268276 | 26.337 ms | 126.900 ms | 40.836 s |
| B3 + 10% Dense | **0.385** | 0.245649 | **7.915** | 0.327895 | 26.610 ms | 130.710 ms | 40.248 s |

相对 B3：

- 默认 Dense：Hit@10 `-0.055`，MRR `-0.093611`，TechnicalScore `-0.063183`，p95 `+27.625 ms`。
- 10% Dense：Hit@10 `+0.005`，MRR `-0.020547`，TechnicalScore `-0.003564`，p95 `+25.510 ms`。
- LLM 回退组：准确率完全相同，说明无凭证回退没有改变 Agent 行为，但这不是 LLM 质量结果。

## 6. 场景 Hit@10

| 组合 | Boundary | Browsing | Buying | Intent Override |
|---|---:|---:|---:|---:|
| **B3 控制组** | **0.500** | **0.4125** | 0.3125 | 0.433333 |
| B3 + LLM（全回退） | 0.500 | 0.4125 | 0.3125 | 0.433333 |
| B3 + Dense（默认权重） | 0.300 | 0.3500 | 0.3125 | 0.300000 |
| B3 + Dense + LLM（LLM 全回退） | 0.300 | 0.3500 | 0.3125 | 0.300000 |
| B3 + 10% Dense | 0.500 | 0.4125 | 0.3125 | **0.466667** |

默认 Dense 对 Boundary、Browsing 和 Intent Override 均产生回退。10% Dense 恢复了前三个稳定场景，并提高 Intent Override Hit@10，但 Buying/Browsing/Override 的排名质量（MRR）仍然下降，导致综合分未超过 B3。

## 7. Dense 分析

Dense 模块不是“开关已开但实际回退”：

- FAISS 索引从磁盘成功加载。
- 默认权重组执行 1525 次 Dense 查询，1026 次缓存命中，0 次查询失败。
- 10% 权重组执行 1460 次 Dense 查询，973 次缓存命中，0 次查询失败。

因此准确率下降来自候选融合和排序，而不是环境故障。当前 `all-MiniLM-L6-v2` 的通用语义相似度会把语义接近但不满足隐藏目标排序需求的商品推高，默认 Browsing 60% Dense 权重尤其激进。

后续若继续优化 Dense，应先在独立校准集上调整 Buying/Browsing 权重、限制 Dense 参与的路由或增加后置重排，不能直接使用当前默认权重。

## 8. LLM 分析与限制

LLM 模块在配置层面已启用，结构化解析器也已创建，但运行环境没有 `DEEPSEEK_API_KEY` 或 `api.env`：

- B3 + LLM：1460 次尝试，0 次成功，1460 次 `E_MODEL_UNAVAILABLE`。
- B3 + Dense + LLM：1525 次尝试，0 次成功，1525 次 `E_MODEL_UNAVAILABLE`。
- 两组 token 使用均为 0，没有发生外部 API 调用或费用。
- 规则解析回退保持了有效响应，response fallback 为 0。

因此本报告不对 DeepSeek 的准确率、延迟、成本或收益作正向结论。获得有效凭证后，应先做 8 会话联网烟测，确认成功率、schema 合规率和 600 ms 超时预算，再决定是否运行完整 200 会话。完整联网实验可能产生 API 费用。

## 9. NLI 轻量意图模型实验

### 9.1 离线意图分类

离线数据集为 `data/intent_eval_v1.jsonl`。最终测试 split 共 930 条，其中 750 条用于 Buying、Browsing、Continue、Switch 和混淆意图指标，其余样本用于事件召回。校准集与测试集按模板族隔离。

| 版本 | 策略 | Macro-F1 | Buying→Browsing | Continue Recall | p95 | 门禁 |
|---|---|---:|---:|---:|---:|---|
| shopping-intent-v1 | single | 0.227428 | 0.500 | 0.000 | 45.215 ms | 失败 |
| **shopping-intent-v2** | **two_stage** | **0.995495** | **0.000** | **1.000** | **20.026 ms** | **通过** |

两个版本的 override、clear、negation、no_preference 和 intent_switch 事件召回均为 `1.0`，因为事件由确定性规则检测，不由 NLI 直接生成。v1 在 Buying/Browsing/Continue 上失效，因此只保留为失败基线；v2 引入两阶段 Continue/Switch 判定后通过离线门禁。

v2 校准只读取 calibration split，750 条样本得到：

| 阈值 | 值 |
|---|---:|
| Initial confidence | 0.769759 |
| Initial margin | 0.070000 |
| Switch confidence | 0.800000 |
| Switch margin | 0.100000 |
| Calibration Macro-F1 | 0.944056 |

### 9.2 200 会话端到端消融

| 变体 | NLI 模式 | Hit@10 | MRR | MTTC | TechnicalScore | p95 |
|---|---|---:|---:|---:|---:|---:|
| **B：B3 规则基线** | **off** | **0.380** | **0.266196** | **7.920** | **0.331459** | **104.955 ms** |
| C：NLI 观察模式 | shadow | 0.380 | 0.266196 | 7.920 | 0.331459 | 168.647 ms |
| D：NLI 主动模式 | active | 0.355 | 0.240919 | 8.010 | 0.309576 | 177.129 ms |
| E：主动但禁止模型切换 | active，no-switch | 0.350 | 0.236196 | 8.040 | 0.305059 | 455.360 ms |

场景 Hit@10：

| 变体 | Boundary | Browsing | Buying | Intent Override |
|---|---:|---:|---:|---:|
| B：off | 0.500 | 0.4125 | 0.3125 | 0.433333 |
| C：shadow | 0.500 | 0.4125 | 0.3125 | 0.433333 |
| D：active | 0.500 | **0.4250** | 0.3125 | 0.233333 |
| E：active no-switch | 0.500 | 0.4125 | 0.3125 | 0.233333 |

### 9.3 结果解释

- Shadow 与 B3 的推荐列表和准确率完全一致，证明观察模式没有污染状态、路由或候选；代价是 p95 增加 `63.692 ms`。
- Active 虽使 Browsing Hit@10 增加 `0.0125`，但 Intent Override Hit@10 下降 `0.20`，TechnicalScore 下降 `0.021883`。
- Active 相对 B3 的 p95 增加 `72.174 ms`，超过批准的 25 ms 开销预算。
- E 禁止模型切换后仍未恢复 Override，且本次 p95 异常升至 `455.360 ms`，不能作为发布配置。
- 离线分类准确率高不等于端到端收益。模型错误发生在状态继承、显式覆盖和候选排序的组合链路中，端到端门禁必须优先于离线 Macro-F1。

最终 Active 门禁的 `active_above_b3`、`scenario_protection` 和 `p95_budget` 均失败，只有事件指标通过，因此自动选择的默认模型模式为 `off`。

### 9.4 启用依赖

Shadow 或 Active 需要同时配置：

```python
intent_model_mode = "shadow"  # 或 "active"
intent_model_path = Path(".runtime/models/nli-deberta-v3-xsmall")
intent_manifest_path = Path(
    ".runtime/models/nli-deberta-v3-xsmall/intent-manifest.json"
)
intent_classifier_strategy = "two_stage"
intent_hypothesis_version = "shopping-intent-v2"
```

还需要 ONNX Runtime、Transformers、本地 tokenizer、量化 ONNX 模型、匹配的 manifest 和校准阈值。运行时只允许 `local_files_only=True`，不会下载模型。Shadow 只用于观测；Active 当前不得作为默认发布模式。

## 10. 发布建议

当前推荐保持：

```python
multiturn_state_enabled = True
intent_routing_enabled = True
intent_policy_enabled = True
intent_model_mode = "off"
llm_enabled = False
dense_enabled = False
```

理由：B3 TechnicalScore 最高，依赖最少，p95 更低，并且已经通过既有质量门禁。10% Dense 可作为后续实验候选，但当前不能替代 B3；LLM 在真实成功调用完成前不得进入发布比较；NLI v2 可继续使用 Shadow 收集数据，但 Active 的端到端准确率和延迟门禁均失败。

## 11. 复现命令

```powershell
python -m scripts.phase4_module_benchmark --name b3-control --output .runtime/phase4-b3-control.json
python -m scripts.phase4_module_benchmark --name b3-llm --llm --output .runtime/phase4-b3-llm.json
python -m scripts.phase4_module_benchmark --name b3-dense --dense --output .runtime/phase4-b3-dense.json
python -m scripts.phase4_module_benchmark --name b3-dense-llm --dense --llm --output .runtime/phase4-b3-dense-llm.json
python -m scripts.phase4_module_benchmark --name b3-dense-10pct --dense --dense-weight 0.10 --output .runtime/phase4-b3-dense-10pct.json

python -m scripts.evaluate_intent_model --split test --model-dir .runtime/models/nli-deberta-v3-xsmall --strategy two_stage --hypothesis-version shopping-intent-v2 --calibration docs/baselines/intent-calibration-v2.json --output .runtime/intent-v2-test.json
python -m scripts.check_intent_gate .runtime/intent-v2-test.json

python -m scripts.phase3_benchmark --state-events --route --policy --intent-mode shadow --output .runtime/multiturn-c-shadow.json
python -m scripts.phase3_benchmark --state-events --route --policy --intent-mode active --output .runtime/multiturn-d-active.json
python -m scripts.phase3_benchmark --state-events --route --policy --intent-mode active --disable-model-switch --output .runtime/multiturn-e-no-switch.json
python -m scripts.check_active_gate
```

`check_active_gate` 在当前冻结结果上返回非零退出码是预期行为，表示 Active 没有通过发布门禁。

## 12. 结果文件与校验和

| 文件 | SHA-256 |
|---|---|
| `.runtime/phase4-b3-control.json` | `F3409B6E76EB2A2A9B0FDAB1C019150788EB8D11C1319EB45C29B4282956924C` |
| `.runtime/phase4-b3-llm.json` | `BDDAE64993051CA0A77B4EDCFF4CBE7277A63CD9C48DF41C52E63A7BD05AA0AA` |
| `.runtime/phase4-b3-dense.json` | `CBED2336202A2B7C2295456AB1DF2A3A1567672FFB7040D4AD3634E7F50F0A9C` |
| `.runtime/phase4-b3-dense-llm.json` | `E2F30526FD2B6D2B2E1D9DF9D75A77933F9D2755C26D452C556A7F7E107FDB2E` |
| `.runtime/phase4-b3-dense-10pct.json` | `75780287E1FF711B333243D9EA5E592DDE884B7B05F3BCA533322F90FBD7733E` |
| `.runtime/multiturn-c-shadow.json` | `E12866D8F97C93940D6838F9C26005D5982F0D5ADC377868C73CF76180FDFE94` |
| `.runtime/multiturn-d-active.json` | `C33DB6FEA5BE683A85D9A85A9639B9A9CC316B759B8F1A1299140F6D8C516371` |
| `.runtime/multiturn-e-no-switch.json` | `C6B49C91805ECEC80876B6FB6F153A3F01F4882772AA5E933A98D660CC4584E0` |

端到端 JSON 均包含全部 200 条 session 明细、总体与场景指标、配置或实验元数据。NLI 离线指标冻结在 `docs/baselines/intent-shadow-v1.json`、`docs/baselines/intent-v2-test.json` 和 `docs/baselines/intent-calibration-v2.json`；端到端汇总冻结在 `docs/baselines/multiturn-model-ablation.json`。
