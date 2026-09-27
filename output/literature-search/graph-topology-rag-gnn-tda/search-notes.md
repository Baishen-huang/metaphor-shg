# Search Notes

Date: 2026-09-27

## Safe Queries Used

- GraphRAG graph retrieval-augmented generation survey
- GNN-RAG graph neural retrieval large language model reasoning arxiv
- topological data analysis text corpora persistent homology NLP
- persistent homology word embeddings topology sentence embeddings analysis arxiv
- HippoRAG LightRAG RAPTOR graph-based retrieval augmented generation comparison
- simplicial attention network text classification topological signal processing
- topological regularization representation learning topological autoencoders PersLay
- topological analysis large language model latent space representations geometry
- "topological" "retrieval-augmented generation" persistent homology retrieval
- Minh Vu topological retrieval augmented generation persistent homology（定位 HPT-TRACE）
- arxiv "Topological Retrieval-Augmented Generation" HPT-TRACE hierarchical partition tree
- "From Local to Global" Graph RAG Edge 2024
- persistent homology knowledge graph topology analysis complex networks arxiv
- HippoRAG 2405.14831 / "From RAG to Memory" 2502.14802 核实
- "Graph Retrieval-Augmented Generation: A Survey" Boci arxiv
- Papamarkou "Topological Deep Learning" survey
- "TopoRAG" OR "T-Retriever" topology retrieval augmented generation

## Sources Checked（一手页面核实记录）

- arXiv abs 页已打开核实：2501.00309（GraphRAG survey, Han et al.）、2411.10298（TDA×NLP survey, Uchendu & Le, KDD Explorations 2026）、2401.18059（RAPTOR）、1809.05679（TextGCN, AAAI 2019）、2410.05779（LightRAG）、2410.20724（SubgraphRAG）、2410.11001（实为 Graph of Records，非综述）、0811.2203（PH of Complex Networks, Horak/Maletic/Rajkovic——搜索摘要误标为 Horak & Jost，已纠正）。
- IJCAI 2013 论文集 PDF（Zhu, PH for NLP）、ACL Anthology W17-2628（Michel 2017）、2020.starsem-1.11（Jakubowski 2020）、JMLR vol.25 23-1185（Hiraoka）—— proceedings 页面确认。
- OpenReview qSaRIuBuYx（HPT-TRACE）：页面被 Cloudflare 验证拦截，API 跳转 challenge；论文信息来自多次检索返回的评审页摘要与 Google Scholar 条目，作者全名与正式结论未核实。
- 2401.12041 打开核实后为量子物理论文（非拓扑深度学习综述）——已弃用；TDL 综述实际为 2402.08871（Papamarkou et al., position）与 2304.10031（Hajij et al., 架构综述）。
- 1803.01271 打开核实后为 TCN 论文（Bai et al.），非 TextGCN——TextGCN 实为 1809.05679，已纠正。

## Excluded Sources

- MDPI Mathematics（Sekuloski 2026, TDA for language models；Chen et al. persistence-sensitive skipping）：政策排除（MDPI），仅在此记录。
- ResearchGate 无 peer-review 信息条目、博客类（Pebblous、Medium、IBM、知乎翻译、YouTube）：不作为证据。
- EmergentMind、CatalyzeX、alphaXiv、hypepaper 等聚合站：仅用于定位一手链接。

## Unknowns

- G1（HPT-TRACE）的正式作者名单、投稿 venue、评审状态：仅 OpenReview id + 检索摘要，需人工打开原文。
- B3（T-Retriever）arXiv 编号未核实（仅 InsightArxiv/alphaXiv 收录记录）。
- D5（arXiv 2404.00500）准确标题未核实。
- GraphRAG-Bench、ACM「In-Depth Analysis of Graph-Based RAG in a Unified Framework」未打开原文。
- RAPTOR 的 ICLR 接收状态未核实（abs 页未标注），论文表按 arXiv 记。
- 「TopoRAG = ICLR 2026」的说法经查为 IoT 论文中的术语，非独立论文——不要引用。

## Handoff Notes

- For writing（Related Work）：建议主线引用 A1+A2/A3（图 RAG 谱系）、B1（GNN×RAG）、D1（TDA×NLP 边界）、G1（拓扑×RAG 最近邻）、D3（负结果）；分层组织引 A6。
- For idea optimization：见同目录 idea-grounding.md。
- For experiment design：基准与 baseline 组合见 papers.md Benchmark 节；对照系至少含 HippoRAG 2 / LightRAG / SubgraphRAG / RAPTOR。
- For review（若审到拓扑+RAG 投稿）：重点核查是否引用 HPT-TRACE 与 Michel 2017 负结果。
