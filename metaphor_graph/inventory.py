# -*- coding: utf-8 -*-
"""全量清单提取：通路 / 准则 / 重构 / 新概念。

**目的**：为"系统总结全部通路、准则、重构与新概念定义"提供**可核对的骨架**，
避免总结时凭印象遗漏。本脚本只做机械提取（AST + 正则），不做判断。

四类定义：
  通路 (pathway)   —— 从输入到输出的可执行数据流（抽取通道、检索通路、
                       构建路线、校验路径）
  准则 (criterion) —— 阈值、门槛、判定规则、不变量
  重构 (refactor)  —— 已实施的修正/重构（含被证伪后的处置）
  新概念 (concept) —— 本项目提出的数据结构/量/机制命名

用法：
    python -m metaphor_graph.inventory                 # 摘要
    python -m metaphor_graph.inventory --json out.json # 落盘
    python -m metaphor_graph.inventory --category pathway
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ROOT))

# 不纳入清单的模块（测试、纯工具）
SKIP = {"test_metaphor_graph.py", "audit_fairness.py", "inventory.py"}


def _iter_modules():
    for f in sorted(os.listdir(ROOT)):
        if f.endswith(".py") and f not in SKIP:
            yield f, os.path.join(ROOT, f)


def _read(p):
    return open(p, encoding="utf-8").read()


# ----------------------------------------------------------------- 通路
# 命名模式：识别"数据流"型函数
PATHWAY_PAT = re.compile(
    r"^(extract|build|retrieve|rank|search|match|link|merge|filter|verify|"
    r"validate|discover|refine|score|select|select_|aggregate|expand|walk|"
    r"propagate|sense|solve|compose|gate|measure|detect|map|align|clean)")


def pathways():
    out = []
    for fname, path in _iter_modules():
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            if not PATHWAY_PAT.match(node.name):
                continue
            doc = ast.get_docstring(node) or ""
            first = doc.strip().split("\n")[0] if doc else ""
            out.append({
                "id": f"{fname}::{node.name}",
                "module": fname,
                "name": node.name,
                "line": node.lineno,
                "doc": first[:120],
                "args": [a.arg for a in node.args.args][:6],
            })
    return out


# ----------------------------------------------------------------- 准则
CRITERION_PAT = re.compile(
    r"^([A-Z][A-Z0-9_]{2,})\s*(?::\s*[^=]+)?=\s*(.+)$")


def criteria():
    out = []
    for fname, path in _iter_modules():
        src = _read(path)
        for i, line in enumerate(src.split("\n"), 1):
            m = CRITERION_PAT.match(line.strip())
            if not m:
                continue
            name, val = m.group(1), m.group(2).strip()
            # 只收"数值型"或"阈值型"常量
            if not re.match(r"^[-0-9.]", val):
                continue
            # 收集紧邻注释作为说明
            ctx = src.split("\n")
            note = ""
            for j in range(i - 2, max(-1, i - 5), -1):
                s = ctx[j].strip()
                if s.startswith("#"):
                    note = s.lstrip("# ").strip()[:100]
                    break
                if s and not s.startswith("#"):
                    break
            out.append({"id": f"{fname}::{name}", "module": fname,
                        "name": name, "line": i, "value": val[:40],
                        "note": note})
    return out


# ----------------------------------------------------------------- 重构
# 从 git 历史与代码注释中提取"修正/重构"记录
REFACTOR_PAT = re.compile(
    r"(实测修正|已修|修复|改为|原实现|原为|此前|曾把|回归护栏|口径修正|"
    r"修正后|统一到|不再|改为走|已改为)")


def refactors():
    out = []
    for fname, path in _iter_modules():
        src = _read(path)
        for i, line in enumerate(src.split("\n"), 1):
            s = line.strip()
            if not s.startswith("#"):
                continue
            if not REFACTOR_PAT.search(s):
                continue
            out.append({"id": f"{fname}:{i}", "module": fname, "line": i,
                        "text": s.lstrip("# ").strip()[:180]})
    return out


# ----------------------------------------------------------------- 新概念
def concepts():
    out = []
    for fname, path in _iter_modules():
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases]
                doc = ast.get_docstring(node) or ""
                first = doc.strip().split("\n")[0] if doc else ""
                out.append({"id": f"{fname}::{node.name}", "module": fname,
                            "name": node.name, "line": node.lineno,
                            "bases": bases, "doc": first[:140],
                            "kind": "class"})
            # 模块级类型别名 / NamedTuple
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                nm = node.target.id
                if nm[0].isupper() and not nm.isupper():
                    out.append({"id": f"{fname}::{nm}", "module": fname,
                                "name": nm, "line": node.lineno,
                                "bases": [], "doc": "", "kind": "alias"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--category",
                    choices=("pathway", "criterion", "refactor", "concept"))
    args = ap.parse_args()

    data = {"pathway": pathways(), "criterion": criteria(),
            "refactor": refactors(), "concept": concepts()}

    if args.category:
        for k, v in enumerate(data[args.category], 1):
            print(f"{k:>4}. [{v['module']}] {v.get('name') or v.get('text','')[:80]}")
        return
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"已写入 {args.json}")
    print("=" * 78)
    print("全量清单提取（机械提取，供人工/subagent 深化）")
    print("=" * 78)
    for k, label in (("pathway", "通路"), ("criterion", "准则"),
                     ("refactor", "重构"), ("concept", "新概念")):
        print(f"  {label:<6} {len(data[k]):>4} 项")
    total = sum(len(v) for v in data.values())
    print(f"  {'合计':<6} {total:>4} 项")
    print()
    print("注：机械提取只保证『不遗漏』，不保证『已理解』。")
    print("    每项的含义、证据、状态需由后续逐项深化补齐。")


if __name__ == "__main__":
    main()
