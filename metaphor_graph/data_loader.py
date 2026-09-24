# -*- coding: utf-8 -*-
"""真实数据集加载器：CCL2018 中文隐喻 + VUA 英文隐喻。

统一为 MetaphorSample(text, gold_metaphor, label_raw, split, source)，
供 evaluate_real.py 做 P1 字面误判率硬门槛验证（方案 §6.5）。

CCL2018 子任务一标签：0=中性(字面) / 1=动词隐喻 / 2=名词隐喻
    → gold_metaphor = label in (1, 2)
VUA 共享任务：token 级 label 0/1，按句聚合（任一 token 隐喻 → 句隐喻）
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MetaphorSample:
    text: str
    gold_metaphor: bool
    label_raw: object
    split: str
    source: str


def _default_ccl_path() -> Optional[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, "..", "data", "CCL2018-Chinese-Metaphor-Analysis",
                        "dataset", "subtask1-metaphor-recognition", "test_with_label.csv")
    cand = os.path.abspath(cand)
    return cand if os.path.exists(cand) else None


def load_ccl2018(csv_path: str = None, split: str = "test") -> List[MetaphorSample]:
    """加载 CCL2018 子任务一标注数据（中文）。

    csv 列：ID, Sentence, Label。Label 0=中性(字面)，1=动词隐喻，2=名词隐喻。
    句子内部可能含逗号（引号包裹），用 csv.reader 解析后合并中间列、取末列标签。
    """
    path = csv_path or _default_ccl_path()
    if not path or not os.path.exists(path):
        raise FileNotFoundError(
            f"未找到 CCL2018 标注文件，请先运行 download_datasets.py。期望路径: {path}")
    samples: List[MetaphorSample] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # 跳过表头 ID,Sentence,Label
        for row in reader:
            if len(row) < 3:
                continue
            text = ",".join(row[1:-1]).strip()   # 跳过 ID 列，合并可能为多列的句子
            label = row[-1].strip()
            if not text:
                continue
            try:
                lab = int(label)
            except ValueError:
                continue
            samples.append(MetaphorSample(
                text=text, gold_metaphor=lab in (1, 2),
                label_raw=lab, split=split, source="ccl2018"))
    return samples


def load_vua_csv(csv_path: str, split: str = "test") -> List[MetaphorSample]:
    """加载 VUA 共享任务 tsv：index, label, sentence, POS, w_index。按句聚合。"""
    samples: List[MetaphorSample] = []
    cur_id = None
    cur_text = None
    cur_met = False

    def _flush():
        if cur_id is not None and cur_text:
            samples.append(MetaphorSample(
                text=cur_text, gold_metaphor=cur_met,
                label_raw=cur_id, split=split, source="vua"))

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 5:
                continue
            idx, label, sent = row[0], row[1], row[2]
            if idx != cur_id:
                _flush()
                cur_id, cur_text, cur_met = idx, sent, False
            if label == "1":
                cur_met = True
    _flush()
    return samples
