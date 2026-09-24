# -*- coding: utf-8 -*-
"""MetaNet 概念隐喻 → 中文 cascade 本体迁移脚本（方案 §5 冷启动种子扩充）。

把英文概念隐喻（Lakoff & Johnson 1980 / Kövecses / MetaNet 代表性清单）的
结构 source_domain → target_domain 自动对齐翻译为**中文 cascade 种子**，灌入
CascadeOntology，从而把方案里仅 7 个级联的种子扩到覆盖更多常见概念隐喻。

数据源（两种）：
  1. BUILTIN_CONCEPTUAL_METAPHORS —— 内置经典清单，已人工对齐中文，开箱即用。
  2. MetaNetImporter.from_dump(path) —— 解析外部 MetaNet/Framester 导出的
     JSON（结构见 from_dump 注释），用于接入真实 MetaNet 数据。

产物：
  - 内存：build_metanet_ontology(base) 返回扩充后的 CascadeOntology；
          同时把新增映射类型写入全局 TYPE_CONSTRAINTS，使类型安全约束
          （§4.1.3，P1 硬门槛）对新框架同样生效。
  - 落地：ontology_metanet_seeds.json（frames / cascades / 扩展类型约束），
          可被 evaluate_real.py 直接加载复用。

运行：python -m metaphor_graph.metanet_migrate
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .ontology import CascadeOntology, FrameSpec, CascadeSpec, DEFAULT_ONTOLOGY

# ----------------------------------------------------------------------------
# 经典英文概念隐喻（已对齐中文 source/target 域 + 中文触发词示例）
#   mapping_type   : 语义化映射名（同时注册进 TYPE_CONSTRAINTS）
#   source_type    : 必须是 TYPE_CONSTRAINTS 的键（或此处新扩展的键）
# ----------------------------------------------------------------------------
BUILTIN_CONCEPTUAL_METAPHORS = [
    dict(id="F_LIFE_JOURNEY", en="LIFE IS A JOURNEY",
         mapping_type="LIFE_IS_JOURNEY", source_type="MOTION",
         source_domain="旅程", target_domain="生活",
         ground=["起点", "方向", "障碍", "同行者", "终点"],
         triggers=["人生旅程", "迈步", "走到", "同行", "拐弯", "停滞不前", "走到尽头"]),
    dict(id="F_LOVE_JOURNEY", en="LOVE IS A JOURNEY",
         mapping_type="LOVE_IS_JOURNEY", source_type="MOTION",
         source_domain="旅程", target_domain="爱情",
         ground=["同行", "波折", "终点", "迷路"],
         triggers=["携手", "同行", "走下去", "婚姻旅程", "走到尽头"]),
    dict(id="F_IDEAS_FOOD", en="IDEAS ARE FOOD",
         mapping_type="IDEAS_ARE_FOOD", source_type="PHYSICAL_OBJECT",
         source_domain="食物", target_domain="想法",
         ground=["生熟", "消化", "营养", "口味"],
         triggers=["半生不熟", "消化", "细品", "精髓", "食粮", "大餐"]),
    dict(id="F_THEORY_BUILDING", en="THEORIES ARE BUILDINGS",
         mapping_type="THEORIES_ARE_BUILDINGS", source_type="PHYSICAL_OBJECT",
         source_domain="建筑", target_domain="理论",
         ground=["地基", "框架", "结构", "倒塌"],
         triggers=["基础", "框架", "构建", "支柱", "坍塌", "大厦", "建筑"]),
    dict(id="F_KNOWING_SEEING", en="KNOWING IS SEEING",
         mapping_type="KNOWING_IS_SEEING", source_type="BODY_SENSATION",
         source_domain="视觉", target_domain="理解",
         ground=["清晰", "视角", "盲区", "照亮"],
         triggers=["看清", "视角", "洞察", "阐明", "盲区", "照亮"]),
    dict(id="F_PURPOSE_DEST", en="PURPOSES ARE DESTINATIONS",
         mapping_type="PURPOSES_ARE_DESTINATIONS", source_type="MOTION",
         source_domain="目的地", target_domain="目标",
         ground=["到达", "路线", "偏离"],
         triggers=["达成", "抵达", "方向", "偏离", "路线图"]),
    dict(id="F_ORG_PLANT", en="SOCIAL ORGANIZATIONS ARE PLANTS",
         mapping_type="ORG_ARE_PLANTS", source_type="NATURAL_PHENOMENON",
         source_domain="植物", target_domain="组织",
         ground=["根", "枝", "枯萎", "繁茂"],
         triggers=["扎根", "分支", "枯萎", "壮大", "枝繁叶茂", "根基"]),
    dict(id="F_COMM_SENDING", en="COMMUNICATION IS SENDING",
         mapping_type="COMM_IS_SENDING", source_type="PHYSICAL_OBJECT",
         source_domain="物体传递", target_domain="交流",
         ground=["传递", "接收", "丢失", "包装"],
         triggers=["传达", "接收", "灌输", "传递", "转达"]),
    dict(id="F_IMPORTANT_BIG", en="IMPORTANT IS BIG",
         mapping_type="IMPORTANT_IS_BIG", source_type="PHYSICAL_OBJECT",
         source_domain="体量", target_domain="重要性",
         ground=["大", "重", "中心"],
         triggers=["重大", "核心", "举足轻重", "分量"]),
    dict(id="F_VALENCE_VERTICAL", en="HAPPY IS UP / SAD IS DOWN",
         mapping_type="VALENCE_IS_VERTICAL", source_type="MOTION",
         source_domain="上下", target_domain="情绪效价",
         ground=["高", "低", "跌落"],
         triggers=["高涨", "低落", "跌入谷底", "情绪高涨"]),
    dict(id="F_MORAL_PURITY", en="MORALITY IS PURITY",
         mapping_type="MORALITY_IS_PURITY", source_type="MORAL",
         source_domain="洁净", target_domain="道德",
         ground=["纯净", "污点", "洗清"],
         triggers=["纯洁", "污点", "洗白", "清白"]),
]


def _seeds_from_list(items: List[dict]):
    """把概念隐喻清单转成 (frames, cascades, type_ext) 三个字典。"""
    frames: Dict[str, FrameSpec] = {}
    cascades: Dict[str, CascadeSpec] = {}
    type_ext: Dict[str, List[str]] = {}
    for it in items:
        fid = it["id"]
        cid = "C_" + fid[2:] if fid.startswith("F_") else "C_" + fid
        frames[fid] = FrameSpec(
            id=fid,
            name=it["en"],
            mapping_type=it["mapping_type"],
            source_domain=it["source_domain"],
            target_domain=it["target_domain"],
            ground=list(it["ground"]),
            triggers=list(it["triggers"]),
            source_type=it["source_type"],
        )
        cascades[cid] = CascadeSpec(
            id=cid,
            name=it["en"],
            member_frames=[fid],
            discourse_domains=[f"{it['source_domain']}→{it['target_domain']}"],
            typical_triggers=list(it["triggers"])[:3],
        )
        type_ext.setdefault(it["source_type"], [])
        if it["mapping_type"] not in type_ext[it["source_type"]]:
            type_ext[it["source_type"]].append(it["mapping_type"])
    return frames, cascades, type_ext


def build_metanet_ontology(base: CascadeOntology = DEFAULT_ONTOLOGY,
                           items: List[dict] = None,
                           dump_path: Optional[str] = None) -> CascadeOntology:
    """把概念隐喻种子合并进基础本体，返回扩充后的 CascadeOntology。

    副作用：把新增映射类型写进全局 TYPE_CONSTRAINTS（通过导入 ontology 模块
    直接修改其字典），使 CascadeOntology.type_valid 对新框架同样生效。
    """
    items = items if items is not None else BUILTIN_CONCEPTUAL_METAPHORS
    f1, c1, type_ext = _seeds_from_list(items)

    merged_frames = dict(base.frames)
    merged_frames.update(f1)
    merged_cascades = dict(base.cascades)
    merged_cascades.update(c1)

    # 扩展全局类型安全约束（P1 硬门槛依赖它）
    import metaphor_graph.ontology as _ont
    for k, vals in type_ext.items():
        _ont.TYPE_CONSTRAINTS.setdefault(k, [])
        for m in vals:
            if m not in _ont.TYPE_CONSTRAINTS[k]:
                _ont.TYPE_CONSTRAINTS[k].append(m)

    onto = CascadeOntology(merged_frames, merged_cascades)
    if dump_path:
        _dump_seeds(onto, type_ext, dump_path)
    return onto


def _dump_seeds(onto: CascadeOntology, type_ext: Dict[str, List[str]], path: str):
    payload = {
        "frames": {k: {
            "id": f.id, "name": f.name, "mapping_type": f.mapping_type,
            "source_domain": f.source_domain, "target_domain": f.target_domain,
            "ground": f.ground, "triggers": f.triggers,
            "source_type": f.source_type,
        } for k, f in onto.frames.items()},
        "cascades": {k: {
            "id": c.id, "name": c.name, "member_frames": c.member_frames,
            "discourse_domains": c.discourse_domains,
            "typical_triggers": c.typical_triggers,
        } for k, c in onto.cascades.items()},
        "type_constraints_ext": type_ext,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


class MetaNetImporter:
    """解析外部 MetaNet / Framester 导出的概念隐喻 JSON。

    期望每条记录至少含 source / target（英文），可选中文对齐字段：
        {"source": "JOURNEY", "target": "LIFE",
         "source_cn": "旅程", "target_cn": "生活",
         "en": "LIFE IS A JOURNEY",
         "examples": ["人生旅程", "走到尽头"],   # 作为中文触发词
         "source_type": "MOTION"}
    若缺中文对齐，则用英文原文占位（需后续人工对齐才能真正用于中文抽取）。
    """

    @staticmethod
    def from_dump(path: str, prefix: str = "F_MN") -> List[dict]:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        items: List[dict] = []
        for i, d in enumerate(data):
            src = d.get("source_cn") or d.get("source_domain") or d.get("source", "")
            tgt = d.get("target_cn") or d.get("target_domain") or d.get("target", "")
            en = d.get("en") or d.get("name") or f"{d.get('source','?')} IS A {d.get('target','?')}"
            items.append(dict(
                id=d.get("id", f"{prefix}_{i}"),
                en=en,
                mapping_type=d.get("mapping_type",
                                   en.replace(" ", "_").replace("IS_A", "IS").upper()),
                source_type=d.get("source_type", "PHYSICAL_OBJECT"),
                source_domain=src,
                target_domain=tgt,
                ground=d.get("ground", []),
                triggers=d.get("triggers") or d.get("examples", []),
            ))
        return items


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    dump = os.path.join(here, "ontology_metanet_seeds.json")
    onto = build_metanet_ontology(dump_path=dump)
    # 读取扩展后的类型约束键
    import metaphor_graph.ontology as _ont
    print("合并前:", DEFAULT_ONTOLOGY.stats())
    print("合并后:", onto.stats())
    print("类型安全约束键（含扩展）:", list(_ont.TYPE_CONSTRAINTS.keys()))
    print(f"已写入种子文件: {dump}")
