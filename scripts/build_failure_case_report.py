from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "public_set": ("data/public_set.jsonl", ".runtime/phase2-final-public-diagnostic.json", ".runtime/phase2-final-public.json"),
    "owntest": ("data/owntest.jsonl", ".runtime/phase2-final-own-diagnostic.json", ".runtime/phase2-final-own.json"),
    "owntest2": ("data/owntest2.jsonl", ".runtime/phase2-final-own2-diagnostic.json", ".runtime/phase2-final-own2.json"),
}
OUT = ROOT / "phase2_low_score_case_analysis.md"


def read_jsonl(path: Path) -> dict[str, dict]:
    return {row["sample_id"]: row for row in map(json.loads, path.open(encoding="utf-8"))}


def catalog_index(path: Path) -> dict[str, dict]:
    result = {}
    for row in map(json.loads, path.open(encoding="utf-8")):
        result[row["parent_asin"]] = row
    return result


def fmt(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def selected_turn(session: dict) -> dict:
    turns = session.get("turns", [])
    if not turns:
        return {}
    ranked = []
    for turn in turns:
        ranks = turn.get("target_ranks", {})
        values = [r for r in (ranks.get("reranked"), ranks.get("fused")) if r is not None]
        ranked.append((min(values) if values else 10_000, turn))
    return min(ranked, key=lambda item: (item[0], item[1].get("turn", 0)))[1]


def rank_gap(rank: int | None) -> str:
    if rank is None:
        return "未产生排名"
    if rank == 1:
        return "理想"
    return f"距理论 Rank 1 差 {rank - 1} 位"


def main() -> None:
    catalog = catalog_index(ROOT / "data/catalog.jsonl")
    reports = {}
    for name, (dataset_path, diagnostic_path, _) in DATASETS.items():
        source = read_jsonl(ROOT / dataset_path)
        diagnostic = json.loads((ROOT / diagnostic_path).read_text(encoding="utf-8"))
        sessions = diagnostic["sessions"]
        low = []
        for session in sessions:
            rank = session.get("best_rank")
            pool_rank = session.get("best_pool_rank")
            if rank is None or rank > 10 or len(session.get("turns", [])) >= 6:
                row = source.get(session["sample_id"], {})
                turn = selected_turn(session)
                target = session.get("target_parent_asin")
                product = catalog.get(target, {})
                ranks = turn.get("target_ranks", {})
                low.append({
                    "session": session,
                    "source": row,
                    "turn": turn,
                    "product": product,
                    "ranks": ranks,
                    "priority": (0 if rank is None else 1 if rank > 10 else 2, -(len(session.get("turns", [])))),
                })
        low.sort(key=lambda item: item["priority"])
        reports[name] = (diagnostic, low)

    lines = [
        "# Phase 2 超低分 Case-Level 分析",
        "",
        "> 生成时间：2026-08-29。数据来自最终保留版本的 `.runtime/phase2-final-*-diagnostic.json`；未修改 evaluator、数据集或标签。",
        "",
        "## 阅读说明",
        "",
        "理论理想值：目标商品应进入最终 Top-10，理想排名为 Rank 1，理想 reciprocal rank 为 1.0000；对话最多 10 轮，但明确需求后应尽早停止无信息增益澄清。",
        "",
        "本报告只展开低质量 case：目标未进 Top-10、目标未进候选池，或 MTTC 对应的对话达到 6 轮以上。`best_rank` 是所有 turn 中目标的最佳最终排名；`best_pool_rank` 是候选池中的最佳排名；二者都为 N/A 表示该阶段没有目标。",
        "",
        "## 总体指标",
        "",
        "| 数据集 | TechnicalScore | Hit@10 | MRR | MTTC | candidate recall@150 | ranking failures | unproductive clarifications | override failures | p95(ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, (diagnostic, _) in reports.items():
        benchmark = json.loads((ROOT / DATASETS[name][2]).read_text(encoding="utf-8"))
        overall = diagnostic["retrieval_diagnostics"]["overall"]
        lines.append(
            f"| {name} | {fmt(diagnostic['recommended_technical_score'])} | {fmt(diagnostic['hit_rate_at_10'])} | {fmt(diagnostic['mrr'])} | {fmt(diagnostic['mttc'])} | {fmt(overall['candidate_recall_at_pool'])} | {fmt(overall['ranking_failures'])} | {fmt(overall['unproductive_clarifications'])} | {fmt(overall['override_state_failures'])} | {fmt(benchmark['benchmark']['response_p95_ms'])} |"
        )

    for name, (diagnostic, low) in reports.items():
        no_top10 = [x for x in low if x["session"].get("best_rank") is None or x["session"].get("best_rank") > 10]
        high_mttc = [x for x in low if len(x["session"].get("turns", [])) >= 6]
        lines += [
            "",
            f"## {name}",
            "",
            f"低质量 case 总数：{len(low)}；未进 Top-10：{len(no_top10)}；MTTC >= 6：{len(high_mttc)}。",
            "",
            "### 低质量 Case 表",
            "",
            "| sample_id | scenario | category | difficulty | 首轮用户输入 | target parent_asin | target title | best rank | pool rank | raw union rank | reciprocal rank | turns | unproductive | override failure | stage ranks | 实际 Top-10 | 理论差距 |",
            "|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
        ]
        for item in low:
            s, row, turn, product, ranks = item["session"], item["source"], item["turn"], item["product"], item["ranks"]
            first_message = (s.get("turns") or [{}])[0].get("user_message", "")
            stage = ", ".join(f"{k}={v if v is not None else 'N/A'}" for k, v in ranks.items())
            top10 = ", ".join(turn.get("top10", []))
            rank = s.get("best_rank")
            lines.append(
                f"| {s.get('sample_id')} | {row.get('scenario_type', s.get('scenario_type'))} | {row.get('category_bucket', 'N/A')} | {row.get('difficulty_bucket', 'N/A')} | {fmt(first_message)} | {s.get('target_parent_asin')} | {fmt(product.get('title', 'N/A'))} | {fmt(rank)} | {fmt(s.get('best_pool_rank'))} | {fmt(s.get('best_raw_union_rank'))} | {fmt(s.get('reciprocal_rank'))} | {len(s.get('turns', []))} | {s.get('unproductive_clarifications', 0)} | {s.get('override_state_failure', False)} | {stage} | {top10 or 'N/A'} | {rank_gap(rank)} |"
            )
        lines += [
            "",
            "### 人工排查重点",
            "",
            "- `best_pool_rank=N/A`：优先检查 query 解析、属性召回、hard filter 和 BM25/attribute channel 是否漏召回。",
            "- `best_pool_rank<=150` 但 `best_rank>10` 或 N/A：优先检查 reranker 的字段权重、phrase/conjunction 处理和 buying/browsing 路由污染。",
            "- `turns>=6`：对照每轮 `candidate_count`、`top10`、`asked_attribute` 和 `policy_reason`，判断是候选持续波动、无效澄清还是目标始终排名过低。",
            "- `override failure=true`：检查 override/clear/negation 后旧 query evidence 是否仍参与检索。",
        ]

    lines += [
        "",
        "## 结论与建议",
        "",
        "1. 最值得优先人工分析的是 owntest2：74 个 case 未进入最终 Top-10，其中多数仍有候选池排名，说明 ranking failure 与候选生成同时存在，但应先按 `pool_rank` 分层。",
        "2. boundary 样例数量少但对话成本高；不要仅依据平均 MTTC 调整全局澄清阈值，应逐轮确认候选 fingerprint 是否真正变化。",
        "3. 本阶段保留的 buying attribute ranking 改动改善了陌生集 MRR，但报告中的低分 case 仍显示大量目标在候选池内排名靠后，后续手动调优应优先从这些共同特征入手。",
        "",
        "## 数据来源",
        "",
        "- `data/public_set.jsonl` + `.runtime/phase2-final-public-diagnostic.json`",
        "- `data/owntest.jsonl` + `.runtime/phase2-final-own-diagnostic.json`",
        "- `data/owntest2.jsonl` + `.runtime/phase2-final-own2-diagnostic.json`",
        "- `data/catalog.jsonl`（仅用于读取目标商品标题，不作为 session dataset 评测输入）",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
