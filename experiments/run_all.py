# -*- coding: utf-8 -*-
"""一键跑完 Ω 的六个实验（全部离线、$0，串行约 30 秒）。

    <python> experiments/run_all.py

顺序有依赖：exp1 产出 exp1_omega.json，exp2/exp3/exp5/exp6 读它。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    ("exp1_omega_distribution", "分布 + 级联失败归因 + regime"),
    ("exp2_controls", "候选池不变式 + 循环性 + 构造性 + 长度混杂"),
    ("exp3_mechanism", "三通道分解 + Ω_G + 门控等价"),
    ("exp4_natural_families", "非构造查询族 regime"),
    ("exp5_verify", "统计自校验 + bootstrap CI + 长度匹配"),
    ("exp6_substrate", "基底结构诊断（Ω_N 死分量等）"),
]


def main():
    t0 = time.time()
    fails = []
    for mod, desc in STEPS:
        out = os.path.join(HERE, mod.split("_")[0] + "_stdout.txt")
        print(f"=== {mod}  —— {desc}", flush=True)
        with open(out, "w", encoding="utf-8") as f:
            r = subprocess.run([sys.executable, os.path.join(HERE, mod + ".py")],
                               stdout=f, stderr=subprocess.STDOUT, cwd=HERE)
        print(f"    exit={r.returncode}  stdout -> {os.path.basename(out)}",
              flush=True)
        if r.returncode != 0:
            fails.append(mod)
    dt = time.time() - t0
    print(f"\n六个实验完成，用时 {dt:.1f}s")
    if fails:
        print(f"失败：{fails}")
        return 1
    print("全部成功。汇总见 experiments/REPORT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
