"""Render a readable Markdown trace report from retrieval diagnostics JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) if value else "-"
    return str(value)


def target_rank(stages: dict[str, Any], name: str) -> str:
    value = stages.get(name)
    return "-" if value is None else str(value)


def turn_path(turn: dict[str, Any]) -> str:
    stages = turn.get("target_ranks") or {}
    if turn.get("fallback"):
        return "core 异常 -> 安全回退"
    if turn.get("conflict_reason"):
        return "NLU/状态冲突 -> 不执行检索 -> 空结果/保留旧结果"
    if turn.get("candidate_count", 0) == 0:
        return "状态归约 -> HardFilter -> 0 候选 -> 空结果"
    channels = []
    if stages.get("attribute") is not None:
        channels.append("ExactAttribute")
    if stages.get("lexical") is not None:
        channels.append("BM25")
    if stages.get("dense") is not None:
        channels.append("Dense")
    channel_text = "+".join(channels) if channels else "无独立通道"
    if stages.get("reranked") is not None:
        channel_text += " -> RouteReranker"
    else:
        channel_text += " -> fused"
    if turn.get("asked_attribute"):
        channel_text += " -> 澄清"
    elif turn.get("response_action") == "recommend":
        channel_text += " -> 推荐"
    return channel_text


def render_turn(turn: dict[str, Any], target: str) -> list[str]:
    stages = turn.get("target_ranks") or {}
    active = turn.get("active_constraints") or {}
    top10 = turn.get("top10") or []
    target_in_top10 = target in top10
    lines = [
        f"#### Turn {turn.get('turn')}",
        f"- 用户输入：{fmt(turn.get('user_message'))}",
        f"- Agent 回复：{fmt(turn.get('response_message'))}",
        f"- 执行路径：`{turn_path(turn)}`",
        f"- 路由：`{fmt(turn.get('route'))}`；动作：`{fmt(turn.get('response_action'))}`；回退：{fmt(turn.get('fallback'))}",
        f"- 活动硬约束：`{fmt(active)}`",
        f"- 保留语义证据：`{fmt(turn.get('query_evidence'))}`；冲突：`{fmt(turn.get('conflict_reason'))}`；放宽级别：`{fmt(turn.get('relaxation_level'))}`",
        f"- 候选数：{fmt(turn.get('candidate_count'))}；澄清属性：`{fmt(turn.get('asked_attribute'))}`；策略原因：`{fmt(turn.get('policy_reason'))}`",
        f"- 事件：`{fmt(turn.get('events'))}`；本轮 override 已生效：{fmt(turn.get('override_applied'))}",
        f"- 目标 `{target}` 各阶段排名：attribute={target_rank(stages, 'attribute')}, lexical={target_rank(stages, 'lexical')}, dense={target_rank(stages, 'dense')}, raw_union={target_rank(stages, 'raw_channel_union')}, reranked={target_rank(stages, 'reranked')}, fused={target_rank(stages, 'fused')}；Top 10 命中：{fmt(target_in_top10)}",
        f"- 延迟(ms)：`{fmt(turn.get('retrieval_timings'))}`",
        f"- 返回 Top 10：`{fmt(top10)}`",
    ]
    if turn.get("reranker_explanations"):
        explanations = turn["reranker_explanations"]
        target_explanation = next((item for item in explanations if item.get("parent_asin") == target), None)
        if target_explanation:
            contributions = target_explanation.get("contributions") or {}
            lines.append(
                "- 目标重排证据："
                f"score={target_explanation.get('score')}, "
                f"rerank_total={contributions.get('rerank_total')}, "
                f"field_category={contributions.get('field_category')}, "
                f"field_completeness={contributions.get('field_completeness')}, "
                f"exact_phrase={contributions.get('exact_phrase', '-')}, "
                f"source_ranks={fmt(target_explanation.get('source_ranks'))}"
            )
    return lines


def render_session(session: dict[str, Any], products: dict[str, dict[str, Any]]) -> list[str]:
    target = str(session.get("target_parent_asin", "unknown"))
    # Older diagnostic reports did not carry the target; current reports do.
    if target == "unknown":
        target = str(session.get("ground_truth", {}).get("parent_asin", "unknown"))
    product = products.get(target, {})
    product_title = str(product.get("title") or "-").replace("\n", " ")
    product_categories = product.get("categories") or []
    product_price = product.get("price")
    lines = [
        f"### {session.get('sample_id')} | {session.get('scenario_type')}",
        f"- 目标商品：`{target}`；标题：{product_title}；类别：`{fmt(product_categories)}`；价格：`{fmt(product_price)}`",
        f"- 最终命中：{fmt(session.get('hit'))}；首次命中轮：{fmt(session.get('first_hit_turn'))}；最佳返回排名：{fmt(session.get('best_rank'))}",
        f"- 候选池最佳排名：{fmt(session.get('best_pool_rank'))}；原始 union 最佳排名：{fmt(session.get('best_raw_union_rank'))}；首次进入候选池：Turn {fmt(session.get('first_recall_turn'))}",
        f"- 无收益澄清次数：{fmt(session.get('unproductive_clarifications'))}；override 状态残留：{fmt(session.get('override_state_failure'))}",
        "",
    ]
    for turn in session.get("turns", []):
        lines.extend(render_turn(turn, target))
        lines.append("")
    return lines


def render(report: dict[str, Any], source: Path, products: dict[str, dict[str, Any]]) -> str:
    overall = report.get("retrieval_diagnostics", {}).get("overall", {})
    config = (report.get("benchmark") or {}).get("config", {})
    lines = [
        "# Public Set 逐用例 Agent 行为路径报告",
        "",
        f"> 数据源：`{source}`；本报告由 `scripts/retrieval_diagnostic_benchmark.py` 生成的逐轮诊断渲染而来。",
        "> 每个用例都记录用户输入、Agent 回复、路由、活动约束、候选阶段、目标排名、Top 10、澄清、策略原因、事件、override、回退和检索耗时。",
        "",
        "## 1. 本次运行摘要",
        "",
        f"- 样本数：{fmt(report.get('sample_count'))}；Hit@10：`{fmt(report.get('hit_rate_at_10'))}`；MRR：`{fmt(report.get('mrr'))}`；MTTC：`{fmt(report.get('mttc'))}`；TechnicalScore：`{fmt(report.get('recommended_technical_score'))}`",
        f"- candidate recall@10/@50/@150：`{fmt(overall.get('candidate_recall_at_10'))}` / `{fmt(overall.get('candidate_recall_at_50'))}` / `{fmt(overall.get('candidate_recall_at_pool'))}`；raw union 覆盖：`{fmt(overall.get('raw_channel_union_coverage'))}`",
        f"- 候选生成失败：`{fmt(overall.get('candidate_generation_failures'))}`；候选池有目标但最终 Top 10 未命中：`{fmt(overall.get('ranking_failures'))}`；无收益澄清：`{fmt(overall.get('unproductive_clarifications'))}`；override 旧证据残留：`{fmt(overall.get('override_state_failures'))}`",
        f"- 初始化：`{fmt((report.get('benchmark') or {}).get('initialization_seconds'))} s`；response p50/p95：`{fmt((report.get('benchmark') or {}).get('p50_ms'))}` / `{fmt((report.get('benchmark') or {}).get('p95_ms'))} ms`；fallback：`{fmt((report.get('benchmark') or {}).get('fallback_count'))}`",
        f"- 配置：`{fmt({key: config.get(key) for key in ('config_version', 'attribute_retrieval_enabled', 'attribute_reranking_enabled', 'recommendation_with_clarification_enabled', 'override_invalidation_enabled', 'optimized_single_pass_enabled', 'dense_enabled', 'llm_enabled', 'intent_model_mode')})}`",
        "",
        "## 2. 阅读方式",
        "",
        "- `raw_union` 表示精确属性、BM25、Dense 等候选通道合并去重后的排名；`reranked/fused` 表示重排/最终候选池排名。目标已在 raw_union 但未进最终 Top 10，说明问题在排序而不是召回。",
        "- `asked_attribute` 非空表示本轮执行澄清；下一轮会话输入由公开评估器的模拟用户规则生成。",
        "- `override_applied` 表示该 Intent Override 用例已经切换到新目标；`override_state_failure=true` 表示旧偏好仍残留在活动槽位或 query evidence。",
        "- 回退路径包括核心异常安全回退、冲突阻断、0 候选空结果和受控 relaxation；“候选池有目标但最终 Top 10 未命中”只是排序损失，不是运行时异常。",
        "- override 旧证据残留是诊断器对旧偏好字符串仍出现在活动槽位或 `query_evidence` 的标记；它与 D4 发布 gate 的 `scenario_non_regression` 是不同维度，应结合对应 turn 的状态变化阅读。",
        "",
        "## 3. 分场景汇总",
        "",
        "| 场景 | 样本 | Hit@10 | MRR | MTTC | 候选 recall@150 | 无收益澄清 | override 状态失败 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    diagnostics = report.get("retrieval_diagnostics", {}).get("scenarios", {})
    metrics = report.get("scenario_metrics", {})
    for name in sorted(metrics):
        metric = metrics[name]
        diag = diagnostics.get(name, {})
        lines.append(
            f"| {name} | {fmt(metric.get('sample_count'))} | {fmt(metric.get('hit_rate_at_10'))} | {fmt(metric.get('mrr'))} | {fmt(metric.get('mttc'))} | {fmt(diag.get('candidate_recall_at_pool'))} | {fmt(diag.get('unproductive_clarifications'))} | {fmt(diag.get('override_state_failures'))} |"
        )
    lines.extend(["", "## 4. 逐用例逐轮路径", ""])
    for session in report.get("sessions", []):
        lines.extend(render_session(session, products))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render detailed public-set agent path report")
    parser.add_argument("--input", type=Path, default=Path(".runtime/public-d4-trace.json"))
    parser.add_argument("--output", type=Path, default=Path("public_set_agent_trace_report.md"))
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    products: dict[str, dict[str, Any]] = {}
    with args.catalog.open(encoding="utf-8") as handle:
        for line in handle:
            product = json.loads(line)
            products[str(product.get("parent_asin"))] = product
    args.output.write_text(render(report, args.input, products), encoding="utf-8")
    print(json.dumps({"input": str(args.input), "output": str(args.output), "sessions": len(report.get("sessions", []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
