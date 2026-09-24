# -*- coding: utf-8 -*-
"""双语对齐：中文生产本体 → MetaNet 英文概念隐喻名（路线图 §8.2 P1 项）。

**为什么需要它**
交付物之一是「中文隐喻级联本体（开放发布，≥1000 框架）」（方案 §9.2）。
开放的资源需要英文锚点才能与 MetaNet / FrameNet 生态对齐（复用其层级与
推理继承），也才能被双语研究引用。`ontology_default.json`（2177 框架）的
框架名是中文（`LLM::食物_IS_爱情`），本模块为其补英文对齐，落盘
`ontology_bilingual.json`。

**三级对齐策略（诚实标注，不虚构）**：
  curated    (中文源域,中文目标域) 与 MetaNet 内置概念隐喻完全一致
             （BUILTIN_CONCEPTUAL_METAPHORS 的 11 条，如 旅程→生活 = LIFE IS A JOURNEY）。
  auto_gloss 域级词典双向命中：en_name = "{EN_SOURCE} IS {EN_TARGET}"
             （如 食物→爱情 = FOOD IS LOVE）。**这是机器生成的词汇级转写**，
             只主张「概念域对应」，不主张该英文隐喻在 MetaNet 中真实存在 ——
             字段 `alignment` 让使用者一眼分级。
  unmapped   任一侧域不在词典中。保留原样，不强行猜。

运行：
    python -m metaphor_graph.ontology_bilingual          # 生成 + 打印覆盖率
"""

from __future__ import annotations

import argparse
import json
import re
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .metanet_migrate import BUILTIN_CONCEPTUAL_METAPHORS  # noqa: E402
from .llm_backend import _parse_json_blob  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ONTOLOGY_JSON = os.path.join(HERE, "ontology_default.json")
DEFAULT_OUT = os.path.join(HERE, "ontology_bilingual.json")

