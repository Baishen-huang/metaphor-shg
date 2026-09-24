# MetaphorSHG 中文级联本体（v1.0）
- 来源：CCL2018 训练集 LLM 自举（glm-5.3-flash，置信≥0.85）→ 清洗（删自环/
  清喻底/支持度分层）→ 生产沉淀。构建脚本：`metaphor_graph/ontology_clean.py`。
- schema：FrameSpec{id, name, mapping_type, source_domain, target_domain, ground,
  triggers, source_type, support, tier}；CascadeSpec{id, name, member_frames,...}。
- 双语：ontology_bilingual.json 每框架含 en_name（curated=MetaNet 内置一致 /
  auto_gloss=词汇级转写，**不主张**该英文隐喻在 MetaNet 真实存在）。
- 口径：本体只用训练集构建，测试集仅评估；支持度与分层见 provenance.stats。
- 许可：语料与本体仅供研究使用；引用格式见仓库 README。
