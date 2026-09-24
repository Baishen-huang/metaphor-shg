# 数据、许可与复现边界

本文件说明：**哪些内容在本仓库里、哪些不在、以及为什么**。在做任何发布或再分发
之前请先读完。

---

## 1. 本仓库不包含语料（`data/` 已排除）

`.gitignore` 排除了整个 `data/`。原因是许可，不是体积：

| 语料 | 规模 | 许可状态 | 能否随仓库分发 |
|---|---|---|---|
| CCL2018 中文隐喻识别与情感分析 | 测试集 1,100 句 / 训练集 4,075 句 | 大连理工 DUTIR 评测共享任务，**仅限学术研究** | ❌ 否 |
| 人民网财经新闻 | 40 篇 | 新闻媒体版权 | ❌ 否 |
| 政府工作报告 | 6 篇（维基文库） | 公版 | ⚠️ 可，但为一致性一并排除 |
| 鲁迅全集散文 | 60 篇（公版） | 公版 | ⚠️ 可，但为一致性一并排除 |

**关键点**：`data/llm_cache_deepseek.json` 的缓存**键就是 CCL2018 测试集原句**
（1,100 条），`data/llm_cache_train.json` 的键是训练集原句（4,074 条）。这些文件
虽然不含密钥，但**包含第三方评测数据集的原文**，因此一并排除，不得发布。

### 如何自行获取语料

```bash
python -m metaphor_graph.download_datasets
```

该脚本会拉取 CCL2018 数据集（含 train/test xml 与 `test_with_label.csv`）。
英文对照基准（VUA / VUA-20 / MOH-X / TroFi）同样由该脚本获取。

**注意**：数据版权归原作者所有，仅限学术研究，禁止商业用途。请遵守各数据集
自身的许可条款。

---

## 2. 本仓库包含的内容（以及其许可依据）

| 内容 | 是否含原句 | 许可依据 |
|---|---|---|
| `metaphor_graph/`（代码） | 否 | 见 LICENSE |
| `metaphor_graph/ontology_default.json`（2,177 框架） | **否**（已扫描验证：0 条测试集原句） | 由训练集构建，仅含概念域/喻底/触发词字段 |
| `metaphor_graph/ontology_bilingual.json`（英文对齐） | **否** | 同上；`auto_gloss` 为域级词典机器转写，**不主张**对应英文隐喻在 MetaNet 中真实存在 |
| `release/MetaphorRAG-Bench/bench_queries.json`（632 条改写查询） | **否**（LLM 生成的查询，非语料原文） | 见 LICENSE |
| `release/MetaphorRAG-Bench/bench_extended_chains.json` | ⚠️ 含 **106 条新闻标题**与 11 条 span 元数据 | 标题属合理引用范畴，但如需完全规避风险可自行剔除 |

### 论文中的示例句

`论文初稿.md` / `论文初稿_en.md` 各含 **1 条** CCL2018 测试集句子，作为说明
"标注存疑"的**单句引用示例**（学术评论语境下的合理引用）。代码与本体资源中
已**不含任何**语料原文——`test_metaphor_graph.py`、`demo_llm.py` 等文件中原有的
示例句已替换为人工构造的等价句（功能完全一致，116 项单测通过）。

### 本体资源的派生许可提示

`ontology_default.json` 由 CCL2018 **训练集**经 LLM 自举构建（见
`release/metaphor_resources/DATASET_CARD.md`）。本体只保留抽象的概念域、喻底
集合与触发词，**不含句子原文**，但它属于评测数据的派生作品。因此本体的发布
沿用**学术研究**口径，与代码许可分开（见 LICENSE 第 2 节）。

---

## 3. 复现边界：缓存与 API

### 零 API 费用重放

所有需要真实 LLM 的阶段均已落盘缓存，重放不发起任何请求：

```
discover / refine / 查询改写 / 相关性判定 / 链校验 / 常识关联 / 生成
```

缓存键为**确定性 id（md5）**，跨进程可复现，并有单测护栏。这意味着：论文中
全部表格都可以在不配置任何 API 密钥的情况下重放。

### 需要 API 的阶段

若要从头构建（而非重放），需设置环境变量：

```bash
export LLM_API_KEY=...      # 必需
export LLM_BASE_URL=...     # 可选，默认 OpenAI 端点
export LLM_MODEL=...        # 可选
```

代码**不硬编码任何密钥**，全部经环境变量读取。未配置时相关阶段会告警并跳过
（返回空结果），不会崩溃。

---

## 4. 复现环境

项目使用独立 venv（jieba + numpy）：

```bash
python -m venv venv_jieba
venv_jieba/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source venv_jieba/bin/activate && pip install -r requirements.txt  # Linux/macOS
```

已验证版本：Python 3.13.12、jieba 0.42.1、numpy 2.5.3。

**注意**：`bootstrap_triggers.py` 依赖 jieba，缺少时以 `SystemExit` 提示而非
静默降级。相关单测在无 jieba 环境下会 skip。

自检：

```bash
python -m unittest metaphor_graph.test_metaphor_graph    # 应为 116 项通过
```

---

## 5. 已知边界

1. **向量器双口径**：主表用哈希向量（可离线复现）；真实句向量结果（+21pp）
   基于单一厂商单模型，转正前需统一重测。
2. **金标来源**：改写查询与相关性判定由同一 LLM 生成/判定（构造一致性 96.8%）；
   跨模型二评 Cohen's κ = 0.965。全量真人复核仍建议。
3. **扩展链精度**：双段管线后 63.6%（7/11），校验与抽取同厂商。
4. **A6 替代口径**：常识关联由 LLM 生成而非 ConceptNet 本体（502 阻塞）。
5. **语料边界**：鲁迅部分（1920 年代白话）L1 基数低，跨语时代泛化是已知边界。
6. **单语言**：框架与本体为中文；英文资源为对齐标注而非独立英文抽取本体。

详见 [论文初稿.md](论文初稿.md) §8。
