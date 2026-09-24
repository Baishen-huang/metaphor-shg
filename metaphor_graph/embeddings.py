"""文本向量化：零依赖哈希编码器（默认） + 可插拔真实句向量（§6.2 / 路线图 P0）。

**默认编码器**：char n-gram + 哈希桶的确定性编码，仅为让原型「可运行、可比较」，
不依赖任何外部模型。生产环境通过 `set_embedder()` 注入真实句向量（bge-zh /
text-embedding 等）——全链路（hgnn / retrieval / training / metagraph / semfield）
的语义信号都会随之切换，无需改任何调用方代码。

**OpenAICompatibleEmbedder**：OpenAI 兼容 `/embeddings` 端点的标准库 urllib 直连
（零额外依赖），带磁盘缓存与批量接口。与 `llm_backend` 同一套静默失败纪律：
**401/402/403 抛 EmbedderFatalError（绝不降级）**，网络/解析失败抛 EmbedderError
由调用方决定降级策略 —— 本模块不替调用方做"安静地退回哈希向量"的决定
（README §7.2：静默降级曾产出看似正常实则全错的结果）。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional

DIM = 512

# ---------------------------------------------------------------------------
# 全局可插拔 embedder（§6.2：一处注入，全链路生效）
# ---------------------------------------------------------------------------
_EMBEDDER: Optional[Callable[[str], List[float]]] = None


def set_embedder(fn: Optional[Callable[[str], List[float]]],
                 propagate: bool = True) -> None:
    """注入真实句向量器 fn(text)->List[float]；传 None 恢复默认哈希编码。

    propagate=True（默认）把 semfield 的独立 embedder 槽位一并设置（语义失谐
    通道与本模块共享同一句向量源）。**检索层实验请传 propagate=False**：
    semfield 会改变抽取候选（incongruity_score 换语义相似度），冻结抽取管线
    才能把"句向量增益"隔离在检索/排序层（缓存重放对照的前提）。
    """
    global _EMBEDDER
    _EMBEDDER = fn
    if not propagate:
        return
    try:  # 懒加载避免环导入；semfield 不反向依赖本模块
        from . import semfield
        semfield.set_embedder(fn)
    except ImportError:
        pass


def embedder_from_env() -> Optional["OpenAICompatibleEmbedder"]:
    """从环境变量构造真实句向量器（未设 EMBED_API_KEY 时返回 None）。

    环境变量：
      EMBED_API_KEY    必需（智谱 / OpenAI 等支持 embeddings 的厂商）
      EMBED_BASE_URL   默认智谱 https://open.bigmodel.cn/api/paas/v4
      EMBED_MODEL      默认 embedding-3
      EMBED_DIMENSIONS 默认 512（须与 embeddings.DIM 一致，HGNN 矩阵依赖它）
      EMBED_CACHE      默认 <项目>/data/embed_cache.json（重跑零请求）
    """
    api_key = os.environ.get("EMBED_API_KEY", "")
    if not api_key:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return OpenAICompatibleEmbedder(
        api_key=api_key,
        base_url=os.environ.get("EMBED_BASE_URL",
                                "https://open.bigmodel.cn/api/paas/v4"),
        model=os.environ.get("EMBED_MODEL", "embedding-3"),
        dimensions=int(os.environ.get("EMBED_DIMENSIONS", "512")),
        cache_path=os.environ.get("EMBED_CACHE",
                                  os.path.join(root, "data", "embed_cache.json")))


def get_embedder() -> Optional[Callable[[str], List[float]]]:
    return _EMBEDDER


class EmbedderFatalError(RuntimeError):
    """认证/计费类致命错误（401/402/403）。重试无用，必须响亮报错。"""


class EmbedderError(RuntimeError):
    """网络/超时/解析等一般性错误。是否降级由调用方决定。"""


# ---------------------------------------------------------------------------
# 默认：零依赖哈希编码器
# ---------------------------------------------------------------------------
def _char_ngrams(text: str, n: int = 2) -> List[str]:
    text = "".join(ch for ch in text if not ch.isspace())
    if len(text) == 0:
        return []
    if len(text) < n:
        return [text]
    return [text[i:i + n] for i in range(len(text) - n + 1)]


def _hash_bucket(token: str, dim: int = DIM) -> int:
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim


def embed(text: str, dim: int = DIM) -> List[float]:
    """返回 dim 维 L2 归一化向量。

    注入了真实 embedder 时走它（返回维度以注入方为准，通常 ≠ dim）；
    否则退回默认哈希编码。**注入的 embedder 抛出的异常原样上抛**——
    是否降级是调用方的决定，本模块不做静默回退（§7.2 纪律）。
    """
    if _EMBEDDER is not None:
        return list(_EMBEDDER(text))
    vec = [0.0] * dim
    grams = set(_char_ngrams(text, 1) + _char_ngrams(text, 2))
    if not grams:
        return vec
    for g in grams:
        vec[_hash_bucket(g, dim)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# 迭代版零依赖向量器（§7.5 改写查询基准首次给了 sem 特征可被度量的场合）
# ---------------------------------------------------------------------------
class NgramEmbedder:
    """改进哈希编码器：**1–3 gram + 符号哈希**（feature hashing, Weinberger et al.）。

    与默认 `embed` 的差异：
      - 三阶字符 n-gram：词形变化/词缀（"推进不动"vs"寸步难行"无共享 n-gram，
        但"泥潭"vs"泥沼"共享「泥」+ 语感组合）覆盖更宽；
      - **符号哈希**：同一 n-gram 按 hash 高位定 ±1，降低哈希碰撞的系统性
        正偏置（无符号哈希下碰撞恒加正号，余弦被虚增）。

    为什么默认不换：全部已上报数字（P4-B 0.950 / 全量基准 0.998 等）都基于
    默认哈希编码器 —— 换默认必须重测全部数字。本类作为 opt-in 变体，
    在 §7.5 llmgold 基准上与默认对照，胜出后由调用方显式决策转正。
    """

    def __init__(self, dim: int = DIM, max_n: int = 3, signed: bool = True):
        self.dim = dim
        self.max_n = max_n
        self.signed = signed

    def _bucket_sign(self, gram: str):
        h = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16)
        sign = 1.0 if (h >> 63) & 1 or not self.signed else -1.0
        return h % self.dim, sign

    def __call__(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        grams: List[str] = []
        clean = "".join(ch for ch in text if not ch.isspace())
        for n in range(1, self.max_n + 1):
            grams.extend(_char_ngrams(clean, n))
        if not grams:
            return vec
        for g in grams:
            idx, sign = self._bucket_sign(g)
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


# ---------------------------------------------------------------------------
# OpenAI 兼容 embedding 后端（零额外依赖，磁盘缓存，批量）
# ---------------------------------------------------------------------------
class OpenAICompatibleEmbedder:
    """OpenAI 兼容 `/embeddings` 端点客户端。

    典型端点（base_url 填到前缀即可，本类自动拼 `/embeddings`）：
      - 智谱： https://open.bigmodel.cn/api/paas/v4   （embedding-3）
      - OpenAI: https://api.openai.com/v1             （text-embedding-3-small）
      - 本地 vLLM / Ollama 兼容端点

    用法（通常只需一行注入）：
        embeddings.set_embedder(OpenAICompatibleEmbedder(
            api_key="...", base_url="https://open.bigmodel.cn/api/paas/v4",
            model="embedding-3", cache_path="data/embed_cache.json"))

    - **磁盘缓存**：向量是确定性资产，缓存后重跑零请求（与 LLM 预取缓存同一纪律）。
    - **批量**：`embed_batch` 一次请求拿一批，摊薄请求开销；单条 `embed(text)`
      查缓存未命中时自动并入批处理路径。
    - **失败纪律**：401/402/403 → EmbedderFatalError（不降级、不重试）；
      其它 HTTP/网络/解析错误 → EmbedderError。是否回退哈希向量由调用方决定。
    """

    _FATAL_HTTP_CODES = {401: "API Key 无效或过期",
                         402: "账户余额不足/欠费，请充值",
                         403: "无该模型权限或地区受限"}

    def __init__(self, api_key: str = None, base_url: str = None,
                 model: str = None, cache_path: Optional[str] = None,
                 batch_size: int = 32, timeout: float = 60.0,
                 dimensions: Optional[int] = None):
        self.dimensions = dimensions   # embedding-3 等支持降维（如 512 对齐 DIM）
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.base_url = (base_url or os.environ.get("EMBED_BASE_URL",
                        os.environ.get("LLM_BASE_URL", ""))).rstrip("/")
        self.model = model or os.environ.get("EMBED_MODEL", "embedding-3")
        self.batch_size = max(1, batch_size)
        self.timeout = timeout
        self.cache_path = cache_path
        self._cache: Dict[str, List[float]] = {}
        self.input_tokens = 0            # 厂商返回的 usage 累积（精确核算用）
        self.n_requests = 0
        if cache_path and os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if payload.get("model") == self.model:
                self._cache = payload.get("vectors", {})

    # ---- 端点 ----
    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/embeddings"

    # ---- 单条 / 批量 ----
    def embed(self, text: str) -> List[float]:
        """单条向量：缓存命中直接返回；未命中走一次批量请求。"""
        if text in self._cache:
            return self._cache[text]
        return self.embed_batch([text])[0]

    __call__ = embed

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量向量：对未命中缓存的**去重**文本分批请求，回写缓存并落盘。"""
        out: Dict[int, List[float]] = {}
        missing: List[str] = []
        seen: set = set()
        for i, t in enumerate(texts):
            if t in self._cache:
                out[i] = self._cache[t]
            elif t not in seen:
                seen.add(t)
                missing.append(t)
        for i in range(0, len(missing), self.batch_size):
            part = missing[i:i + self.batch_size]
            got = self._request(part)
            for t, v in zip(part, got):
                self._cache[t] = v
        for i, t in enumerate(texts):   # 请求完统一回填（含重复文本）
            out[i] = self._cache[t]
        if self.cache_path and missing:
            self._save()
        return [out[i] for i in range(len(texts))]

    # ---- HTTP ----
    def _request(self, batch: List[str]) -> List[List[float]]:
        payload = {"model": self.model, "input": batch}
        if self.dimensions:
            payload["dimensions"] = self.dimensions
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            if e.code in self._FATAL_HTTP_CODES:
                raise EmbedderFatalError(
                    f"{e.code} {self._FATAL_HTTP_CODES[e.code]} — {detail}") from e
            raise EmbedderError(f"embeddings HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise EmbedderError(f"embeddings 网络错误: {e}") from e

        if not isinstance(payload, dict) or "data" not in payload:
            raise EmbedderError(f"embeddings 响应格式异常: {str(payload)[:200]}")
        usage = payload.get("usage") or {}
        self.input_tokens += int(usage.get("prompt_tokens",
                                           usage.get("input_tokens", 0)) or 0)
        self.n_requests += 1
        rows = sorted(payload["data"], key=lambda d: d.get("index", 0))
        vecs = [list(map(float, d["embedding"])) for d in rows]
        if len(vecs) != len(batch):
            raise EmbedderError(
                f"embeddings 返回 {len(vecs)} 条，请求 {len(batch)} 条（静默丢批防护）")
        return vecs

    def _save(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump({"model": self.model, "vectors": self._cache}, f,
                      ensure_ascii=False)

    def usage_report(self) -> str:
        return (f"embeddings 请求 {self.n_requests} 次，输入 {self.input_tokens} tok，"
                f"缓存 {len(self._cache)} 条")
