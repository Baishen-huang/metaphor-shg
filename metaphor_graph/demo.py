# -*- coding: utf-8 -*-
"""端到端演示：用一段中文样例跑通四层隐喻超超图 + 两类检索。

运行：python -m metaphor_graph.demo
（在 E:\02_AI项目\元图隐喻分析 目录下执行）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaphor_graph import (  # noqa: E402
    MetaphorSHGBuilder, MetaphorMetagraph, MetaphorURetrieval, RetrievalEngine,
    MetaphorHGNN, HLIndex, storage, DEFAULT_ONTOLOGY,
)

# ---------------------------------------------------------------------------
# 样例文档（拆分为 chunk，刻意制造：跨域、扩展隐喻、字面干扰）
# ---------------------------------------------------------------------------
CHUNKS = [
    # 0 跨域案例：字面"推进不动"实际写"泥潭"
    "我们的项目现在陷在泥潭里，每前进一步都要拔出腿来，整个团队都快窒息了。",
    # 1 扩展隐喻（前半句）→ 与 chunk2 合并为跨 chunk 超边
    "别活得像根发条，每天被拧紧了才肯动弹。",
    # 2 扩展隐喻（延伸部分，与 chunk1 同框架同源域）
    "别每天拧紧自己，机械重复的日子里早就没有弹性了。",
    # 3 商战 / 护城河（ARGUMENT_IS_WAR 级联）
    "这场商战里，谁先抢滩谁就守住了护城河，对手只能困在战壕里。",
    # 4 时间就是金钱（TIME_IS_MONEY）
    "我们花在会议上的时间太多了，光是预算讨论就浪费了一整天。",
    # 5 愤怒是热（ANGER_IS_HEAT）
    "看到这个结果我火大，积压的怒火一下子就爆发了。",
    # 6 心智是容器（MIND_IS_CONTAINER）
    "脑子里装满了琐碎的任务，情绪早就满溢出来装不下了。",
    # 7 字面干扰：不应判为隐喻
    "苹果发布了新手机，屏幕比上一代更大。",
]

DOC_ID = "demo_doc"


def banner(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def main():
    banner("0. 本体规模")
    print(DEFAULT_ONTOLOGY.stats())

    banner("1. 构建四层隐喻超超图（L1→L1.5→L2→L3）")
    builder = MetaphorSHGBuilder()
    shg = builder.build(CHUNKS, doc_id=DOC_ID)
    print(shg.summary())
    print("\nL1 隐喻超边明细：")
    for e in shg.edges:
        tag = " [跨chunk扩展]" if e.is_extended else ""
        print(f"  - {e.id}{tag}  {e.source_domain}→{e.target_domain}"
              f"  喻底={e.ground}  触发={e.triggers}  置信={e.confidence}"
              f"  frame={e.frame_id} cascade={e.cascade_id}")
    print("\nL2 框架（超顶点）：")
    for f in shg.frames:
        print(f"  - {f.id} {f.name}  ({len(f.member_mapping_ids)} 条映射)")
    print("\nL3 级联（超超顶点）：")
    for c in shg.cascades:
        print(f"  - {c.id} {c.name}  框架={c.member_frame_ids}")

    banner("2. 扩展隐喻链接验证（chunk1+chunk2 应合并为一条跨 chunk 超边）")
    ext = [e for e in shg.edges if e.is_extended]
    if ext:
        for e in ext:
            spans = sorted({s.chunk_id for s in e.chunk_spans})
            print(f"  ✅ 扩展超边 {e.id} 跨 chunk: {spans}")
            print(f"     合并喻底={e.ground}  触发={e.triggers}")
    else:
        print("  （未检测到扩展隐喻）")

    banner("3. 字面抗干扰验证（chunk7 '苹果' 不应被判为隐喻）")
    from metaphor_graph.extractor import MetaphorExtractor
    ex = MetaphorExtractor()
    lit = ex.extract(CHUNKS[7], doc_id=DOC_ID, chunk_id=f"{DOC_ID}_c7")
    print(f"  chunk7 抽取到的隐喻数 = {len(lit)}  -> "
          f"{'✅ 正确：无字面误判' if len(lit)==0 else '⚠️ 出现误判'}")

    banner("4. 方案 B：隐喻元图 + U-Retrieval")
    mg = MetaphorMetagraph()
    mg.build_from_shg(shg, CHUNKS, doc_id=DOC_ID)
    print(f"  元图节点数={len(mg.nodes)}  L0子图边数={sum(len(v) for v in mg.L0.values())}"
          f"  L2主题边数={len(mg.L2)}")
    ur = MetaphorURetrieval()
    ur.index(CHUNKS, doc_id=DOC_ID)
    res = ur.retrieve("为什么我们的项目推进不动？")
    print("\n  U-Retrieval('为什么我们的项目推进不动？'):")
    print(f"    {res.trace}")
    print(f"    召回 chunk: {res.chunk_ids[:5]}")

    banner("5. 方案 A 共享检索：跨域通路 + RRF 融合")
    eng = RetrievalEngine(shg, CHUNKS, doc_id=DOC_ID)
    cd = eng.cross_domain_retrieve("为什么我们的项目推进不动？")
    print("\n  跨域检索('项目推进不动'):")
    print(f"    {cd.trace}")
    print(f"    命中 chunk: {cd.chunk_ids}")
    if cd.chunk_ids:
        c0 = cd.chunk_ids[0]
        print(f"    证据文本 → [{c0}] {CHUNKS[int(c0.split('_c')[-1])]}")

    banner("6. 多线索汇聚（≥2 个触发词支持的映射优先）")
    clues = eng.multi_clue_retrieval(["泥潭", "战壕", "护城河"])
    print(f"  触发词[泥潭,战壕,护城河] 汇聚结果: {clues}")

    banner("7. 超图版 HyperRetriever（含 type_score 防污染信号）")
    # 取一条映射做评分演示
    demo_edge = next((e for e in shg.edges if e.source_domain == "地形"), None)
    if demo_edge:
        sc = eng.metaphor_retriever_score("项目推进不动", demo_edge)
        print(f"  对映射 {demo_edge.id}({demo_edge.source_domain}→{demo_edge.target_domain})"
              f" 综合得分={sc}（type_score=1 表示通过类型安全约束）")

    banner("8. HGNN 跨层消息传递（L3 级联语义下沉到 L1 实体节点）")
    import numpy as np
    hgnn = MetaphorHGNN(shg, layers=2)
    hgnn.forward()
    ent, cas_node = "机器", "C_LIFE_MACHINE"
    if ent in hgnn.node_index and cas_node in hgnn.node_index:
        def cos(a, b):
            a = np.asarray(a, float); b = np.asarray(b, float)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        ni = hgnn.node_index
        pre = cos(hgnn.X[ni[ent]], hgnn.X[ni[cas_node]])
        post = cos(hgnn.H[ni[ent]], hgnn.X[ni[cas_node]])
        print(f"  实体节点 '{ent}' 与级联 {cas_node} 的语义相似度：")
        print(f"    传播前 = {pre:.3f}  →  传播后 = {post:.3f}  "
              f"({'✅ 级联语义已下沉' if post > pre else '⚠️ 未提升'})")
        print("  （跨层超图卷积使 L3 级联向量混入 L1 实体表示；")
        print("    注：此处用哈希向量做原理验证，真实语义增益需替换为句向量模型）")

    banner("9. HL-index 可达性索引（触发词→可达目标域）")
    hl = HLIndex(shg)
    reach = hl.reachable_targets("发条")
    print(f"  '发条' 沿超图可达的目标概念: {reach}")

    banner("10. 导出（Neo4j Cypher + JSON）")
    out_dir = os.path.dirname(os.path.abspath(__file__))
    cypher = storage.shg_to_cypher(shg)
    cypher_path = os.path.join(out_dir, "export_shg.cypher")
    with open(cypher_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cypher))
    json_path = os.path.join(out_dir, "export_shg.json")
    storage.shg_to_json(shg, json_path)
    print(f"  Neo4j 写入语句: {cypher_path}  ({len(cypher)} 条)")
    print(f"  JSON 导出:      {json_path}")

    banner("✅ 端到端运行完成")


if __name__ == "__main__":
    main()
