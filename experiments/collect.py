# -*- coding: utf-8 -*-
"""收集各并行实验方向的报告与状态，生成汇总看板。

用法：
    python experiments/collect.py            # 打印状态
    python experiments/collect.py --write    # 写入 实验结论汇总.md

每个方向在 .wt/<name>/experiments/ 下产出 REPORT.md。本脚本不解析报告内容
（各方向结论形态不同），只做存在性、提交状态与关键数字的机械汇总，
最终判读仍需人工阅读 REPORT.md。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WT = os.path.join(ROOT, ".wt")

# 项目解释器（含 jieba/numpy）；可用 METAPHOR_PY 覆盖
PY = os.environ.get("METAPHOR_PY") or (
    "C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/"
    "venv_jieba/Scripts/python.exe")

DIRECTIONS = {
    "dynamics": "算子动力学（源项 / 谱性质 / flat-HGNN 平局）",
    "source": "特征口径一致性（type 特征 1.0 vs 0.0）",
    "omega": "查询侧可观测泛函 Ω",
    "degrade": "降级来源封顶可靠度通道",
}


def _run(cmd, cwd):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=900)
        # unittest 把结果写到 stderr，合并两路
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


def status(name: str) -> dict:
    d = os.path.join(WT, name)
    info = {"name": name, "desc": DIRECTIONS.get(name, ""), "exists": os.path.isdir(d)}
    if not info["exists"]:
        return info
    report = os.path.join(d, "experiments", "REPORT.md")
    info["report"] = os.path.isfile(report)
    info["report_lines"] = (sum(1 for _ in open(report, encoding="utf-8"))
                            if info["report"] else 0)
    info["branch"] = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], d)
    info["dirty"] = bool(_run(["git", "status", "--porcelain"], d))
    info["commits"] = _run(["git", "log", "--oneline", "main..HEAD"], d)
    info["n_commits"] = len(info["commits"].splitlines()) if info["commits"] else 0
    # 测试状态：跑各方向自己的测试套件（隔离 worktree，互不影响）
    interp = PY if os.path.isfile(PY) else sys.executable
    info["tests"] = _run([interp, "-m", "unittest",
                          "metaphor_graph.test_metaphor_graph"], d)[-600:]
    info["n_tests"] = _extract_tests(info["tests"])
    return info


def _extract_tests(out: str) -> str:
    m = re.search(r"Ran (\d+) tests", out)
    ok = "OK" in out
    if not m:
        return "?"
    return f"{m.group(1)} {'OK' if ok else 'FAIL'}"


def key_numbers(name: str) -> list:
    """从 REPORT.md 里机械抽取带数字的行，供人工快速判读。"""
    p = os.path.join(WT, name, "experiments", "REPORT.md")
    if not os.path.isfile(p):
        return []
    rows = []
    for line in open(p, encoding="utf-8"):
        s = line.strip()
        # 表格行或含数字的结论行
        if s.startswith("|") and re.search(r"\d", s):
            rows.append(s)
        elif re.search(r"(?i)(verdict|结论|SUPPORTED|REFUTED|UNDETERMINED)", s) and re.search(r"\d|SUPPORT|REFUT|UNDETER", s):
            rows.append(s)
    return rows[:24]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="写入 实验结论汇总.md")
    args = ap.parse_args()

    print(f"实验根目录: {WT}\n")
    infos = [status(n) for n in DIRECTIONS]
    for i in infos:
        flag = "✅" if i.get("report") else ("⏳" if i["exists"] else "❌")
        print(f"{flag} {i['name']:<10} {i['desc']}")
        if not i["exists"]:
            print("     worktree 不存在")
            continue
        print(f"     分支={i.get('branch')} 提交={i.get('n_commits')} "
              f"未提交改动={'有' if i.get('dirty') else '无'} 单测={i.get('n_tests')}")
        if i.get("report"):
            print(f"     报告 {i['report_lines']} 行")
            for r in key_numbers(i["name"])[:6]:
                print(f"       {r[:150]}")

    if args.write:
        out = os.path.join(ROOT, "experiments", "实验结论汇总.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write("# 实验结论汇总（自动生成）\n\n")
            f.write("> 由 `python experiments/collect.py --write` 生成。\n")
            f.write("> 数字为机械抽取，最终判读请阅读各方向 `REPORT.md`。\n\n")
            for i in infos:
                f.write(f"## {i['name']} — {i['desc']}\n\n")
                if not i.get("report"):
                    f.write("状态：报告未产出。\n\n")
                    continue
                f.write(f"- 分支：`{i.get('branch')}`，提交数：{i.get('n_commits')}，"
                        f"单测：{i.get('n_tests')}\n\n")
                rows = key_numbers(i["name"])
                if rows:
                    f.write("关键数字（机械抽取）：\n\n")
                    for r in rows:
                        f.write(f"    {r}\n")
                    f.write("\n")
        print(f"\n已写入 {out}")


if __name__ == "__main__":
    main()