# ---------------------------------------------------------------------------
# 高频中文概念域 → 英文（域级词典；只收抽象概念域与具体经验域的基础词）
# ---------------------------------------------------------------------------
DOMAIN_ZH_EN = {
    # 具体经验域（源域一侧为主）
    "人体": "BODY", "身体": "BODY", "手": "HAND", "脚": "FOOT", "头": "HEAD",
    "眼": "EYE", "目光": "GAZE", "心": "HEART", "血": "BLOOD", "面孔": "FACE",
    "疾病": "DISEASE", "痛": "PAIN", "温度": "TEMPERATURE", "热": "HEAT",
    "冷": "COLD",
    "动物": "ANIMAL", "野兽": "BEAST", "昆虫": "INSECT", "鸟": "BIRD",
    "鱼": "FISH", "蜜蜂": "BEE", "蚂蚁": "ANT", "狐狸": "FOX", "狼": "WOLF",
    "虎": "TIGER", "蛇": "SNAKE", "马": "HORSE", "牛": "CATTLE", "羊": "SHEEP",
    "狗": "DOG", "猫": "CAT", "鹰": "HAWK",
    "植物": "PLANT", "花": "FLOWER", "草": "GRASS", "树": "TREE",
    "森林": "FOREST", "种子": "SEED", "根": "ROOT", "叶": "LEAF",
    "庄稼": "CROP", "农业": "FARMING", "种植": "PLANTING",
    "水流": "WATER", "水": "WATER", "液体": "LIQUID", "海洋": "SEA",
    "江河": "RIVER", "河": "RIVER", "海": "SEA", "湖": "LAKE", "浪": "WAVE",
    "潮": "TIDE", "洪": "FLOOD", "泉": "SPRING", "流": "FLOW", "漩涡": "WHIRLPOOL",
    "火": "FIRE", "火焰": "FLAME", "光": "LIGHT", "影": "SHADOW",
    "天气": "WEATHER", "风": "WIND", "雨": "RAIN", "雪": "SNOW", "冰": "ICE",
    "霜": "FROST", "雷": "THUNDER", "电": "LIGHTNING", "云": "CLOUD",
    "雾": "FOG", "星": "STAR", "天体": "CELESTIAL_BODY",
    "道路": "ROAD", "路": "ROAD", "旅程": "JOURNEY", "旅行": "TRAVEL",
    "交通": "TRANSPORT", "车": "VEHICLE", "船": "SHIP", "航海": "SAILING",
    "航行": "VOYAGE", "轨道": "TRACK", "行程": "ITINERARY", "旅途": "JOURNEY",
    "方向": "DIRECTION", "速度": "SPEED", "运动": "MOTION", "移动": "MOVEMENT",
    "战争": "WAR", "军事": "MILITARY", "武器": "WEAPON", "刀": "KNIFE",
    "剑": "SWORD", "枪": "GUN", "炮": "CANNON", "战场": "BATTLEFIELD",
    "战斗": "BATTLE", "军队": "ARMY", "士兵": "SOLDIER", "攻击": "ATTACK",
    "防御": "DEFENSE", "战略": "STRATEGY", "对手": "OPPONENT", "阵地": "POSITION",
    "建筑": "BUILDING", "房屋": "HOUSE", "房": "HOUSE", "楼": "BUILDING",
    "塔": "TOWER", "桥": "BRIDGE", "墙": "WALL", "门": "DOOR", "柱": "PILLAR",
    "梁": "BEAM", "地基": "FOUNDATION", "结构": "STRUCTURE", "工程": "ENGINEERING",
    "殿": "PALACE", "城堡": "CASTLE", "阶梯": "STAIRS",
    "机器": "MACHINE", "机械": "MACHINERY", "装置": "DEVICE", "齿轮": "GEAR",
    "发动机": "ENGINE", "仪表": "GAUGE", "设备": "EQUIPMENT", "仪器": "INSTRUMENT",
    "零件": "PART", "发条": "CLOCKWORK",
    "容器": "CONTAINER", "箱": "BOX", "盒": "BOX", "瓶": "BOTTLE",
    "罐": "JAR", "杯": "CUP", "袋": "BAG", "篮": "BASKET", "仓": "STORE",
    "库": "WAREHOUSE", "桶": "BUCKET", "囊": "SACK",
    "舞台": "STAGE", "戏剧": "DRAMA", "表演": "PERFORMANCE", "音乐": "MUSIC",
    "舞蹈": "DANCE", "游戏": "GAME", "电影": "MOVIE", "剧场": "THEATER",
    "戏": "PLAY", "角色": "ROLE", "幕": "ACT", "剧本": "SCRIPT",
    "物体": "OBJECT", "物品": "OBJECT", "器物": "UTENSIL", "器具": "TOOL",
    "金属": "METAL", "铁": "IRON", "石": "STONE", "木": "WOOD",
    "玻璃": "GLASS", "珍宝": "TREASURE", "珠宝": "JEWEL", "镜子": "MIRROR",
    "工具": "TOOL", "绳": "ROPE", "锁": "LOCK", "链": "CHAIN", "网": "NET",
    "布": "CLOTH", "纸": "PAPER", "线": "THREAD", "针": "NEEDLE",
    "球": "BALL", "笼": "CAGE", "重物": "WEIGHT", "担子": "BURDEN",
    "包袱": "BUNDLE", "货物": "CARGO", "家具": "FURNITURE", "器皿": "VESSEL",
    "尺": "RULER", "秤": "SCALE",
    "物质": "MATTER", "材料": "MATERIAL", "原料": "RAW_MATERIAL",
    "成分": "INGREDIENT", "化学": "CHEMISTRY", "泥": "MUD", "土": "EARTH",
    "沙": "SAND", "尘": "DUST", "灰": "ASH",
    "食物": "FOOD", "酒": "WINE", "蜜": "HONEY", "盐": "SALT", "糖": "SUGAR",
    "毒药": "POISON", "药": "MEDICINE", "棉花糖": "MARSHMALLOW",
    "金钱": "MONEY", "金融": "FINANCE", "经济": "ECONOMY", "货币": "CURRENCY",
    "财富": "WEALTH", "交易": "TRADE", "买卖": "BUSINESS", "资本": "CAPITAL",
    "市场": "MARKET", "价格": "PRICE", "成本": "COST",
    "空气": "AIR", "气味": "ODOR", "香": "FRAGRANCE", "臭": "STENCH",
    "声音": "SOUND", "回声": "ECHO",
    # 抽象目标域
    "时间": "TIME", "情感": "EMOTION", "情绪": "EMOTION", "爱": "LOVE",
    "爱情": "LOVE", "恨": "HATE", "愤怒": "ANGER", "恐惧": "FEAR",
    "喜悦": "JOY", "悲伤": "SADNESS", "希望": "HOPE", "绝望": "DESPAIR",
    "人": "PERSON", "人物": "PERSON", "人生": "LIFE", "生活": "LIFE",
    "生命": "LIFE", "命运": "FATE", "思想": "THOUGHT", "想法": "IDEA",
    "理念": "CONCEPT", "知识": "KNOWLEDGE", "理解": "UNDERSTANDING",
    "智慧": "WISDOM", "记忆": "MEMORY", "回忆": "REMINISCENCE",
    "梦想": "DREAM", "理想": "IDEAL", "信念": "BELIEF", "信仰": "FAITH",
    "心理": "MIND", "精神": "SPIRIT", "灵魂": "SOUL", "性格": "CHARACTER",
    "话语": "DISCOURSE", "语言": "LANGUAGE", "争论": "ARGUMENT",
    "对话": "DIALOGUE", "谎言": "LIE", "承诺": "PROMISE",
    "社会": "SOCIETY", "组织": "ORGANIZATION", "文化": "CULTURE",
    "历史": "HISTORY", "政治": "POLITICS", "权力": "POWER", "地位": "STATUS",
    "声誉": "REPUTATION", "名声": "FAME", "道德": "MORALITY", "伦理": "ETHICS",
    "善恶": "GOOD_AND_EVIL", "责任": "RESPONSIBILITY", "义务": "DUTY",
    "价值": "VALUE", "重要性": "IMPORTANCE", "品质": "QUALITY",
    "关系": "RELATIONSHIP", "友谊": "FRIENDSHIP", "家庭": "FAMILY",
    "团队": "TEAM", "合作": "COOPERATION", "竞争": "COMPETITION",
    "事业": "CAREER", "工作": "WORK", "项目": "PROJECT", "任务": "TASK",
    "计划": "PLAN", "战略规划": "STRATEGY", "决策": "DECISION",
    "目标": "GOAL", "目的": "PURPOSE", "过程": "PROCESS", "变化": "CHANGE",
    "发展": "DEVELOPMENT", "成长": "GROWTH", "进步": "PROGRESS",
    "困境": "DIFFICULTY", "困难": "DIFFICULTY", "问题": "PROBLEM",
    "机会": "OPPORTUNITY", "风险": "RISK", "危机": "CRISIS",
    "失败": "FAILURE", "成功": "SUCCESS", "努力": "EFFORT", "奋斗": "STRIVING",
    "经历": "EXPERIENCE", "感受": "FEELING", "状态": "STATE",
    "境遇": "CIRCUMSTANCE", "局势": "SITUATION", "形势": "SITUATION",
    "世界": "WORLD", "自然": "NATURE", "环境": "ENVIRONMENT",
    "空间": "SPACE", "位置": "POSITION", "高度": "HEIGHT", "深处": "DEPTH",
    "边界": "BOUNDARY", "范围": "SCOPE", "程度": "DEGREE", "水平": "LEVEL",
    "核心": "CORE", "中心": "CENTER", "顶层": "TOP", "底层": "BOTTOM",
    "侵蚀": "EROSION", "腐蚀": "CORROSION", "冲击": "IMPACT", "碰撞": "COLLISION",
    "压力": "PRESSURE", "力量": "FORCE", "能量": "ENERGY", "动力": "MOMENTUM",
    "束缚": "RESTRAINT", "解放": "LIBERATION", "自由": "FREEDOM",
    "伤害": "HARM", "创伤": "TRAUMA", "伤口": "WOUND", "痛苦": "SUFFERING",
    "煎熬": "TORMENT", "甜蜜": "SWEETNESS", "幸福": "HAPPINESS",
    "温暖": "WARMTH", "寒冷": "COLDNESS", "黑暗": "DARKNESS", "光明": "BRIGHTNESS",
    "清晰": "CLARITY", "模糊": "VAGUENESS", "复杂": "COMPLEXITY",
    "简单": "SIMPLICITY", "秩序": "ORDER", "混乱": "CHAOS",
    "答案": "ANSWER", "方法": "METHOD", "路径": "PATH", "途径": "APPROACH",
    "手段": "MEANS", "资源": "RESOURCE", "财富积累": "ACCUMULATION",
    "作品": "WORK_OF_ART", "创作": "CREATION", "艺术": "ART", "文学": "LITERATURE",
    "故事": "STORY", "情节": "PLOT", "灵感": "INSPIRATION", "想象": "IMAGINATION",
    "幻想": "FANTASY", "谜语": "RIDDLE", "秘密": "SECRET",
    "学习": "LEARNING", "教育": "EDUCATION", "阅读": "READING",
    "青春": "YOUTH", "童年": "CHILDHOOD", "老去": "AGING",
    "头脑": "MIND", "胸怀": "BOSOM", "眉睫": "IMMINENCE", "根基": "FOUNDATION",
    "壁垒": "RAMPART", "护城河": "MOAT", "窗口": "WINDOW", "桥梁": "BRIDGE",
    "浪潮": "WAVE", "洪流": "TORRENT", "风口": "TREND", "蓝海": "BLUE_OCEAN",
    "硝烟": "GUNSMOKE", "炮火": "FIRE", "熵": "ENTROPY",
    # —— 第二轮补充（按 unmapped 高频域统计扩入）——
    "医疗": "MEDICINE", "车辆": "VEHICLE", "飞行": "FLIGHT", "生物": "ORGANISM",
    "地理": "GEOGRAPHY", "宝石": "GEM", "绘画": "PAINTING", "阳光": "SUNSHINE",
    "颜色": "COLOR", "生育": "BIRTH", "山": "MOUNTAIN", "衣物": "CLOTHING",
    "石头": "STONE", "泡沫": "FOAM", "钥匙": "KEY", "遮盖": "COVERING",
    "行走": "WALKING", "爆炸": "EXPLOSION", "摇篮": "CRADLE", "洪水": "FLOOD",
    "土地": "LAND", "商品": "GOODS", "烹饪": "COOKING", "固体": "SOLID",
    "魔术": "MAGIC", "季节": "SEASON", "影响": "INFLUENCE", "言语": "SPEECH",
    "人际": "INTERPERSONAL", "自我": "SELF", "内心": "INNER_MIND",
    "国家": "NATION", "眼睛": "EYES", "心灵": "MIND", "书": "BOOK",
    "科技": "TECHNOLOGY", "消除": "ELIMINATION", "心情": "MOOD",
    "观念": "NOTION", "城市": "CITY", "控制": "CONTROL", "表情": "EXPRESSION",
    # —— 第三轮补充（第二轮 unmapped 高频域统计）——
    "母亲": "MOTHER", "老师": "TEACHER", "孩子": "CHILD", "敌人": "ENEMY",
    "考试": "EXAM", "商业": "BUSINESS", "企业": "ENTERPRISE", "财产": "PROPERTY",
    "天空": "SKY", "婚姻": "MARRIAGE", "睡眠": "SLEEP", "死亡": "DEATH",
    "织物": "FABRIC", "宝藏": "TREASURE", "注意": "ATTENTION", "时代": "ERA",
    "障碍": "OBSTACLE", "灯光": "LIGHTING", "信息": "INFORMATION",
    "饮食": "DIET", "动作": "ACTION", "气氛": "ATMOSPHERE", "果实": "FRUIT",
    "成果": "ACHIEVEMENT", "能力": "ABILITY", "编织": "WEAVING", "太阳": "SUN",
    "抓握": "GRASP", "绿洲": "OASIS", "消化": "DIGESTION", "风景": "SCENERY",
    "网络": "NETWORK", "书籍": "BOOKS", "意志": "WILL", "比赛": "COMPETITION",
    "改革": "REFORM", "丝线": "SILK_THREAD", "成就": "ACCOMPLISHMENT",
    "挖掘": "EXCAVATION", "友情": "FRIENDSHIP", "神话": "MYTH",
    "事件": "EVENT", "文章": "ARTICLE", "文明": "CIVILIZATION", "文字": "WRITING",
    "虫": "INSECT", "手机": "PHONE",
}


