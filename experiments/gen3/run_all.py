# -*- coding: utf-8 -*-
"""gen3 一键复现：数据收集 + 六个实验（全部离线、$0）。

    <python> experiments/gen3/run_all.py            # 全部（约 3–5 分钟）
    <python> experiments/gen3/run_all.py --fast     # 跳过置换检验最重的部分

产物：experiments/gen3/dataset_*.json + exp_g3_*.json + *_stdout.txt
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

STEPS = [
    ("_collect.py", ["--rule", "json"]),
    ("_collect.py", ["--rule", "source"]),
    ("_collect.py", ["--rule", "metanet"]),
    ("_collect.py", ["--rule", "source_type"]),
    ("exp_g3_1_baseline.py", []),
    ("exp_g3_2_mechanism.py", []),
    ("exp_g3_3_candidates.py", []),
    ("exp_g3_4_downstream.py", []),
    ("exp_g3_5_verdict.py", []),
    ("exp_g3_6_conditional.py", []),
    ("exp_g3_7_squery.py", []),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="给收集脚本加 --force 之外不改行为；保留给将来更重的检验")
    args = ap.parse_args()
    t0 = time.time()
    for i, (script, extra) in enumerate(STEPS, 1):
        path = os.path.join(HERE, script)
        cmd = [PY, path] + extra
        print(f"\n{'#' * 90}\n# [{i}/{len(STEPS)}] {script} {' '.join(extra)}"
              f"\n{'#' * 90}", flush=True)
        t = time.time()
        r = subprocess.run(cmd, cwd=os.path.dirname(HERE))
        print(f"# [{i}/{len(STEPS)}] {script} 退出码 {r.returncode}"
              f"  用时 {time.time() - t:.1f}s", flush=True)
        if r.returncode != 0:
            print(f"!! {script} 失败，中止")
            return r.returncode
    print(f"\n全部完成，总用时 {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
