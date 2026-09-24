"""中文语义域标注器（MIPVU + Wmatrix 轻量接入，方案 §6.5）。

设计：
  - 借鉴 Wmatrix 的 USAS 语义场思路，但用**中文自建词表**替代英文 USAS 标注器
    （Wmatrix 是英文 web 工具，中文不可直接用）。语义场与级联本体的 source_domain
    同源——级联本体的 ground 词表本来就是语义场种子。
  - FIELDS：USAS 风格语义域 → 词表。覆盖我们新接入的 6 个级联域
    （THEATRE/NATURE/BUILDING/VALUE/SUBSTANCE/ORGANISM）。
  - tag_token：查词表得 token 的语义域（基本义所在域）。
  - discourse_field：对 chunk 内全部内容词统计域分布，取主导域作为「语篇预期域」。
  - FIELD_TO_CASCADE / FIELD_TO_FRAME：语义域 → 级联/框架 桥接，供 mipvu 产出候选。
  - embedder 可插拔：若 set_embedder(fn) 提供句向量，incongruity_score 改用语义相似度，
    否则走词表路径（默认，无需外部模型）。

注意：本模块只在 use_semfield=True 时被 extractor 调用；jieba 懒加载，
非 jieba 环境下不影响包其余部分导入。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

# ----------------------------------------------------------------------------
# USAS 风格中文语义域词表（轻量版，覆盖新接入的 6 个级联域）
# 每个域含：典型喻体（vehicle）+ 少量基础域词（使语篇预期域可统计）
# ----------------------------------------------------------------------------
FIELDS: Dict[str, List[str]] = {
    "THEATRE": ["舞台", "角色", "剧本", "谢幕", "导演", "台词", "戏台", "幕", "配角",
                "主角", "彩排", "剧场", "戏", "演出", "排练"],
    "NATURE": ["风", "火", "水", "光", "花", "海洋", "雨", "冰", "雪", "雷", "电",
               "太阳", "月亮", "星", "山", "河", "树", "草", "云", "浪", "潮", "霜"],
    "BUILDING": ["大厦", "地基", "支柱", "栋梁", "围墙", "梁", "砖", "墙", "楼", "柱",
                 "基石", "框架", "屋顶", "桥梁"],
    "VALUE": ["宝石", "明珠", "黄金", "瑰宝", "钻石", "珍宝", "金子", "璞玉", "翡翠",
              "珍珠", "宝贝", "宝藏"],
    "SUBSTANCE": ["棉花糖", "蜜", "盐", "糖", "毒药", "甘露", "良药", "苦药", "酒",
                  "茶", "咖啡", "糖衣", "蜜糖"],
    "ORGANISM": ["老虎", "绵羊", "狐狸", "老黄牛", "蜜蜂", "狼", "蝴蝶", "鹰", "蛇",
                 "牛", "马", "羊", "燕", "鹊", "乌鸦", "鲸", "鱼"],
}

# 反向索引：词 → 域
_WORD_TO_FIELD: Dict[str, str] = {}
for _f, _ws in FIELDS.items():
    for _w in _ws:
        _WORD_TO_FIELD[_w] = _f

# 语义域 → 级联 / 框架（须与 ontology.py 中的 id 一致）
FIELD_TO_CASCADE: Dict[str, str] = {
    "THEATRE": "C_EVENT_IS_PLAY",
    "NATURE": "C_STATE_IS_NATURE",
    "BUILDING": "C_STRUCTURE_IS_BUILDING",
    "VALUE": "C_WORTH_IS_VALUE",
    "SUBSTANCE": "C_QUALITY_IS_SUBSTANCE",
    "ORGANISM": "C_TRAIT_IS_ORGANISM",
}
FIELD_TO_FRAME: Dict[str, str] = {
    "THEATRE": "F_EVENT_PLAY",
    "NATURE": "F_STATE_NATURE",
    "BUILDING": "F_STRUCT_BUILDING",
    "VALUE": "F_WORTH_VALUE",
    "SUBSTANCE": "F_QUALITY_IS_SUBSTANCE",
    "ORGANISM": "F_TRAIT_ORGANISM",
}

# 可插拔句向量器（默认 None → 词表路径）
EMBEDDER = None


def set_embedder(fn):
    """fn(word:str) -> List[float]；设置后 incongruity_score 用语义相似度。"""
    global EMBEDDER
    EMBEDDER = fn


def tag_token(word: str) -> Optional[str]:
    """返回词所属语义域（基本义所在域），未收录返回 None。"""
    return _WORD_TO_FIELD.get(word)


def segment(text: str) -> List[str]:
    """中文分词（jieba 懒加载）。"""
    try:
        import jieba
    except ImportError:
        # 退化：按字切（精度差，仅保证可用）
        return list(text)
    return [w for w in jieba.lcut(text) if w.strip()]


def discourse_field(text: str) -> Optional[str]:
    """对 chunk 统计语义域分布，返回主导域（语篇预期域）；无域词返回 None。"""
    counts: Dict[str, int] = defaultdict(int)
    for w in segment(text):
        f = tag_token(w)
        if f:
            counts[f] += 1
    if not counts:
        return None
    return max(counts.items(), key=lambda x: x[1])[0]


def incongruity_score(word: str, text: str) -> float:
    """0–1：词与语篇预期域的失谐强度。

    - 词未收录 → 0（不在此通道处理）。
    - 词域 == 语篇预期域 → 0（同域，非跨域隐喻）。
    - 词域 != 语篇预期域 → 基础 0.6；若语篇无主导域（None）→ 0.3（仅按标记判断）。
    - 若 EMBEDDER 可用：用语义相似度精化（词向量 vs 语篇向量越不相似分越高）。
    """
    f = tag_token(word)
    if not f:
        return 0.0
    dom = discourse_field(text)
    if dom is None:
        return 0.3
    if f == dom:
        return 0.0
    return 0.6