def _en_name(src_en: str, tgt_en: str) -> str:
    """英文隐喻名：复数/系词的粗糙统一 —— 只做词汇级转写，不做语法承诺。"""
    return f"{src_en} IS {tgt_en}"


def build_bilingual(ontology_json: str = DEFAULT_ONTOLOGY_JSON,
                    out_path: str = DEFAULT_OUT) -> dict:
    with open(ontology_json, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # curated 层：(中文源域,中文目标域) → 英文名（MetaNet 内置 11 条）
    curated = {(it["source_domain"], it["target_domain"]): it["en"]
               for it in BUILTIN_CONCEPTUAL_METAPHORS}

    rows = {}
    stats = Counter()
    for fr in payload["frames"]:
        s, t = fr["source_domain"], fr["target_domain"]
        if (s, t) in curated:
            en_name, en_s, en_t, align = curated[(s, t)], "", "", "curated"
        elif s in DOMAIN_ZH_EN and t in DOMAIN_ZH_EN:
            en_s, en_t = DOMAIN_ZH_EN[s], DOMAIN_ZH_EN[t]
            en_name, align = _en_name(en_s, en_t), "auto_gloss"
        else:
            en_name, en_s, en_t, align = "", "", "", "unmapped"
        stats[align] += 1
        rows[fr["id"]] = {
            "zh_name": fr["name"], "zh_source": s, "zh_target": t,
            "en_name": en_name, "en_source": en_s, "en_target": en_t,
            "alignment": align, "tier": fr.get("tier", ""),
            "support": fr.get("support", 0),
        }

    coverage = {
        "n_frames": len(payload["frames"]),
        "curated": stats["curated"],
        "auto_gloss": stats["auto_gloss"],
        "unmapped": stats["unmapped"],
        "note": ("auto_gloss 是域级词典的机器转写（只主张概念域对应，"
                 "不主张该英文隐喻在 MetaNet 中真实存在）；curated 与 "
                 "BUILTIN_CONCEPTUAL_METAPHORS 完全一致。"),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"coverage": coverage, "alignments": rows}, f,
                  ensure_ascii=False, indent=1)
    return coverage


