"""MIPVU-lite 候选通道（方案 §6.5，轻量接入）。

把 MIPVU 的「基本义 ≠ 语境义」判定 + Wmatrix 的「语义域失谐」做成一条
不依赖触发词表的候选通道：

  1. 对 chunk 分词，给每个内容词打 USAS 风格语义域（semfield.tag_token）。
  2. 语境预期域 = chunk 主导语义域（discourse_field）。
  3. 候选判据（满足其一即候选）：
     a. 等比标记邻近：喻体词前后相邻 token 是 是/像/如/似/若 或其复合词
        （就是/如同/成为/变成/当作/仿佛/犹如/宛如/好比/一样/一般/似的/成了/化作）。
        —— 基于**分词 token** 匹配，避免「如」误中「栩栩如生」、「像」误中「好像」。
     b. 语义失谐：词域 ≠ 语境预期域 且 该域词在 chunk 中稀有（count<=1）
        → Wmatrix 式 keyness（跨域转移）。
  4. 域内字面护栏：同域词出现 ≥2 且该域即语篇主导域 → 喻体落在源域内，非跨域，跳过。
  5. 域 → 级联/框架 桥接（semfield.FIELD_TO_FRAME），产出候选供抽取器过类型护栏。

为何能突破「触发词天花板」：通道不看触发词表，喻体词只要落在某语义域
（如 舞台→THEATRE）即被召回，一个域覆盖几十个喻体，且不要求词在 triggers 里。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import semfield

# 等比标记（MIPVU 显式信号）。单字必须作为独立分词 token 出现才算，
# 复合词直接匹配整词。刻意排除「为/做」（"为一只老虎"=硬币图案，字面）、
# 以及「好像/如果/如何」之类（非等比隐喻）。
MARKERS = {
    "是", "像", "如", "似", "若",
    "就是", "也是", "正是", "便是", "或是", "像是", "像被", "如同", "犹如", "宛如",
    "就像", "就如", "宛若", "有如", "恰似", "形似",
    "好比", "成为", "变成", "当作", "仿佛", "一样", "一般", "似的", "成了", "化作",
}
# token 窗口：检查喻体词前/后若干 token 是否含等比标记。
# 「X是一个Y」中标记「是/就是」常隔「一个」等量词，故取 ±2。
_TOKEN_WIN = 2


def _segment_with_pos(text: str):
    """返回 [(token, start, end), ...]。"""
    toks = semfield.segment(text)
    out = []
    i = 0
    for t in toks:
        j = text.find(t, i)
        if j < 0:
            j = i
        out.append((t, j, j + len(t)))
        i = j + len(t)
    return out


def _marker_near_token(tok_pos: List, idx: int) -> bool:
    for k in range(idx - _TOKEN_WIN, idx + _TOKEN_WIN + 1):
        if 0 <= k < len(tok_pos):
            if tok_pos[k][0] in MARKERS:
                return True
    return False


def mipvu_candidates(chunk: str,
                     ontology=None) -> List[Dict]:
    """返回 MIPVU 候选列表。

    每项: {"frame_id", "cascade_id", "start", "end", "vehicle", "conf"}
    ontology 仅用于确认桥接目标存在（缺失则跳过）。
    """
    from .ontology import CascadeOntology
    ont = ontology or CascadeOntology()

    tok_pos = _segment_with_pos(chunk)
    # 统计各域在 chunk 中的出现次数（用于「稀有」「域内字面」判据）
    field_counts: Dict[str, int] = {}
    for w, _, _ in tok_pos:
        f = semfield.tag_token(w)
        if f:
            field_counts[f] = field_counts.get(f, 0) + 1

    out: List[Dict] = []
    seen = set()
    for idx, (w, s, e) in enumerate(tok_pos):
        f = semfield.tag_token(w)
        if not f:
            continue
        frame_id = semfield.FIELD_TO_FRAME.get(f)
        cascade_id = semfield.FIELD_TO_CASCADE.get(f)
        if not frame_id or not cascade_id:
            continue
        # 桥接目标必须存在，且该框架必须**有 L3 归属**（否则语义域通道等于绕过层级）。
        # 原实现只认 semfield 里写死的 6 个级联 id —— 那会让任何替换级联构造规则
        # （cascade_rules 模块）的实验**静默关掉整条 MIPVU 通道**（实测丢 7 条 L1 边，
        # 见 experiments/gen2/REPORT.md §4）。改为「框架存在 + 框架有级联归属」后：
        #   - 默认 json 规则下逐位不变（6 个 id 都存在，get_cascade 也都有值）；
        #   - none 规则（L3 消融）下通道正确地关闭。
        if ont.get_frame(frame_id) is None:
            continue
        if ont.cascades.get(cascade_id) is None and \
                ont.get_cascade(frame_id) is None:
            continue

        # 域内字面护栏（Wmatrix keyness）：chunk 明显围绕该语义域 → 跳过
        dom = semfield.discourse_field(chunk)
        if field_counts.get(f, 0) >= 2 and f == dom:
            continue

        # 判据 a：等比标记邻近（独立 token）
        if _marker_near_token(tok_pos, idx):
            conf = 0.5
        else:
            # 判据 b：语义失谐 + 稀有
            inc = semfield.incongruity_score(w, chunk)
            if inc < 0.6 or field_counts.get(f, 0) > 1:
                continue
            conf = 0.45 if inc >= 0.6 else 0.4

        key = (frame_id, s)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "frame_id": frame_id,
            "cascade_id": cascade_id,
            "start": s,
            "end": e,
            "vehicle": w,
            "conf": conf,
        })
    return out
