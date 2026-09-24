# -*- coding: utf-8 -*-
"""下载经典隐喻数据集（用于真实文档验证，方案 §实测 P1 门槛）。

运行：python -m metaphor_graph.download_datasets

下载内容：
  1. CCL2018 中文隐喻识别与情感分析（大连理工 DUTIR）—— 中文 P1 验证主数据
  2. VUA / VUA-20 / MOH-X / TroFi（英文）—— 对照基准（需补英文本体）

注意：数据版权归原作者所有，仅限学术研究；禁止商业用途。
"""

from __future__ import annotations

import os
import subprocess

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _run(cmd: str):
    print("+", cmd)
    subprocess.run(cmd, shell=True, check=False)


def main():
    os.makedirs(BASE, exist_ok=True)

    # 1) CCL2018 中文隐喻（含 train/test xml + test_with_label.csv）
    dest = os.path.join(BASE, "CCL2018-Chinese-Metaphor-Analysis")
    if not os.path.isdir(dest):
        _run(f'git clone --depth 1 '
             f'https://github.com/DUTIR-Emotion-Group/CCL2018-Chinese-Metaphor-Analysis.git "{dest}"')
    else:
        print("CCL2018 已存在，跳过克隆。")

    # 2) VUA 英文共享任务（说明 + 可选克隆）
    print("\n[英文 VUA 数据] 如需英文对照基准，任选其一：")
    print("  方式A(推荐): git clone https://github.com/EducationalTestingService/metaphor")
    print("  方式B(Zenodo): https://zenodo.org/records/10721623  (VUAMC.json)")
    print("  方式C(MelBERT 发布版, 含 VUA-18/20, MOH-X, TroFi): https://github.com/linahmoh/MelBERT")
    print("  注: 英文需补英文本体(触发词)，否则当前中文抽取器对英文召回≈0；")
    print("      可扩展 metanet_migrate.BUILTIN 的 triggers 为英文，或接入 LLM 后端。")

    print("\n下载完成。下一步评估：")
    print("  python -m metaphor_graph.evaluate_real                # CCL2018 + 默认中文本体")
    print("  python -m metaphor_graph.evaluate_real --use-metanet # 对比 MetaNet 迁移后本体")


if __name__ == "__main__":
    main()
