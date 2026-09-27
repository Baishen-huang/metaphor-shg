# Search Notes

Date: 2026-09-27
Topic: 凸几何 × 表示学习 ＆ 多 Agent LLM 写作（方向侦察 / 文献整理）

## Safe Queries Used

- convex hull word embeddings geometry arXiv
- "linear representation hypothesis" geometry large language models Park Choe Veitch ICML 2024
- counting linear regions piecewise affine neural networks Montúfar Serra
- "Living on the edge" phase transitions convex optimization intrinsic volumes Amelunxen Lotz McCoy Tropp
- rogue dimensions anisotropy transformer word embeddings Timkey van Schijndel EMNLP
- IsoScore isotropy representation spaces Rudman Eickhoff
- LLM multi-agent collaborative writing survey 2025
- "Agents' Room" narrative generation multi-step collaboration DeepMind
- "Encouraging Divergent Thinking" multi-agent debate Liang EMNLP 2024
- Du Li Torralba Tenenbaum Mordatch "improving factuality and reasoning" multiagent debate
- WritingBench comprehensive benchmark LLM writing evaluation 2025
- "why do multi-agent LLM systems fail" MAST taxonomy Berkeley arXiv
- multi-agent story generation character simulation ACL 2025 arXiv
- AutoGen CAMEL MetaGPT multi-agent framework arXiv 2308.08155 2303.17760 2308.00352
- Chuang simulating opinion dynamics networks LLM-based agents NAACL 2024
- "the geometry of truth" Marks Tegmark emergent linear structure true false datasets

## Verification Performed（arXiv API / 一手页面核验）

- arXiv:2005.02433 = Stolen Probability (Demeter, Kimmel, Downey; ACL 2020) —— 检索快照曾误标为其他标题，已用 abs 页核正
- arXiv:2109.04404 = All Bark and No Bite (EMNLP 2021)
- arXiv:2108.07344 = IsoScore (Findings of ACL 2022)
- arXiv:2503.05244 = WritingBench (2025)
- arXiv:2408.07055 = LongWriter (2024)
- arXiv:2303.17760 = CAMEL（comment 标注 Accepted at NeurIPS'2023）
- 其余 arXiv ID（2311.03658、2310.06824、2410.02603、2305.14325、2308.08155、2308.00352、2501.06322、2503.13657、2406.12665、2311.09618、1303.6672）均由检索结果直接给出 abs 链接

## Excluded Sources

- ResearchGate / Scribd / 博客类快照仅用于发现，不作为最终依据
- MDPI 等政策排除源未纳入

## Unknowns（⧖ 标记项）

- #5 Palominos 2024 的正式卷期信息（Nature 域名链接已核，卷期待核）
- #7 Geometry of Truth 的最终收录 venue（ICLR 2024 OpenReview 在案；最终录用状态未核）
- #8 Toy Models of Superposition 为技术报告，非会议论文（链接凭知识填写，未本次核验）
- #12 Goujon/Etemadi 2024 的正式 venue
- #14 Tran survey、#26 MAST、#27 WritingBench 的 NeurIPS 2025 收录状态来自检索结果，未逐条打开 OpenReview 核验
- #20 为 2025 年 10 月预印本（检索时点信息），状态可能更新
- #4 Ethayarajh 2019 的 ACL Anthology ID（D19-1006）凭知识填写，未本次核验
- #22 的 ACL Anthology 论文页 ID 未核验，现给出卷页链接

## Handoff Notes

- For writing: B2 的占坑对手是 Agents' Room（ICLR 2025）；A1 的占坑对手是 Stolen Probability（ACL 2020）——两个方向各自必引并需写明差异
- For idea optimization: 最有活力的交叉点在 X 带（协作轨迹的几何建模）与 B5（写作专用失败分类）；两者都缺最小信号实验
- For direction scouting: B1 描述性综述已饱和（covered central claim），不要做综述类贡献
- For experiment design: 评测锚用 WritingBench + Tell Me A Story；多 Agent 基线用 Du et al. 辩论（最便宜）；表征协议对齐 Marks true/false 探针
- For review: 若论文主张「凸几何 + 多 Agent」交叉贡献，审稿风险点是 #29（观点动力学桥已存在）与 #16（拓扑 scaling 已有）
