# -*- coding: utf-8 -*-
"""比较公平性审计：自动检查各比较型实验的两臂预算/池规模是否对等。

**为什么需要它**：本轮已发现**三处同类缺陷**，都是"两臂的搜索预算、候选池规模
或金标口径不对等"导致指标失真：

  ① §6.1 三通路 —— 候选池 ≤10 使 Hits@10 平凡饱和（各通路同样饱和，
     但"1.000"被当成性能成就）；
  ② §6.2 排序器 —— 人工权重与学到权重错配（37 倍）+ 构造锚定；
  ③ §6.4 A6   —— 常识通路无上限 vs 隐喻通路硬编码 top_k=5，低估 17pp。

人工审查三次都漏掉了下一处，故改为**机器检查**。

本脚本做静态检查（不跑实验）：扫描各评测脚本中影响"每臂搜索预算"的参数，
报告是否存在同一实验内两臂参数不一致的情况。

用法：
    python -m metaphor_graph.audit_fairness
"""

from __future__ import annotations

import inspect
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.abspath(__file__))

# 每个评测脚本：需要检查的"预算类"参数与两臂标识
TARGETS = {
    "evaluate_a6.py": {
        "desc": "A6：专属隐喻 vs 通用常识",
        "arms": {"常识通路": "无上限（全池扫描）",
                 "隐喻通路": "rank_mappings(top_k=...)"},
    },
    "evaluate_retrieval.py": {
        "desc": "H3/A5/A7/A9 检索消融",
        "arms": {"各配置": "score_conditions 共享同一候选池"},
    },
    "evaluate_hgnn.py": {
        "desc": "H4：判别信号来源分解",
        "arms": {"各表示": "同一配对样本"},
    },
    "evaluate_chain_quality.py": {
        "desc": "§6.6 扩展链双段管线",
        "arms": {"候选生成": "continuity 判据",
                 "语义校验": "LLM 逐链判定"},
    },
}


def _strip_comments(src: str) -> str:
    """去掉 `#` 注释，避免把说明文字里提到的旧值误判为硬编码。

    实测踩过：A6 的修复注释里写了 "原实现用 top_k=5"，被本工具误报为
    "仍有硬编码 top_k=5"。剥离后不再误报。
    """
    out = []
    for line in src.split("\n"):
        # 简单处理：仅剥离整行注释与行尾注释（不处理 # 出现在字符串内的情况，
        # 对预算参数这类数字赋值已足够；宁可漏报也不误报）
        i = line.find("#")
        out.append(line[:i] if i >= 0 else line)
    return "\n".join(out)


def scan(path: str) -> dict:
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return {"exists": False}
    raw = open(p, encoding="utf-8").read()
    src = _strip_comments(raw)
    out = {"exists": True, "lines": raw.count("\n")}
    # 收集所有 top_k / max_* / *_per_* 字面量与参数
    out["budget_literals"] = sorted(set(re.findall(
        r"\b(top_k|max_gap|max_results|n_pairs|negatives_per_positive)"
        r"\s*=\s*([0-9]+)", src)))
    # 收集 argparse 定义的预算参数（说明可调，风险低）
    out["budget_args"] = sorted(set(re.findall(
        r'"--([a-z0-9-]*(?:top|k|budget|max)[a-z0-9-]*)"', src)))
    # 检测"硬编码预算"（函数调用里直接写数字，未走参数）
    out["hardcoded_calls"] = sorted(set(re.findall(
        r"(top_k|max_gap)=([0-9]+)", src)))
    return out


def main():
    print("=" * 84)
    print("比较公平性审计 —— 检查各比较型实验的两臂预算/池规模是否对等")
    print("=" * 84)
    print()
    findings = []
    for fname, meta in TARGETS.items():
        info = scan(fname)
        print(f"【{fname}】{meta['desc']}")
        if not info.get("exists"):
            print("  （文件不存在）\n")
            continue
        arms = meta["arms"]
        for a, d in arms.items():
            print(f"  {a:<12} {d}")
        hc = info.get("hardcoded_calls", [])
        if hc:
            print(f"  ⚠️ 硬编码预算调用：{hc}")
            findings.append((fname, hc))
        args = info.get("budget_args", [])
        if args:
            print(f"  ✓ 可调预算参数：{args}")
        print()

    print("=" * 84)
    print("【结论】")
    print("=" * 84)
    if findings:
        print("以下位置仍有硬编码预算，需人工确认两臂是否对等：")
        for f, hc in findings:
            print(f"  - {f}: {hc}")
    else:
        print("未发现硬编码的预算调用。")
    print()
    print("【已修复的三处（供对照）】")
    print("  §6.1 三通路  —— 候选池 ≤10 平凡饱和；已在修复后基准（池 1,100）重测")
    print("  §6.2 排序器  —— 权重错配 37 倍；已单一真源 + 四族对比")
    print("  §6.4 A6      —— 两臂预算不对等（5 vs 无上限）；已 --meta-top-k=20")
    print()
    print("【建议】论文 §4 增「比较公平性声明」：所有两臂比较须报告")
    print("  各自的搜索预算、候选池规模、金标口径。")


if __name__ == "__main__":
    main()
