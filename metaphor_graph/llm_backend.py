# -*- coding: utf-8 -*-
"""LLM 后端接入（方案 §6.1 / §8 路线图）。

把「真实大模型」作为可插拔后端接入 L1 抽取与 L2/L3 构建，目标是突破
「触发词天花板」与「语义域词表覆盖」带来的召回瓶颈（README §6.4/§6.5
已实证：在 P1<15% 硬门槛下，纯规则召回被钉在 ~9.7%，再上必须靠 LLM）：

    - discover(chunk) -> List[LLMCandidate]
        开放发现：从自由文本直接找隐喻候选（不依赖触发词表，召回突破的关键）。
    - refine(chunk, frame) -> Optional[LLMRefine]
        细化：确认 / 否认「触发词通道 / 语义域通道」已命中的候选，并给出置信度与喻底。
    - cluster(edges) -> Optional[dict]
        构建期回退：对未匹配到本体的 L1 超边做 L2/L3 聚类命名（少量调用）。

提供三类实现：
    - OpenAIBackend        真实 OpenAI 兼容端点（标准库 urllib，零额外依赖）。
                            可配参数或环境变量 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。
                            网络/超时/解析失败一律优雅降级（返回空/None），抽取不崩。
    - LocalHeuristicBackend 离线确定性近似（等比结构挖掘），用于演示/测试/无密钥环境。
                            它复用了与 MIPVU 通道相同的「等比标记 + 本体/语义域绑定」思路，
                            但走统一 llm_backend 接口 —— 因此换成 OpenAIBackend 只需一行。
    - MockBackend          单测用，返回预置结果。

接入方式见 MetaphorExtractor(llm_backend=...) 与 MetaphorSHGBuilder(llm_backend=...)。
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, runtime_checkable

from .ontology import DEFAULT_ONTOLOGY, CascadeOntology, FrameSpec
from . import semfield

logger = logging.getLogger("metaphor_graph.llm_backend")

# 认证/计费类错误：重试无意义，且**绝不能**降级成"没有隐喻"。
# （本次踩坑：DeepSeek 账户欠费返回 402，被优雅降级吞成空结果，
#   导致域归并返回 100% 恒等映射、本体碎片化，而流程一路"成功"。）
_FATAL_HTTP_CODES = {
    401: "API Key 无效或过期",
    402: "账户余额不足/欠费，请充值",
    403: "无该模型权限或地区受限",
}


class LLMFatalError(RuntimeError):
    """LLM 后端致命错误（认证/计费/权限）。

    刻意**不**被 except Exception 吞掉：这类错误重试无用，
    静默降级会产出看似正常实则全错的结果。
    """


# ----------------------------------------------------------------------------
# 数据协议
# ----------------------------------------------------------------------------
@runtime_checkable
class MetaphorLLMBackend(Protocol):
    """LLM 后端接口（结构化协议，鸭子类型即可，无需继承）。

    三个方法：
        discover(chunk)        开放发现 —— 突破召回天花板的关键通道
        refine(chunk, frame)   细化确认 —— 对已命中候选做是/否判断与置信度调整
        cluster(edges)         构建期回退 —— 对未匹配本体的超边做 L2/L3 聚类命名
    """

    def discover(self, chunk: str) -> List["LLMCandidate"]: ...

    def refine(self, chunk: str, frame: FrameSpec) -> Optional["LLMRefine"]: ...

    def cluster(self, edges) -> Optional[dict]: ...


@dataclass
class LLMCandidate:
    """LLM 开放发现产出的单条隐喻候选（尚未过类型安全约束）。"""

    source_domain: str
    target_domain: str
    ground: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)   # 原文中的喻体/触发词（用于定位）
    confidence: float = 0.6


@dataclass
class LLMRefine:
    """LLM 对「已命中候选」的细化结论。"""

    is_metaphor: bool
    confidence: float = 0.6
    ground: List[str] = field(default_factory=list)


def _parse_json_blob(text: str):
    """容错解析：先整段 json.loads，失败则回退到抽取首个 [...] 或 {...} 子串。"""
    if text is None:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except json.JSONDecodeError:
            pass
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except json.JSONDecodeError:
            pass
    return None


# ----------------------------------------------------------------------------
# 1) OpenAIBackend —— 真实 OpenAI 兼容端点
# ----------------------------------------------------------------------------
# MIPVU 判定标准 + 排除项。
# 这段是**压住 P1 的关键**：实测去掉它时，模型会把固化成语（"七上八下"）、
# 描写性美称（"琼玉世界"）、拟人（"钟塔告诫学子"）都判成隐喻，
# CCL2018 全量上 P1 直接飙到 28.9%（门槛 15%）。
_MIPVU_RULE = (
    "判定标准（MIPVU）：只有当某个词在语境中的意义**不同于它的基本义**"
    "（基本义通常更具体、更物理、更常用于描述具体事物），"
    "且语境义可以通过与基本义的比较来理解时，才算隐喻。\n"
    "以下**不算**隐喻，必须排除：\n"
    "1) 已词汇化的成语 / 惯用语（如「七上八下」「守株待兔」）—— 隐喻义已固化进词义；\n"
    "2) 纯描写性修饰语 / 美称（如「琼玉世界」「金色大厅」）；\n"
    "3) 字面用法与身份判断句（如「苏利曼是苏丹」「他是我的朋友」）。\n"
    "拿不准时宁可不标，输出空数组。"
)

_DISCOVER_SYSTEM = (
    "你是一名认知语言学与计算隐喻分析专家。给定中文文本，"
    "找出其中使用的概念隐喻（跨域映射）。\n" + _MIPVU_RULE
)
# 输出字段里带 basic_meaning，是刻意的：逼模型先确认「基本义 ≠ 语境义」再下结论，
# 等价于让它把 MIPVU 判据走一遍（实测能明显压掉固化成语类的误判）。
_FIELDS_SPEC = (
    "{{\"source_domain\": \"源域(如 机器/战争/泥潭)\", "
    "\"target_domain\": \"目标域(如 生活状态/争论/项目困境)\", "
    "\"basic_meaning\": \"该喻体词的基本义(字面义，用以确认与语境义不同)\", "
    "\"ground\": [\"喻底词列表\"], "
    "\"triggers\": [\"原文中的喻体或触发词，须是文本里真实出现的词\"], "
    "\"confidence\": 0到1 之间的数}}"
)

_DISCOVER_USER = (
    "文本：{chunk}\n"
    "请只输出一个 JSON 数组，每个元素形如：\n" + _FIELDS_SPEC + "。\n"
    "若文本没有隐喻，输出 []。不要输出任何说明文字，只输出 JSON。"
)

# 批量版提示：**摊薄固定样板开销的关键**。
# 实测：CCL2018 句子中位数仅 15 字，而单次调用的样板提示就有 321 字，
# 逐句调用时 91% 的输入 token 都是样板。按批发送可把这部分摊薄（20 句/批 → 省 86%）。
_DISCOVER_BATCH_USER = (
    "下面有 {n} 个句子，编号 1 到 {n}。请对**每个句子分别**找出其中使用的概念隐喻。\n"
    "{body}\n"
    "只输出一个 JSON 对象：键是句子编号（字符串），值是该句子的隐喻候选数组，形如：\n"
    "{{\"1\": [" + _FIELDS_SPEC + "], \"2\": []}}\n"
    "某句没有隐喻就给空数组 []。编号必须齐全。不要输出任何说明文字，只输出 JSON。"
)

_REFINE_SYSTEM = _DISCOVER_SYSTEM
_REFINE_BATCH_USER = (
    "下面有 {n} 条「文本 + 候选概念隐喻框架」需要判断：该文本是否**真的**使用了"
    "这个隐喻（而非字面用法）。\n{body}\n"
    "只输出一个 JSON 对象：键是编号（字符串），值是判断结果，形如：\n"
    '{{"1": {{"is_metaphor": true, "confidence": 0.9, "ground": ["喻底词"]}}, '
    '"2": {{"is_metaphor": false, "confidence": 0.2, "ground": []}}}}\n'
    "编号必须齐全。不要输出任何说明文字，只输出 JSON。"
)

_REFINE_USER = (
    "候选概念隐喻框架：源域={sd}，目标域={td}。\n"
    "文本：{chunk}\n"
    "判断该文本是否真的使用了这个隐喻（而非字面用法）。\n"
    "只输出一个 JSON 对象：{{\"is_metaphor\": true 或 false, "
    "\"confidence\": 0到1 的数, \"ground\": [\"喻底词\"]}}。"
    "不要输出任何说明文字，只输出 JSON。"
)


class OpenAIBackend:
    """OpenAI 兼容 Chat Completions 后端（零额外依赖，标准库 urllib）。

    可对接：OpenAI、DeepSeek、通义千问、本地 vLLM / Ollama OpenAI 兼容服务等。
    失败时优雅降级：discover 返回 []，refine 返回 None（即「不判为隐喻」），
    因此即便 LLM 不可用，整条抽取流水线仍照常工作（只是少了 LLM 增益）。

    配置优先级：显式参数 > 环境变量 > 默认值。
    """

    def __init__(self, api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 model: Optional[str] = None,
                 temperature: float = 0.0, timeout: float = 20.0,
                 verbose: bool = False, extra_body: Optional[dict] = None):
        self.api_key = api_key if api_key is not None else os.environ.get("LLM_API_KEY")
        base = base_url or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        self.endpoint = base.rstrip("/") + "/chat/completions"
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.temperature = temperature
        self.timeout = timeout
        self.verbose = verbose
        # 累计用量（读响应里的 usage 字段，用于精确核算成本，而非估算）
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                      "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}
        # 致命错误标记（401/402/403）；非空表示结果不可信
        self.fatal_error: Optional[str] = None
        # 透传厂商私有参数（合并进请求体）。典型用途：
        #   GLM-5.3 / glm-5.3-flash：{"reasoning_effort": "low"} —— 该模型 thinking 默认开启、
        #   不可关闭，reasoning_effort 直接决定思考 token 的开销，抽词这类简单任务用 low 即可。
        #   OpenAI o 系列：{"reasoning_effort": "low"}；Ollama：{"options": {...}}
        self.extra_body = extra_body
        if self.verbose:
            logger.setLevel(logging.INFO)

    @classmethod
    def from_env(cls, model: Optional[str] = None, **kw) -> "OpenAIBackend":
        """用环境变量 LLM_API_KEY/LLM_BASE_URL/LLM_MODEL 构造。"""
        return cls(api_key=os.environ.get("LLM_API_KEY"),
                   base_url=os.environ.get("LLM_BASE_URL"),
                   model=model or os.environ.get("LLM_MODEL"), **kw)

    def _accumulate_usage(self, usage: Optional[dict]):
        """累加厂商返回的 usage（各厂商字段名不完全一致，缺字段就跳过）。"""
        if not isinstance(usage, dict):
            return
        self.usage["calls"] += 1
        direct = {"prompt_tokens", "completion_tokens",
                  "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"}
        for k in direct:
            v = usage.get(k)
            if isinstance(v, (int, float)):
                self.usage[k] += int(v)
        # OpenAI 系把缓存明细放在 prompt_tokens_details 里
        det = usage.get("prompt_tokens_details")
        if isinstance(det, dict):
            v = det.get("cached_tokens")
            if isinstance(v, (int, float)):
                self.usage["prompt_cache_hit_tokens"] += int(v)

    def usage_report(self) -> str:
        """用量小结（精确核算成本用）。"""
        u = self.usage
        cached = u["prompt_cache_hit_tokens"]
        miss = u["prompt_cache_miss_tokens"] or max(0, u["prompt_tokens"] - cached)
        return (f"调用 {u['calls']} 次 | 输入 {u['prompt_tokens']:,} tok"
                f"（缓存命中 {cached:,} / 未命中 {miss:,}）"
                f" | 输出 {u['completion_tokens']:,} tok")

    # ---- 与模型对话（统一入口，含优雅降级）----
    def _chat(self, system: str, user: str):
        if not self.api_key:
            logger.warning("OpenAIBackend 未配置 api_key，跳过 LLM 调用（返回空结果）。"
                           "可设环境变量 LLM_API_KEY 或显式传 api_key=。")
            return None
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": self.temperature,
        }
        if self.extra_body:
            payload.update(self.extra_body)
        try:
            req = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.api_key}"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
            self._accumulate_usage(data.get("usage"))
            if self.verbose:
                logger.info("LLM raw: %s", content)
            return _parse_json_blob(content)
        except urllib.error.HTTPError as ex:
            # 4xx 里的认证/计费类是**致命错误**：重试一万次也不会成功，
            # 而降级成"没有隐喻"更糟 —— 它会让整批语料静默变成空结果，
            # 下游所有指标看起来"跑通了"，实际全是错的（本次 402 欠费就是这么被吞掉的）。
            code = getattr(ex, "code", None)
            if code in _FATAL_HTTP_CODES:
                self.fatal_error = f"HTTP {code}（{_FATAL_HTTP_CODES[code]}）"
                logger.error(
                    "LLM 调用**致命失败**，不再重试也不静默降级：%s。"
                    "请检查 API Key / 账户余额 / 权限后重跑。", self.fatal_error)
                raise LLMFatalError(self.fatal_error) from ex
            logger.warning("OpenAIBackend HTTP %s，降级为空结果：%s", code, ex)
            return None
        except Exception as ex:  # 网络/超时/解析/字段缺失 → 优雅降级
            logger.warning("OpenAIBackend 调用失败，降级为空结果：%s", ex)
            return None

    # ---- 开放发现 ----
    def discover(self, chunk: str) -> List[LLMCandidate]:
        out: List[LLMCandidate] = []
        parsed = self._chat(_DISCOVER_SYSTEM, _DISCOVER_USER.format(chunk=chunk))
        if not isinstance(parsed, list):
            return out
        for item in parsed:
            if not isinstance(item, dict):
                continue
            sd, td = item.get("source_domain"), item.get("target_domain")
            if not sd or not td:
                continue
            out.append(LLMCandidate(
                source_domain=str(sd), target_domain=str(td),
                ground=[str(g) for g in (item.get("ground") or [])],
                triggers=[str(t) for t in (item.get("triggers") or [])],
                confidence=float(item.get("confidence", 0.6)),
            ))
        return out

    # ---- 批量开放发现（摊薄样板开销，强烈建议用于大批量语料）----
    def discover_batch(self, chunks: List[str]) -> List[List[LLMCandidate]]:
        """一次请求处理多句，返回与 chunks 等长的结果列表。

        实测（CCL2018，1100 句）：逐句调用的输入中 91% 是固定样板；
        20 句/批 可省约 86% 输入 token，并把请求数从 1100 降到 55（延迟同步大幅下降）。
        解析失败时整批降级为空列表，绝不抛异常。
        """
        n = len(chunks)
        if n == 0:
            return []
        body = "\n".join(f"{i}. {t}" for i, t in enumerate(chunks, 1))
        parsed = self._chat(_DISCOVER_SYSTEM,
                            _DISCOVER_BATCH_USER.format(n=n, body=body))
        out: List[List[LLMCandidate]] = [[] for _ in chunks]
        if not isinstance(parsed, dict):
            logger.warning("discover_batch: 响应不是 JSON 对象，整批降级为空。")
            return out
        for key, items in parsed.items():
            try:
                idx = int(str(key)) - 1
            except (TypeError, ValueError):
                continue
            if not (0 <= idx < n) or not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                sd, td = item.get("source_domain"), item.get("target_domain")
                if not sd or not td:
                    continue
                out[idx].append(LLMCandidate(
                    source_domain=str(sd), target_domain=str(td),
                    ground=[str(g) for g in (item.get("ground") or [])],
                    triggers=[str(t) for t in (item.get("triggers") or [])],
                    confidence=float(item.get("confidence", 0.6)),
                ))
        return out

    # ---- 批量细化（与 discover_batch 同理：摊薄样板 + 减少请求数）----
    def refine_batch(self, items: List[tuple]) -> List[Optional["LLMRefine"]]:
        """一次请求判断多条 (文本, 源域, 目标域)，返回等长结果列表。

        为什么必须批量：本体扩充到 679 框架后，触发词通道的候选暴涨，
        实测 1100 句要发 **2,297 次** refine 请求（串行约 23 分钟）。
        批量后降到 ~115 次，与 discover 同量级。

        items: [(chunk, source_domain, target_domain), ...]
        """
        n = len(items)
        if n == 0:
            return []
        body = "\n".join(f"{i}. 文本：{c} | 源域：{s} | 目标域：{t}"
                         for i, (c, s, t) in enumerate(items, 1))
        parsed = self._chat(_REFINE_SYSTEM, _REFINE_BATCH_USER.format(n=n, body=body))
        out: List[Optional[LLMRefine]] = [None] * n
        if not isinstance(parsed, dict):
            logger.warning("refine_batch: 响应不是 JSON 对象，整批降级为空。")
            return out
        for key, val in parsed.items():
            try:
                idx = int(str(key)) - 1
            except (TypeError, ValueError):
                continue
            if not (0 <= idx < n) or not isinstance(val, dict):
                continue
            out[idx] = LLMRefine(
                is_metaphor=bool(val.get("is_metaphor", False)),
                confidence=float(val.get("confidence", 0.6)),
                ground=[str(g) for g in (val.get("ground") or [])],
            )
        return out

    # ---- 细化已命中候选 ----
    def refine(self, chunk: str, frame: FrameSpec) -> Optional[LLMRefine]:
        parsed = self._chat(_REFINE_SYSTEM,
                            _REFINE_USER.format(chunk=chunk,
                                                sd=frame.source_domain,
                                                td=frame.target_domain))
        if not isinstance(parsed, dict):
            return None
        return LLMRefine(
            is_metaphor=bool(parsed.get("is_metaphor", False)),
            confidence=float(parsed.get("confidence", 0.6)),
            ground=[str(g) for g in (parsed.get("ground") or [])],
        )

    # ---- 构建期聚类命名（可选，默认不实现）----
    def cluster(self, edges) -> Optional[dict]:
        return None


# ----------------------------------------------------------------------------
# 2) LocalHeuristicBackend —— 离线确定性近似（无密钥可跑）
# ----------------------------------------------------------------------------
_PUNCT = set("，。；、！？：（）《》“”‘’…—,.!?;:()[]{}'\"")
# 虚词词性：代词/数词/量词/助词/介词/连词 —— 在标记与喻体之间应被跳过
_FUNC_FLAGS = ("r", "m", "q", "u", "p", "c", "e", "y")
_SKIP_WORDS = {"的", "了", "个", "一", "之", "着", "过", "地", "得"}
# 专有名词词性：人名 nr / 地名 ns / 机构名 nt / 其他专名 nz
# —— 等比句里作谓语时基本是身份判断（"苏利曼是苏丹"），不是跨域映射
_PROPER_NOUN_FLAGS = ("nr", "ns", "nt", "nz")


class LocalHeuristicBackend:
    """离线 LLM 近似：用「等比标记 + 喻体名词」做开放发现，再把喻体绑定到本体。

    喻体识别走 **jieba 词性标注**（与 bootstrap_triggers / mipvu 同思路），
    而非裸正则 —— 裸正则会抓出「个舞台」「我们团队的」这类错误片段。

    取词规则（刻意保守，优先压住 P1）：
      - 从等比标记（是/就是/像/如同/成为/化作……）向后扫描窗口；
      - 跳过虚词（的/了/个/一 + r/m/q/u/p/c/e/y）；
      - 遇到名词(len≥2) 收录；遇到**既非名词也非虚词**的词即停止
        （如「他是我最好的朋友」中「最好」是形容词 → 直接停，不产出喻体）；
      - 若中途跳过过「的」，则取「的」之后的名词（"是我们团队的顶梁柱"→顶梁柱）；
        否则取第一个名词（"就是一个舞台"→舞台）。

    喻体随后由 _bind 绑定到已知框架（类型护栏生效）或 GENERIC 通道。

    **为何默认不产出「绑不上的喻体」（allow_generic=False）**：
    离线近似拿不到 target_domain（只能填「待 LLM 补全」），于是把「父母/奥斯曼帝国/
    待机时间/夫人」这类**字面身份判断句**的名词也当成喻体了。实测在 CCL2018 上，
    这类 GENERIC 候选贡献了**全部**字面误判，把 P1 顶到 17%（超 15% 硬门槛）。
    而它们本该由真实 LLM 来判断并补全 target_domain。因此默认只在**能确定概念映射**
    （已知框架 / 已知语义域）时才发言；置 allow_generic=True 可放开（召回更高、P1 更高），
    仅建议用于在接真实 LLM 前观察「新喻体」的潜在收益。

    注意：这是「弱 LLM」近似，召回增益有限（受等比结构与词表限制）；
    真实召回突破请用 OpenAIBackend（配置 LLM_API_KEY）。
    """

    def __init__(self, ontology: CascadeOntology = None,
                 allow_generic: bool = False):
        self.ont = ontology or DEFAULT_ONTOLOGY
        self.allow_generic = allow_generic

    def _bind(self, vehicle: str) -> FrameSpec:
        """把喻体词绑定到最合适的框架；绑不上返回 GENERIC 合成框架。"""
        # 1) 喻体词命中某框架的触发词/喻底 → 复用该框架（类型护栏生效）
        for fid, f in self.ont.frames.items():
            if vehicle in f.triggers or vehicle in f.ground:
                return f
        # 2) 喻体词落在某 USAS 语义域 → 桥接到对应框架
        field_name = semfield.tag_token(vehicle)
        if field_name:
            fid = semfield.FIELD_TO_FRAME.get(field_name)
            f = self.ont.get_frame(fid)
            if f:
                return f
        # 3) 全新喻体 → GENERIC 通道（类型护栏放行，交由阈值 + LLM 信任把关）
        return FrameSpec(
            id=f"F_LLM_{abs(hash(vehicle)) % 10 ** 8:08d}",
            name=f"LLM::{vehicle}",
            mapping_type="GENERIC_VEHICLE_MAP",
            source_domain=vehicle,
            target_domain="（待 LLM 补全）",
            ground=[],
            triggers=[vehicle],
            source_type="GENERIC_VEHICLE",
        )

    def _equative_vehicles(self, chunk: str) -> List[tuple]:
        """在等比标记后提取喻体名词（jieba 词性标注），返回 [(喻体, 词性), ...]。

        缺 jieba 时返回 []（优雅降级，不抛异常）。
        """
        try:
            import jieba.posseg as pseg
        except ImportError:
            logger.warning("LocalHeuristicBackend 需要 jieba 才能识别喻体，返回空结果。"
                           "（安装 jieba，或改用 OpenAIBackend）")
            return []
        from . import mipvu  # 复用 MIPVU 通道的等比标记词表，保持一致

        toks = list(pseg.cut(chunk))
        vehicles: List[str] = []
        for i, tok in enumerate(toks):
            if tok.word not in mipvu.MARKERS:
                continue
            nouns: List[tuple] = []
            saw_de = False
            for j in range(i + 1, min(i + 7, len(toks))):
                w, f = toks[j].word, toks[j].flag
                if (not w) or all(ch in _PUNCT for ch in w) or w in mipvu.MARKERS:
                    break
                if w in _SKIP_WORDS or f.startswith("u"):
                    saw_de = saw_de or w == "的" or f.startswith("u")
                    continue
                if f.startswith(_FUNC_FLAGS):
                    continue
                # n*:名词（含 nr 人名/喻体如"老黄牛"）；i/l:成语与习用语
                # —— 中文隐喻喻体大量是成语（顶梁柱/摇钱树），必须一并接纳
                if (f.startswith("n") or f.startswith("i") or f.startswith("l")) \
                        and len(w) >= 2:
                    nouns.append((w, saw_de, f))
                    saw_de = False
                else:
                    break  # 既非名词也非虚词 → 保守停止（"是我最好的朋友"）
            if nouns:
                after_de = [item for item in nouns if item[1]]
                picked = after_de[-1] if after_de else nouns[0]
                vehicles.append((picked[0], picked[2]))  # (喻体, 词性)
        return vehicles

    def _within_domain_literal(self, vehicle: str, chunk: str) -> bool:
        """域内字面护栏（Wmatrix keyness，与 mipvu 一致）：
        喻体所属语义域即语篇主导域、且同域词出现 ≥2 次 → 喻体落在源域内，非跨域映射。
        """
        f = semfield.tag_token(vehicle)
        if not f or f != semfield.discourse_field(chunk):
            return False
        n = sum(1 for w in semfield.segment(chunk) if semfield.tag_token(w) == f)
        return n >= 2

    def discover(self, chunk: str) -> List[LLMCandidate]:
        out: List[LLMCandidate] = []
        for vehicle, flag in self._equative_vehicles(chunk):
            frame = self._bind(vehicle)
            # 字面干扰词（苹果/水/火/路）只有在已绑定到具体概念框架时才保留
            if vehicle in ("苹果", "水", "火", "路") and \
               frame.source_type == "GENERIC_VEHICLE":
                continue
            # 域内字面：「这是戏剧舞台上的表演」→ 舞台仍在 THEATRE 域内，非隐喻
            if self._within_domain_literal(vehicle, chunk):
                continue
            if frame.source_type == "GENERIC_VEHICLE":
                # 专有名词作等比谓语几乎都是身份判断（"苏利曼是苏丹"），非跨域映射
                if flag.startswith(_PROPER_NOUN_FLAGS):
                    continue
                # 绑不上的新喻体：默认交给真实 LLM（详见类注释中的实测说明）
                if not self.allow_generic:
                    continue
            out.append(LLMCandidate(
                source_domain=frame.source_domain,
                target_domain=frame.target_domain,
                ground=list(frame.ground),
                triggers=[vehicle],
                confidence=0.5,
            ))
        return out

    def refine(self, chunk: str, frame: FrameSpec) -> Optional[LLMRefine]:
        # 离线近似：已知框架（非 GENERIC）直接采信；GENERIC 仅当喻体字面临近等比标记才采信
        if frame.source_type != "GENERIC_VEHICLE":
            return LLMRefine(is_metaphor=True, confidence=0.6,
                             ground=list(frame.ground))
        return LLMRefine(is_metaphor=True, confidence=0.5, ground=[])

    def cluster(self, edges) -> Optional[dict]:
        return None


# ----------------------------------------------------------------------------
# 3) MockBackend —— 单测用
# ----------------------------------------------------------------------------
class PrecomputedBackend:
    """把「批量预取」的 LLM 结果当作后端喂给抽取器。

    用途：先用 `precompute_all()` 把整批语料的 discover + refine 一次性问完
    （摊薄样板开销、合并请求），再让抽取器逐句消费缓存结果 ——
    抽取器接口不用改，成本/延迟却降一个量级。

        backend = OpenAIBackend(...)                       # 真实端点
        pre     = precompute_all(backend, texts, ontology) # 两趟预取（可落盘缓存）
        ex      = MetaphorExtractor(llm_backend=pre)
    """

    def __init__(self, table: Dict[str, List[LLMCandidate]],
                 fallback: Optional["MetaphorLLMBackend"] = None,
                 refine_table: Optional[Dict[tuple, LLMRefine]] = None):
        self.table = table
        self.fallback = fallback
        self.refine_table = refine_table

    def discover(self, chunk: str) -> List[LLMCandidate]:
        return self.table.get(chunk, [])

    def refine(self, chunk: str, frame: FrameSpec) -> Optional[LLMRefine]:
        if self.refine_table is not None:
            r = self.refine_table.get(_refine_key(chunk, frame))
            if r is not None:
                return r
            # 表里查到但记为"非隐喻"的，用哨兵区分于"没查到"
            if _refine_key(chunk, frame) in self.refine_table:
                return None
        if self.fallback is not None:
            return self.fallback.refine(chunk, frame)
        return LLMRefine(is_metaphor=True, confidence=0.6,
                         ground=list(frame.ground))

    def cluster(self, edges) -> Optional[dict]:
        return self.fallback.cluster(edges) if self.fallback else None


def _refine_key(chunk: str, frame: FrameSpec) -> tuple:
    return (chunk, frame.source_domain, frame.target_domain)


class _RefineCollector:
    """第一趟：只记录抽取器会发出哪些 refine 请求，不真调 LLM。"""

    def __init__(self, discover_table: Dict[str, List[LLMCandidate]]):
        self.table = discover_table
        self.pairs: List[tuple] = []

    def discover(self, chunk: str) -> List[LLMCandidate]:
        return self.table.get(chunk, [])

    def refine(self, chunk: str, frame: FrameSpec) -> Optional[LLMRefine]:
        self.pairs.append(_refine_key(chunk, frame))
        return None  # 第一趟不产出，只为收集

    def cluster(self, edges) -> Optional[dict]:
        return None


def batch_refine(backend, pairs: List[tuple], batch_size: int = 20,
                 verbose: bool = True,
                 cache_path: Optional[str] = None) -> Dict[tuple, "LLMRefine"]:
    """批量判断 (文本,源域,目标域) 是否为真隐喻，返回 {key: LLMRefine 或 None}。

    值为 None 表示"模型判为非隐喻"（与"没查到"区分开，靠 key 是否存在）。
    """
    pairs = list(dict.fromkeys(pairs))
    table: Dict[tuple, Optional[LLMRefine]] = {}

    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for k, v in raw:
            table[tuple(k)] = LLMRefine(**v) if v else None
        missing = [p for p in pairs if p not in table]
        if not missing:
            if verbose:
                print(f"    命中 refine 缓存 {cache_path}（{len(table)} 条，0 次请求）")
            return table
        if verbose:
            print(f"    refine 缓存部分命中，补取 {len(missing)} 条…")
    else:
        missing = pairs

    supports = hasattr(backend, "refine_batch")
    size = batch_size if supports else 1
    total = -(-len(missing) // size)
    for bi in range(0, len(missing), size):
        part = missing[bi:bi + size]
        rows = (backend.refine_batch(part) if supports
                else [backend.refine(c, s, t) for (c, s, t) in part])
        for p, r in zip(part, rows):
            table[p] = r
        if verbose:
            print(f"    refine 批量: {min(bi + size, len(missing))}/{len(missing)}"
                  f"（第 {bi // size + 1}/{total} 批）", flush=True)

    if cache_path:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump([[list(k), (dataclasses.asdict(v) if v else None)]
                       for k, v in table.items()],
                      f, ensure_ascii=False)
        if verbose:
            print(f"    已缓存到 {cache_path}")
    return table


def precompute_all(backend, texts: List[str], ontology=None,
                   use_semfield: bool = False, batch_size: int = 20,
                   discover_cache: Optional[str] = None,
                   refine_cache: Optional[str] = None,
                   verbose: bool = True) -> "PrecomputedBackend":
    """两趟预取，一次拿齐 discover 与 refine 的全部结果。

    第一趟：批量 discover（可缓存）。
    1.5 趟：用收集器跑一遍抽取器，记录会发出哪些 refine 请求。
    第二趟：批量 refine（可缓存）。

    返回 PrecomputedBackend，抽取器消费时零网络请求。
    """
    from .extractor import MetaphorExtractor

    dtable = batch_discover(backend, texts, batch_size, verbose, discover_cache)

    collector = _RefineCollector(dtable)
    ex = MetaphorExtractor(ontology=ontology, use_semfield=use_semfield,
                           llm_backend=collector)
    for t in texts:
        ex.extract(t, doc_id="precompute", chunk_id="pre")
    if verbose:
        print(f"    收集到 {len(set(collector.pairs))} 条待细化候选", flush=True)

    rtable = batch_refine(backend, list(dict.fromkeys(collector.pairs)),
                          batch_size, verbose, refine_cache)
    return PrecomputedBackend(dtable, backend, rtable)


def save_table(table: Dict[str, List[LLMCandidate]], path: str):
    """把预取结果落盘，便于复现实验与离线迭代（避免重复付费）。"""
    import dataclasses
    payload = {k: [dataclasses.asdict(c) for c in v] for k, v in table.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


def load_table(path: str) -> Dict[str, List[LLMCandidate]]:
    """读回落盘结果（与 save_table 配对）。"""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return {k: [LLMCandidate(**c) for c in v] for k, v in payload.items()}


# ----------------------------------------------------------------------------
# L1.5 扩展链语义校验（延续性判据的语义级方案，README §7.3）
# ----------------------------------------------------------------------------
_VERIFY_SYSTEM = (
    "你是认知语言学标注专家（MIPVU 严格口径）。给你同一篇文档中的若干相邻段落，"
    "以及系统合并出的一条「扩展隐喻链」（源域→目标域、喻底）。判断这些段落是否"
    "构成**连贯的扩展隐喻**：同一源域的隐喻表达跨越段落持续出现并共同建构一个"
    "目标概念。注意：① 固化成语/惯用语（如\"基础上\"\"聚焦\"）不算隐喻提及；"
    "② 仅标题出现、正文无延续的不算；③ 单段孤立隐喻不算。"
)
_VERIFY_USER = (
    "共 {n} 条候选链：\n{body}\n"
    "只输出 JSON 数组：[{{\"i\": 0, \"verdict\": 1 或 0}}, ...]，i 与输入对应，"
    "不要输出其它文字。"
)


def verify_chains_batch(backend, chains: List[dict], batch_size: int = 8,
                        verbose: bool = True,
                        cache_path: Optional[str] = None) -> Dict[str, bool]:
    """批量 LLM 校验扩展隐喻链，返回 {chain_key: bool}。

    chains 元素：{"key": str, "doc_title": str, "source": str, "target": str,
                  "ground": List[str], "texts": List[str]}（texts 为链上各 chunk 原文）。
    key 必须确定性（如 doc_id|source|ground），供跨脚本重放与下游过滤。

    失败纪律：整批解析失败重试一次，仍失败则该批链**不写入缓存**并在
    返回值中缺失 —— 调用方必须把「缺失」当未校验处理，不得当作通过。
    """
    cache: Dict[str, bool] = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = {k: bool(v) for k, v in json.load(f).items()}
    todo = [c for c in chains if c["key"] not in cache]
    if cache_path and todo and verbose:
        print(f"    链校验待验 {len(todo)}/{len(chains)} 条（缓存 {len(cache)}）",
              flush=True)
    supports = hasattr(backend, "discover_batch")   # 批量 JSON 能力同源
    size = batch_size if supports else 1
    for bi in range(0, len(todo), size):
        part = todo[bi:bi + size]
        rows = []
        for i, c in enumerate(part):
            paras = "\n".join(f"[段{i_+1}] {t[:150]}"
                              for i_, t in enumerate(c["texts"]))
            rows.append(json.dumps({
                "i": i, "source": c["source"], "target": c["target"],
                "ground": "、".join(c["ground"][:4]),
                "title": c["doc_title"][:20], "paras": paras},
                ensure_ascii=False))
        user = _VERIFY_USER.format(n=len(part), body="\n".join(rows))
        parsed = None
        for _ in range(2):     # 整批解析失败重试一次
            out = backend._chat(_VERIFY_SYSTEM, user)
            if isinstance(out, list) and out:
                parsed = out
                break
        if not parsed:
            if verbose:
                print(f"    [链校验批次失败] 第 {bi // size + 1} 批（{len(part)} 条不写入缓存）",
                      flush=True)
            continue
        got = 0
        for item in parsed:
            try:
                i = int(item.get("i"))
                key = part[i]["key"]
            except (TypeError, ValueError, IndexError):
                continue
            cache[key] = bool(int(item.get("verdict", 0)))
            got += 1
        if verbose:
            print(f"    链校验批次 {bi // size + 1}: +{got}/{len(part)}"
                  f"（累计 {len(cache)}）", flush=True)
        if cache_path:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
    return cache


def batch_discover(backend, texts: List[str], batch_size: int = 20,
                   verbose: bool = True,
                   cache_path: Optional[str] = None) -> Dict[str, List[LLMCandidate]]:
    """对整批文本按批调用 discover_batch，返回 {原文: [候选]}。

    后端不支持 discover_batch 时，自动退化为逐句调用 discover（结果一致，只是更贵/更慢）。

    cache_path：落盘缓存。**强烈建议开启** —— 调阈值、改本体、跑消融都要反复重跑，
    缓存后迭代零成本且实验可复现；命中缓存时不发出任何请求。
    """
    texts = list(dict.fromkeys(texts))  # 去重，保序

    if cache_path and os.path.exists(cache_path):
        cached = load_table(cache_path)
        missing = [t for t in texts if t not in cached]
        if not missing:
            if verbose:
                print(f"    命中 LLM 缓存 {cache_path}（{len(cached)} 句，0 次请求）")
            return {t: cached[t] for t in texts}
        if verbose:
            print(f"    缓存部分命中，补取 {len(missing)} 句…")
        cached.update(_batch_discover_uncached(backend, missing, batch_size, verbose,
                                               checkpoint_path=cache_path))
        save_table(cached, cache_path)
        return {t: cached[t] for t in texts}

    table = _batch_discover_uncached(backend, texts, batch_size, verbose,
                                     checkpoint_path=cache_path)
    if cache_path:
        save_table(table, cache_path)
        if verbose:
            print(f"    已缓存到 {cache_path}")
    return table


def _batch_discover_uncached(backend, texts: List[str], batch_size: int,
                             verbose: bool,
                             checkpoint_path: Optional[str] = None,
                             checkpoint_every: int = 10
                             ) -> Dict[str, List[LLMCandidate]]:
    table: Dict[str, List[LLMCandidate]] = {}
    supports_batch = hasattr(backend, "discover_batch")
    size = batch_size if supports_batch else 1
    total = -(-len(texts) // size)
    for bi in range(0, len(texts), size):
        # 长任务（如 4075 句训练集挖掘，约 45 分钟）必须断点续跑：
        # 只在最后落盘的话，中途挂掉就前功尽弃。
        if checkpoint_path and bi and (bi // size) % checkpoint_every == 0:
            save_table(table, checkpoint_path)
            if verbose:
                print(f"      检查点：已存 {len(table)} 句 → {checkpoint_path}",
                      flush=True)
        part = texts[bi:bi + size]
        if supports_batch:
            rows = backend.discover_batch(part)
            # 整批全空 = 高度可疑（喂的是隐喻句，20 句一个候选都没有几乎不可能），
            # 通常是超时/截断被优雅降级吞掉了。不重试就是**静默数据丢失**。
            if rows and all(not r for r in rows) and len(part) > 1:
                rows = backend.discover_batch(part)        # 重试一次（网络抖动）
                if all(not r for r in rows):
                    mid = len(part) // 2                   # 仍空：拆半，规避单批过大
                    rows = (backend.discover_batch(part[:mid])
                            + backend.discover_batch(part[mid:]))
                    if verbose:
                        print(f"      第 {bi // size + 1} 批整批为空，已重试并拆半",
                              flush=True)
        else:
            rows = [backend.discover(t) for t in part]
        for t, cands in zip(part, rows):
            table[t] = cands
        if verbose:
            done = min(bi + size, len(texts))
            print(f"    LLM 批量发现: {done}/{len(texts)} 句"
                  f"（第 {bi // size + 1}/{total} 批）", flush=True)
    return table


class MockBackend:
    """返回预置结果，便于单元测试验证抽取器与后端的接线。"""

    def __init__(self, discover_candidates: Optional[List[LLMCandidate]] = None,
                 refine_result: Optional[LLMRefine] = None):
        self._discover = discover_candidates or []
        self._refine = refine_result  # None / LLMRefine / callable(chunk, frame)->LLMRefine|None

    def discover(self, chunk: str) -> List[LLMCandidate]:
        return list(self._discover)

    def refine(self, chunk: str, frame: FrameSpec) -> Optional[LLMRefine]:
        if callable(self._refine):
            return self._refine(chunk, frame)
        return self._refine

    def cluster(self, edges) -> Optional[dict]:
        return None