def _load_llm_ext() -> dict:
    """加载 LLM 翻译的域词典扩展（--llm-complete 生成；无则空）。"""
    ext_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "data", "bilingual_llm_ext.json")
    if os.path.exists(ext_path):
        with open(ext_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def llm_complete(ontology_json: str = DEFAULT_ONTOLOGY_JSON) -> dict:
    """AI 补全：把 unmapped 域词批量交 LLM 翻译，落盘扩展词典并重建对齐。

    诚实口径：LLM 翻译的域对应仍是「概念域词汇级转写」（同 auto_gloss 级别），
    不主张英文隐喻在 MetaNet 中真实存在；alignment 标记仍为 auto_gloss。
    """
    with open(ontology_json, "r", encoding="utf-8") as f:
        payload = json.load(f)
    # 当前对齐里 unmapped 框架的两侧域词
    counts_prev = build_bilingual(ontology_json, DEFAULT_OUT + ".tmp")
    with open(DEFAULT_OUT + ".tmp", "r", encoding="utf-8") as f:
        prev = json.load(f)
    words = set()
    for r in prev["alignments"].values():
        if r["alignment"] == "unmapped":
            if r["zh_source"] not in DOMAIN_ZH_EN:
                words.add(r["zh_source"])
            if r["zh_target"] not in DOMAIN_ZH_EN:
                words.add(r["zh_target"])
    os.remove(DEFAULT_OUT + ".tmp")
    words = sorted(words)
    print(f"待翻译域词 {len(words)} 个")

    cache_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "llm_cache_bilingual.json")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    todo = [w for w in words if w not in cache]
    if todo:
        if not os.environ.get("LLM_API_KEY"):
            raise SystemExit("需要 LLM_API_KEY")
        from .evaluate_real import build_llm_backend
        backend = build_llm_backend()
        backend.timeout = 180.0
        batch = 30
        for bi in range(0, len(todo), batch):
            part = todo[bi:bi + batch]
            user = ("给出每个中文概念域的英文对应（1-3 个英文单词，全大写，"
                    "下划线连接；常识性概念域，不要隐喻义）。\n"
                    "概念词：" + "、".join(part) +
                    '\n只输出 JSON 对象：{"词": "ENGLISH", ...}，键必须齐全。')
            parsed = None
            for _ in range(2):
                try:
                    out = _raw_chat_compat(backend, user)
                    parsed = _parse_json_blob(out)
                    if isinstance(parsed, dict) and parsed:
                        break
                except Exception as e:
                    print(f"    [翻译批次失败] {type(e).__name__}: {str(e)[:60]}",
                          flush=True)
                    import time as _t
                    _t.sleep(3)
            if not parsed:
                print(f"    [翻译批次失败] 第 {bi // batch + 1} 批跳过", flush=True)
                continue
            got = 0
            for w in part:
                v = parsed.get(w)
                if isinstance(v, str) and v.strip():
                    cache[w] = re.sub(r"[^A-Z_]", "",
                                      v.strip().upper().replace(" ", "_")) or v.strip().upper()
                    got += 1
            print(f"    翻译批次 {bi // batch + 1}: +{got}/{len(part)}"
                  f"（累计 {len(cache)}）", flush=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=1)
    # 合并进域词典（运行时扩展）+ **持久化扩展词典**（spot_check 与
    # 未来重建都要用；只写本次新增的键）
    new_ext = {k: v for k, v in cache.items() if v and k not in DOMAIN_ZH_EN}
    DOMAIN_ZH_EN.update({k: v for k, v in cache.items() if v})
    ext_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "bilingual_llm_ext.json")
    existing = {}
    if os.path.exists(ext_path):
        with open(ext_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing.update(new_ext)
    with open(ext_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=1)
    cov = build_bilingual(ontology_json, DEFAULT_OUT)
    return cov


def _raw_chat_compat(backend, user) -> str:
    import urllib.request
    payload = {"model": backend.model,
               "messages": [{"role": "system", "content":
                             "你是术语翻译专家。只输出 JSON。"},
                            {"role": "user", "content": user}],
               "temperature": 0.2}
    if backend.extra_body:
        payload.update(backend.extra_body)
    req = urllib.request.Request(
        backend.endpoint, data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {backend.api_key}"})
    import urllib.error
    with urllib.request.urlopen(req, timeout=backend.timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data["choices"][0]["message"]["content"]).strip()


def spot_check(sample_n: int = 84, temp: float = 0.7) -> dict:
    """AI 自一致性抽检（D5 的 AI 替代）：抽样重译比对翻译稳定性。

    诚实口径：同一模型（glm-5.3-flash）不同提示框架/温度的**自一致性**检查，
    非独立验证；一致 = 归一化（大写/去空格/连字符转下划线）后完全相同或互为前缀。
    """
    ext_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "bilingual_llm_ext.json")
    ext = json.load(open(ext_path, encoding="utf-8"))
    import random as _rd
    rng = _rd.Random(20260907)
    words = sorted(ext)
    rng.shuffle(words)
    words = words[:sample_n]
    print(f"自一致性抽检：{len(words)} / {len(ext)} 词（temp={temp}）")

    if not os.environ.get("LLM_API_KEY"):
        raise SystemExit("需要 LLM_API_KEY")
    from .evaluate_real import build_llm_backend
    backend = build_llm_backend()
    backend.timeout = 180.0

    match = mismatch = 0
    samples = []
    batch = 30
    for bi in range(0, len(words), batch):
        part = words[bi:bi + batch]
        user = ("对每个中文概念域，独立给出你认为最标准的英文对应（1-3 个英文单词，"
                "全大写下划线连接；凭你自己的判断，无需参考其它格式）。\n"
                "概念词：" + "、".join(part) +
                '\n只输出 JSON：{"词": "ENGLISH", ...}，键必须齐全。')
        parsed = None
        for _ in range(2):
            try:
                raw = _raw_chat_compat(backend, user)
                parsed = _parse_json_blob(raw)
                if isinstance(parsed, dict) and parsed:
                    break
            except Exception as e:
                print(f"    [抽检批次失败] {type(e).__name__}: {str(e)[:50]}",
                      flush=True)
                import time as _t
                _t.sleep(3)
        if not parsed:
            continue
        for w in part:
            orig = str(ext[w]).upper().replace(" ", "_")
            new = str(parsed.get(w, "")).upper().replace(" ", "_").replace("-", "_")
            ok = (new == orig) or (new.startswith(orig)) or (orig.startswith(new))
            match += 1 if ok else 0
            mismatch += 0 if ok else 1
            samples.append({"word": w, "first": ext[w],
                            "second": str(parsed.get(w, "")), "match": bool(ok)})
    rate = match / max(1, match + mismatch)
    out_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "bilingual_spotcheck.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"self_consistency": rate, "n": match + mismatch,
                   "samples": samples}, f, ensure_ascii=False, indent=1)
    print(f"自一致率 {rate:.1%}（{match}/{match + mismatch}）→ {out_path}")
    print("诚实口径：同模型不同提示的自一致性，非独立验证；分歧词可人工复核。")
    return {"self_consistency": rate, "n": match + mismatch}


def main():
    import urllib.request  # noqa: F401
    ap = argparse.ArgumentParser()
    ap.add_argument("--ontology", default=DEFAULT_ONTOLOGY_JSON)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--llm-complete", action="store_true",
                    help="AI 补全：LLM 翻译 unmapped 域词后重建对齐（需 LLM_API_KEY）")
    ap.add_argument("--spot-check", action="store_true",
                    help="AI 自一致性抽检：抽样重译比对（D5 的 AI 替代）")
    args = ap.parse_args()
    if args.spot_check:
        spot_check()
        return 0
    if args.llm_complete:
        cov = llm_complete(args.ontology)
    else:
        cov = build_bilingual(args.ontology, args.out)
    print(f"双语对齐 → {args.out}")
    print(f"  框架总数 {cov['n_frames']}：curated {cov['curated']} / "
          f"auto_gloss {cov['auto_gloss']} / unmapped {cov['unmapped']}")
    n_aligned = cov['curated'] + cov['auto_gloss']
    print(f"  对齐率 {n_aligned / cov['n_frames']:.1%}（全量）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
