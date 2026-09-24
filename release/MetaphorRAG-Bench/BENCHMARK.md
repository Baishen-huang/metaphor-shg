# MetaphorRAG-Bench（v0.1）
1. bench_docs.json：2 篇诊疗文档（11/7 chunk，含字面干扰与跨距负样本）。
2. bench_queries.json：652 条改写查询（触发词红线过滤后）+ LLM 非构造金标
   （一致性 96.8%；按确定性边 id 映射到 chunk 集合）。
   评测协议：查询 → 语义超图排序 → Recall@10 / MRR@10（金标 chunk 集合）。
3. bench_extended_chains.json：106 篇连贯文档语料抽取的 52 条候选扩展链
   （含链上 chunk 原文），供扩展隐喻消歧研究；LLM 校验判定见
   chain_verify/llm_cache_corups.verify.json（21.1% 通过率）。
引用本基准请注明构建管线（MetaphorSHG v0.2，见论文附录 A）。
