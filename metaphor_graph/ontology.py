"""中文隐喻级联（cascade）本体 —— 方案 §5 的「冷启动种子」。

这是 P0 资源建设的最小可用版本：从 MetaNet 英文级联结构与中文隐喻类型
（WordNet/SUMO 1256 汉语隐喻类型、COGMED 感官隐喻）对齐而来。

设计要点：
  1. 层级同构：Cascade(级联) → Frame(框架) → Mapping(映射/超边) 严格对应
     L3 → L2 → L1。
  2. 类型安全约束 TYPE_CONSTRAINTS 是「结构化过滤器」，不依赖 LLM 判断
     字面误判（方案 §4.1.3，对应 H1 硬门槛）。
  3. 本体的查表归属替代 embedding 聚类，是核心降本来源（对应 H2）。

注意：这是 *种子* 本体，目标是后续自举回流到 ≥1000 框架（§9.1）。
此处内置 7 个级联 / 20+ 框架作为可运行的最小示例。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# 源域 → source_type 推断规则
# ----------------------------------------------------------------------------
# 为什么需要：LLM 自举出的框架此前 **98.6% 被标成 GENERIC_VEHICLE**，
# 而 GENERIC_VEHICLE → GENERIC_VEHICLE_MAP 在 TYPE_CONSTRAINTS 里无条件合法，
# 导致类型安全约束运行时**从不拒绝任何候选**（实测拦下 0 个，见 README §7.1 A1）。
# 给框架推断出真实 source_type 后，约束才有信息可用 —— 尤其是用来拦截
# 模糊匹配把候选绑到类型不相干框架上的情况（见 extractor._frame_for_candidate）。
_SOURCE_TYPE_RULES: Dict[str, Tuple[str, ...]] = {
    "BODY_SENSATION": ("人体", "身体", "手", "足", "脚", "头", "眼", "心", "血",
                       "温度", "痛", "触觉", "感官", "疾病", "医疗", "生理",
                       "器官", "面孔", "脸色", "身姿"),
    "ORGANISM": ("动物", "兽", "昆虫", "鸟", "鱼", "生物", "畜", "虫", "禽",
                 "蜜蜂", "蚂蚁", "狐狸", "狼", "虎", "蛇", "马", "牛", "羊",
                 "狗", "猫", "鹰", "雀", "野兽"),
    "NATURE": ("植物", "花", "草", "树", "森林", "农业", "园艺", "种植", "庄稼",
               "生命", "生长", "苗", "叶", "根", "种子", "作物", "幼苗"),
    "NATURAL_PHENOMENON": ("水流", "水", "液体", "海洋", "江河", "河", "海", "湖",
                           "浪", "潮", "火", "火焰", "光", "天气", "风", "雨",
                           "雪", "冰", "霜", "雷", "电", "天体", "星", "云",
                           "雾", "自然", "物理", "气候", "洪", "泉", "流"),
    "MOTION": ("道路", "路", "旅程", "旅行", "行走", "奔跑", "飞行", "交通",
               "车", "船", "航海", "航行", "运动", "移动", "步", "轨道",
               "行程", "旅途", "方向", "速度"),
    "WAR": ("战争", "军事", "武器", "刀", "剑", "枪", "炮", "战场", "战斗",
            "军队", "士兵", "攻击", "防御", "战略"),
    "BUILDING": ("建筑", "房屋", "房", "楼", "塔", "桥", "墙", "门", "柱",
                 "梁", "地基", "结构", "工程", "殿", "城堡"),
    "MACHINE": ("机器", "机械", "装置", "齿轮", "发动机", "仪表", "设备",
                "仪器", "零件"),
    "CONTAINER": ("容器", "箱", "盒", "瓶", "罐", "杯", "袋", "篮", "仓",
                  "库", "桶", "囊"),
    "PERFORMANCE": ("舞台", "戏剧", "表演", "音乐", "舞蹈", "游戏", "电影",
                    "剧场", "戏", "曲", "演奏", "角色", "幕", "剧本"),
    "FINANCIAL": ("金钱", "金融", "经济", "货币", "财富", "交易", "买卖",
                  "资本", "市场", "价格"),
    "PHYSICAL_OBJECT": ("物体", "物品", "器物", "器具", "金属", "珍宝", "珠宝",
                        "镜子", "工具", "绳", "锁", "链", "网", "布", "纸",
                        "石", "铁", "木", "玻璃", "线", "针", "球", "框",
                        "笼", "重物", "担子", "包袱", "货物", "家具", "器皿",
                        "瓷", "尺", "秤", "刀"),
    "SUBSTANCE": ("物质", "材料", "原料", "化学", "成分", "泥", "土", "沙",
                  "灰", "尘"),
    "VALUE": ("价值", "价格", "贵重", "衡量", "尺度"),
    "MORAL": ("道德", "纯洁", "善恶", "伦理", "洁净", "污"),
}


def infer_source_type(domain: str) -> str:
    """从源域描述推断 source_type，让类型安全约束获得可用信息。

    匹配不到就退回 GENERIC_VEHICLE —— 不做无根据的猜测，宁可放弃约束信息。
    """
    if not domain:
        return "GENERIC_VEHICLE"
    for stype, kws in _SOURCE_TYPE_RULES.items():
        if any(kw in domain for kw in kws):
            return stype
    return "GENERIC_VEHICLE"


# ----------------------------------------------------------------------------
# 类型安全约束（方案 §4.1.3）
#   source_type(源域类型) → 允许出现的映射类型集合
#   类型不匹配 → 大概率字面误判，直接丢弃。
# ----------------------------------------------------------------------------
TYPE_CONSTRAINTS: Dict[str, List[str]] = {
    "PHYSICAL_OBJECT": ["OBJECT_IS_CONTAINER", "OBJECT_IS_INSTRUMENT"],
    "BODY_SENSATION": ["ANGER_IS_HEAT", "AFFECTION_IS_WARMTH"],
    "MOTION": ["CHANGE_IS_MOTION", "PROGRESS_IS_JOURNEY"],
    "FINANCIAL": ["TIME_IS_MONEY", "EFFORT_IS_CURRENCY"],
    "NATURAL_PHENOMENON": ["DIFFICULTY_IS_TERRAIN", "OBSTACLE_IS_TERRAIN"],
    "MACHINE": ["LIFE_IS_A_MACHINE", "BODY_IS_A_MACHINE"],
    "WAR": ["ARGUMENT_IS_WAR", "COMPETITION_IS_WAR"],
    "CONTAINER": ["MIND_IS_CONTAINER", "EMOTION_IS_CONTAINER"],
    # 自举回流（方案 §9.1）：从语料高频挖掘、尚未绑定到具体概念隐喻的喻体词，
    # 统一归入 GENERIC 通道，使 type_valid 通过但不污染已有概念映射。
    "GENERIC_VEHICLE": ["GENERIC_VEHICLE_MAP"],
    # --- MIPVU/Wmatrix 轻量接入（§6.5）：语义域（USAS 风格）桥接通道 ---
    # 每个语义域对应一个 source_type，使语义失谐检测产出的候选能过类型安全约束。
    "PERFORMANCE": ["EVENT_IS_PERFORMANCE"],
    "NATURE": ["STATE_IS_NATURE"],
    "BUILDING": ["STRUCTURE_IS_BUILDING"],
    "VALUE": ["WORTH_IS_VALUE"],
    "SUBSTANCE": ["QUALITY_IS_SUBSTANCE"],
    "ORGANISM": ["TRAIT_IS_ORGANISM"],
}


@dataclass
class FrameSpec:
    """一个 L2 框架（一般隐喻）的本体条目。"""
    id: str
    name: str
    mapping_type: str               # 映射到 TYPE_CONSTRAINTS 的键
    source_domain: str
    target_domain: str
    ground: List[str]               # 典型喻底
    triggers: List[str]             # 中文触发词（用于启发式抽取）
    source_type: str                # 源域类型（用于类型安全约束）
    source_frame: str = ""
    target_frame: str = ""
    # 自举框架的清洗元数据（ontology_clean.py 写入；内置/MetaNet 框架留默认）
    support: int = 0                # 支持该框架的高置信候选数（缓存重算）
    tier: str = ""                  # core（count≥2 二次出现）/ longtail（单例锚点）


@dataclass
class CascadeSpec:
    """一个 L3 级联的本体条目。"""
    id: str
    name: str
    member_frames: List[str]        # FrameSpec.id 列表
    discourse_domains: List[str] = field(default_factory=list)
    typical_triggers: List[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# 种子级联 / 框架定义（中文）
# ----------------------------------------------------------------------------

_FRAMES: Dict[str, FrameSpec] = {}
_CASCADES: Dict[str, CascadeSpec] = {}


def _add_frame(f: FrameSpec):
    _FRAMES[f.id] = f


def _add_cascade(c: CascadeSpec):
    _CASCADES[c.id] = c


# --- 级联 1：ARGUMENT_IS_WAR（争论是战争）---
_add_frame(FrameSpec("F_ARG_WAR", "ARGUMENT_IS_WAR", "ARGUMENT_IS_WAR",
    source_domain="战争", target_domain="争论",
    ground=["对抗", "胜负", "进攻", "防守", "战略"],
    triggers=["开火", "攻击", "防守", "攻势", "战壕", "击败", "阵地", "交锋"],
    source_type="WAR", source_frame="Combat", target_frame="Communication"))
_add_frame(FrameSpec("F_COMP_WAR", "COMPETITION_IS_WAR", "COMPETITION_IS_WAR",
    source_domain="战争", target_domain="商业竞争",
    ground=["对手", "阵地", "突围", "卡位"],
    triggers=["商战", "抢滩", "攻城略地", "护城河", "突围"],
    source_type="WAR", source_frame="Combat", target_frame="Business"))

# --- 级联 2：TIME_IS_MONEY（时间是金钱）---
_add_frame(FrameSpec("F_TIME_MONEY", "TIME_IS_MONEY", "TIME_IS_MONEY",
    source_domain="金钱", target_domain="时间",
    ground=["稀缺", "可花费", "可浪费", "有预算", "可投资"],
    triggers=["花时间", "浪费时间", "时间预算", "投入时间", "省时间"],
    source_type="FINANCIAL", source_frame="Resource", target_frame="Time"))
_add_frame(FrameSpec("F_EFFORT_CUR", "EFFORT_IS_CURRENCY", "EFFORT_IS_CURRENCY",
    source_domain="货币", target_domain="努力",
    ground=["成本", "回报", "投资", "折旧"],
    triggers=["投入精力", "付出代价", "血本", "回报"],
    source_type="FINANCIAL", source_frame="Resource", target_frame="Effort"))

# --- 级联 3：PROGRESS_IS_JOURNEY（进展是旅程）---
_add_frame(FrameSpec("F_PROG_JOURNEY", "PROGRESS_IS_JOURNEY", "PROGRESS_IS_JOURNEY",
    source_domain="旅程", target_domain="项目进展",
    ground=["起点", "方向", "障碍", "里程碑", "停滞"],
    triggers=["推进", "前进", "停滞", "迈步", "抵达", "路途"],
    source_type="MOTION", source_frame="Path", target_frame="Project"))
_add_frame(FrameSpec("F_CHANGE_MOTION", "CHANGE_IS_MOTION", "CHANGE_IS_MOTION",
    source_domain="运动", target_domain="变化",
    ground=["转向", "加速", "倒车", "惯性"],
    triggers=["转向", "提速", "急刹", "倒车"],
    source_type="MOTION", source_frame="Motion", target_frame="Change"))

# --- 级联 4：LIFE_IS_A_MACHINE（生活是一部机器）---
_add_frame(FrameSpec("F_LIFE_MACHINE", "LIFE_IS_A_MACHINE", "LIFE_IS_A_MACHINE",
    source_domain="机器", target_domain="生活状态",
    ground=["紧绷", "需要放松", "机械重复", "缺乏弹性"],
    triggers=["发条", "拧紧", "齿轮", "上弦", "机械"],
    source_type="MACHINE", source_frame="Machine", target_frame="Life"))
_add_frame(FrameSpec("F_BODY_MACHINE", "BODY_IS_A_MACHINE", "BODY_IS_A_MACHINE",
    source_domain="机器", target_domain="身体",
    ground=["运转", "零件", "磨损", "检修"],
    triggers=["零件", "磨损", "检修", "运转"],
    source_type="MACHINE", source_frame="Machine", target_frame="Body"))

# --- 级联 5：DIFFICULTY_IS_TERRAIN（困难是地形）---
_add_frame(FrameSpec("F_OBST_TERRAIN", "OBSTACLE_IS_TERRAIN", "OBSTACLE_IS_TERRAIN",
    source_domain="地形", target_domain="项目困境",
    ground=["泥潭", "深坑", "陡坡", "沼泽"],
    triggers=["泥潭", "陷进", "沼泽", "深坑", "泥沼"],
    source_type="NATURAL_PHENOMENON", source_frame="Terrain", target_frame="Difficulty"))
_add_frame(FrameSpec("F_DIFF_TERRAIN", "DIFFICULTY_IS_TERRAIN", "DIFFICULTY_IS_TERRAIN",
    source_domain="地形", target_domain="困难",
    ground=["攀登", "悬崖", "陡坡"],
    triggers=["攀登", "悬崖", "陡坡"],
    source_type="NATURAL_PHENOMENON", source_frame="Terrain", target_frame="Difficulty"))

# --- 级联 6：ANGER_IS_HEAT（愤怒是热）---
_add_frame(FrameSpec("F_ANGER_HEAT", "ANGER_IS_HEAT", "ANGER_IS_HEAT",
    source_domain="热", target_domain="愤怒",
    ground=["升温", "爆发", "灼烧", "沸腾"],
    triggers=["火大", "怒火", "爆发", "升温", " boiling".replace(" boiling", "沸腾")],
    source_type="BODY_SENSATION", source_frame="Heat", target_frame="Emotion"))
_add_frame(FrameSpec("F_AFF_WARM", "AFFECTION_IS_WARMTH", "AFFECTION_IS_WARMTH",
    source_domain="温暖", target_domain="喜爱",
    ground=["亲近", "舒适", "融化"],
    triggers=["暖心", "温暖", "融化", "贴心"],
    source_type="BODY_SENSATION", source_frame="Warmth", target_frame="Emotion"))

# --- 级联 7：MIND_IS_CONTAINER（心智是容器）---
_add_frame(FrameSpec("F_MIND_CONT", "MIND_IS_CONTAINER", "MIND_IS_CONTAINER",
    source_domain="容器", target_domain="心智",
    ground=["装满", "溢出", "封闭", "空洞"],
    triggers=["装满", "溢出", "塞满", "脑容量"],
    source_type="CONTAINER", source_frame="Container", target_frame="Mind"))
_add_frame(FrameSpec("F_EMO_CONT", "EMOTION_IS_CONTAINER", "EMOTION_IS_CONTAINER",
    source_domain="容器", target_domain="情绪",
    ground=["积压", "释放", "压抑", "满溢"],
    triggers=["积压", "释放", "压抑", "满溢", "装不下"],
    source_type="CONTAINER", source_frame="Container", target_frame="Emotion"))


# --- 级联 8：EVENT_IS_PERFORMANCE（事件是演出，语义域 THEATRE）---
_add_frame(FrameSpec("F_EVENT_PLAY", "EVENT_IS_PERFORMANCE", "EVENT_IS_PERFORMANCE",
    source_domain="戏剧", target_domain="人生/社会事件",
    ground=["舞台", "角色", "剧本", "谢幕", "导演", "台词", "戏台"],
    triggers=[], source_type="PERFORMANCE", source_frame="Theater", target_frame="Event"))
# --- 级联 9：STATE_IS_NATURE（境遇是自然物，语义域 NATURE）---
_add_frame(FrameSpec("F_STATE_NATURE", "STATE_IS_NATURE", "STATE_IS_NATURE",
    source_domain="自然", target_domain="状态/境遇",
    ground=["风", "火", "水", "光", "花", "海洋", "雨", "冰"],
    triggers=[], source_type="NATURE", source_frame="Nature", target_frame="State"))
# --- 级联 10：STRUCTURE_IS_BUILDING（体系是建筑，语义域 BUILDING）---
_add_frame(FrameSpec("F_STRUCT_BUILDING", "STRUCTURE_IS_BUILDING", "STRUCTURE_IS_BUILDING",
    source_domain="建筑", target_domain="体系/组织",
    ground=["大厦", "地基", "支柱", "栋梁", "围墙", "梁"],
    triggers=[], source_type="BUILDING", source_frame="Building", target_frame="System"))
# --- 级联 11：WORTH_IS_VALUE（价值是珍宝，语义域 VALUE）---
_add_frame(FrameSpec("F_WORTH_VALUE", "WORTH_IS_VALUE", "WORTH_IS_VALUE",
    source_domain="珍宝", target_domain="价值",
    ground=["宝石", "明珠", "黄金", "瑰宝", "钻石"],
    triggers=[], source_type="VALUE", source_frame="Treasure", target_frame="Worth"))
# --- 级联 12：QUALITY_IS_SUBSTANCE（品质是物质，语义域 SUBSTANCE）---
_add_frame(FrameSpec("F_QUALITY_SUBSTANCE", "QUALITY_IS_SUBSTANCE", "QUALITY_IS_SUBSTANCE",
    source_domain="物质", target_domain="品质/感受",
    ground=["棉花糖", "蜜", "盐", "糖", "毒药", "甘露"],
    triggers=[], source_type="SUBSTANCE", source_frame="Substance", target_frame="Quality"))
# --- 级联 13：TRAIT_IS_ORGANISM（人的特质是生物，语义域 ORGANISM）---
_add_frame(FrameSpec("F_TRAIT_ORGANISM", "TRAIT_IS_ORGANISM", "TRAIT_IS_ORGANISM",
    source_domain="生物", target_domain="人的特质",
    ground=["老虎", "绵羊", "狐狸", "老黄牛", "蜜蜂", "狼"],
    triggers=[], source_type="ORGANISM", source_frame="Organism", target_frame="Trait"))


# --- 级联聚合 ---
_add_cascade(CascadeSpec("C_ARG_WAR", "ARGUMENT_IS_WAR",
    member_frames=["F_ARG_WAR", "F_COMP_WAR"],
    discourse_domains=["政治评论", "商业竞争"],
    typical_triggers=["开火", "商战", "护城河", "攻城略地"]))
_add_cascade(CascadeSpec("C_TIME_MONEY", "TIME_IS_MONEY",
    member_frames=["F_TIME_MONEY", "F_EFFORT_CUR"],
    discourse_domains=["职场", "财经"],
    typical_triggers=["花时间", "投入精力", "回报"]))
_add_cascade(CascadeSpec("C_PROGRESS_JOURNEY", "PROGRESS_IS_JOURNEY",
    member_frames=["F_PROG_JOURNEY", "F_CHANGE_MOTION", "F_OBST_TERRAIN"],
    discourse_domains=["项目管理", "政策"],
    typical_triggers=["推进", "转向", "停滞"]))
_add_cascade(CascadeSpec("C_LIFE_MACHINE", "LIFE_IS_A_MACHINE",
    member_frames=["F_LIFE_MACHINE", "F_BODY_MACHINE"],
    discourse_domains=["生活", "健康"],
    typical_triggers=["发条", "机械", "磨损"]))
_add_cascade(CascadeSpec("C_DIFFICULTY_TERRAIN", "DIFFICULTY_IS_TERRAIN",
    member_frames=["F_DIFF_TERRAIN"],
    discourse_domains=["项目困境", "创业"],
    typical_triggers=["泥潭", "沼泽", "悬崖"]))
_add_cascade(CascadeSpec("C_ANGER_HEAT", "ANGER_IS_HEAT",
    member_frames=["F_ANGER_HEAT", "F_AFF_WARM"],
    discourse_domains=["情绪", "文学"],
    typical_triggers=["火大", "暖心", "沸腾"]))
_add_cascade(CascadeSpec("C_MIND_CONTAINER", "MIND_IS_CONTAINER",
    member_frames=["F_MIND_CONT", "F_EMO_CONT"],
    discourse_domains=["心理", "文学"],
    typical_triggers=["装满", "积压", "释放"]))
# --- MIPVU/Wmatrix 语义域桥接级联 ---
_add_cascade(CascadeSpec("C_EVENT_IS_PLAY", "EVENT_IS_PERFORMANCE",
    member_frames=["F_EVENT_PLAY"],
    discourse_domains=["人生", "社会评论", "文学"],
    typical_triggers=[]))
_add_cascade(CascadeSpec("C_STATE_IS_NATURE", "STATE_IS_NATURE",
    member_frames=["F_STATE_NATURE"],
    discourse_domains=["文学", "抒情"],
    typical_triggers=[]))
_add_cascade(CascadeSpec("C_STRUCTURE_IS_BUILDING", "STRUCTURE_IS_BUILDING",
    member_frames=["F_STRUCT_BUILDING"],
    discourse_domains=["组织", "社会"],
    typical_triggers=[]))
_add_cascade(CascadeSpec("C_WORTH_IS_VALUE", "WORTH_IS_VALUE",
    member_frames=["F_WORTH_VALUE"],
    discourse_domains=["评价", "文学"],
    typical_triggers=[]))
_add_cascade(CascadeSpec("C_QUALITY_IS_SUBSTANCE", "QUALITY_IS_SUBSTANCE",
    member_frames=["F_QUALITY_SUBSTANCE"],
    discourse_domains=["感受", "文学"],
    typical_triggers=[]))
_add_cascade(CascadeSpec("C_TRAIT_IS_ORGANISM", "TRAIT_IS_ORGANISM",
    member_frames=["F_TRAIT_ORGANISM"],
    discourse_domains=["人物刻画", "文学"],
    typical_triggers=[]))


class CascadeOntology:
    """中文级联本体的查表层。

    提供两类核心查询：
      - 抽取阶段：match_by_triggers(触发词) → 候选框架（L1 抽取用）
      - 构建阶段：match_frame / get_cascade（L2/L3 归属用）
    """

    def __init__(self, frames: Dict[str, FrameSpec] = None,
                 cascades: Dict[str, CascadeSpec] = None):
        self.frames = frames or dict(_FRAMES)
        self.cascades = cascades or dict(_CASCADES)
        # 触发词 → 框架 反向索引（加速抽取）
        self._trigger_index: Dict[str, List[str]] = {}
        for fid, f in self.frames.items():
            for t in f.triggers:
                self._trigger_index.setdefault(t, []).append(fid)
        # 框架 → 级联 反向索引
        self._frame_to_cascade: Dict[str, str] = {}
        for cid, c in self.cascades.items():
            for fid in c.member_frames:
                self._frame_to_cascade[fid] = cid

    # ---- 抽取期：触发词 → 候选框架 ----
    def match_by_triggers(self, tokens: List[str]) -> List[FrameSpec]:
        hits: Dict[str, int] = {}
        for tok in tokens:
            for fid in self._trigger_index.get(tok, []):
                hits[fid] = hits.get(fid, 0) + 1
        # 按命中数排序，全部返回（由抽取器做置信度过滤）
        return [self.frames[fid] for fid, _ in
                sorted(hits.items(), key=lambda x: -x[1])]

    # ---- 构建期：源域/目标域 → 框架 ----
    def match_frame(self, source_domain: str, target_domain: str) -> Optional[str]:
        best = None
        for fid, f in self.frames.items():
            if f.source_domain == source_domain and f.target_domain == target_domain:
                return fid
            # 宽松匹配（仅源域命中）作为回退
            if f.source_domain == source_domain and best is None:
                best = fid
        return best

    def get_frame(self, frame_id: str) -> Optional[FrameSpec]:
        return self.frames.get(frame_id)

    # ---- 构建期：框架 → 级联 ----
    def get_cascade(self, frame_id: str) -> Optional[str]:
        return self._frame_to_cascade.get(frame_id)

    def get_cascade_spec(self, cascade_id: str) -> Optional[CascadeSpec]:
        return self.cascades.get(cascade_id)

    # ---- 类型安全约束（§4.1.3）----
    @staticmethod
    def type_valid(source_type: str, mapping_type: str) -> bool:
        return mapping_type in TYPE_CONSTRAINTS.get(source_type, [])

    def stats(self) -> str:
        return (f"CascadeOntology: {len(self.cascades)} 级联 / "
                f"{len(self.frames)} 框架 / "
                f"{len(self._trigger_index)} 触发词")


# 全局默认本体
DEFAULT_ONTOLOGY = CascadeOntology()
