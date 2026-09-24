"""存储层（方案 §4.6）。

选型依据（§4.6）：Neo4j 是属性图数据库，超图与属性图同构，总可以将超图
表示为属性图（更多的关系和节点），且超图在捕获「元意图」方面有特殊优势——
恰好对应 L2/L3 超顶点的「元」语义。

本模块提供：
  - 将 SHG 导出为**幂等**的 Neo4j Cypher（MERGE + 唯一性约束），可重复导入
  - 导出为 JSON（无 Neo4j 时也能验证）

幂等性是知识管理的硬要求：增量摄入必须能安全重放。旧实现全部使用 CREATE，
重复导入会产生重复节点，且 :Domain 端点节点从未被创建（MATCH 不到任何
Domain，导致关系全部建不出来）。本版修复这两点，并补齐 HAS_GROUND ——
喻底是超边多端点语义的来源，不落关系就无法在图里做「喻底交集」遍历。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import List

from .models import MetaphorSHG


# --------------------------------------------------------------------------- 工具
def _esc(value) -> str:
    """Cypher 字符串字面量转义（防止域/喻底里含引号导致语法错误）。"""
    s = "" if value is None else str(value)
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _jlist(values) -> str:
    return json.dumps(list(values or []), ensure_ascii=False)


# --------------------------------------------------------------------- 约束
def constraints_cypher() -> List[str]:
    """唯一性约束：MERGE 幂等写入的前提，也是增量摄入不产生重复节点的保证。"""
    return [
        "CREATE CONSTRAINT mapping_id IF NOT EXISTS "
        "FOR (m:MetaphorMapping) REQUIRE m.id IS UNIQUE;",
        "CREATE CONSTRAINT frame_id IF NOT EXISTS "
        "FOR (f:MetaphorFrame) REQUIRE f.id IS UNIQUE;",
        "CREATE CONSTRAINT cascade_id IF NOT EXISTS "
        "FOR (c:MetaphorCascade) REQUIRE c.id IS UNIQUE;",
        "CREATE CONSTRAINT domain_name IF NOT EXISTS "
        "FOR (d:Domain) REQUIRE d.name IS UNIQUE;",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS "
        "FOR (ch:Chunk) REQUIRE ch.id IS UNIQUE;",
        "CREATE INDEX mapping_layer IF NOT EXISTS "
        "FOR (m:MetaphorMapping) ON (m.layer);",
        "CREATE INDEX mapping_extended IF NOT EXISTS "
        "FOR (m:MetaphorMapping) ON (m.isExtended);",
    ]


def _ensure_domain(name: str) -> str:
    """MERGE 一个 :Domain 端点节点。旧实现缺这一步，是导出语句失效的根因。"""
    return f"MERGE (d:Domain {{name:'{_esc(name)}'}}) RETURN d;"


# ------------------------------------------------------------------ SHG → Cypher
def shg_to_cypher(shg: MetaphorSHG, with_constraints: bool = True) -> List[str]:
    """把四层隐喻超超图转成**幂等**的 Neo4j 属性图写入语句。

    结构沿用 neo4j_schema.cypher：一条 L1 超边 = 一个 :MetaphorMapping 节点，
    通过 HAS_SOURCE / HAS_TARGET / HAS_GROUND 连接多个端点，从而表达
    「n 元 / 喻底集合」的超边语义。全部写入改用 MERGE。
    """
    stmts: List[str] = []
    if with_constraints:
        stmts.extend(constraints_cypher())

    for e in shg.edges:
        ext = "true" if e.is_extended else "false"
        dep = "true" if e.deprecated else "false"
        # 端点节点必须先存在（源域 / 目标域 / 喻底集合）
        for name in [e.source_domain, e.target_domain] + list(e.ground):
            stmts.append(_ensure_domain(name))

        stmts.append(
            f"MERGE (m:MetaphorMapping {{id:'{_esc(e.id)}'}}) "
            f"SET m.layer={e.layer}, m.source='{_esc(e.source_domain)}', "
            f"m.target='{_esc(e.target_domain)}', "
            f"m.ground={_jlist(e.ground)}, "
            f"m.triggers={_jlist(e.triggers)}, "
            f"m.description='{_esc(e.describe())}', "
            f"m.confidence={float(e.confidence)}, m.isExtended={ext}, "
            f"m.deprecated={dep}, m.novelty='{_esc(e.novelty)}', "
            f"m.source_type='{_esc(e.source_type)}', "
            f"m.cascade_id='{_esc(e.cascade_id or '')}', "
            f"m.frame_id='{_esc(e.frame_id or '')}', "
            f"m.extractor_version='{_esc(e.extractor_version)}';")

        stmts.append(
            f"MATCH (m:MetaphorMapping {{id:'{_esc(e.id)}'}}), "
            f"(s:Domain {{name:'{_esc(e.source_domain)}'}}) "
            f"MERGE (m)-[:HAS_SOURCE]->(s);")
        stmts.append(
            f"MATCH (m:MetaphorMapping {{id:'{_esc(e.id)}'}}), "
            f"(t:Domain {{name:'{_esc(e.target_domain)}'}}) "
            f"MERGE (m)-[:HAS_TARGET]->(t);")

        # 喻底集合 = 超边多端点语义的来源，必须落关系才能图遍历
        for g in e.ground:
            stmts.append(
                f"MATCH (m:MetaphorMapping {{id:'{_esc(e.id)}'}}), "
                f"(g:Domain {{name:'{_esc(g)}'}}) "
                f"MERGE (m)-[:HAS_GROUND]->(g);")

        # 溯源证据链
        for v in e.evidence:
            stmts.append(
                f"MATCH (m:MetaphorMapping {{id:'{_esc(e.id)}'}}) "
                f"MERGE (v:Evidence {{chunk_id:'{_esc(v.chunk_id)}', "
                f"snippet:'{_esc(v.snippet)}'}}) "
                f"SET v.doc_id='{_esc(v.doc_id)}', v.authority={float(v.authority)}, "
                f"v.timestamp={float(v.timestamp)}, "
                f"v.extractor_version='{_esc(v.extractor_version)}' "
                f"MERGE (m)-[:SUPPORTED_BY]->(v);")

        # 跨 chunk 覆盖
        for s in e.chunk_spans:
            stmts.append(
                f"MERGE (ch:Chunk {{id:'{_esc(s.chunk_id)}'}}) "
                f"SET ch.doc_id='{_esc(s.doc_id)}';")
            stmts.append(
                f"MATCH (m:MetaphorMapping {{id:'{_esc(e.id)}'}}), "
                f"(ch:Chunk {{id:'{_esc(s.chunk_id)}'}}) "
                f"MERGE (m)-[:SPANS]->(ch);")

    for f in shg.frames:
        stmts.append(
            f"MERGE (f:MetaphorFrame {{id:'{_esc(f.id)}'}}) "
            f"SET f.name='{_esc(f.name)}', f.layer={f.layer}, "
            f"f.source_frame='{_esc(f.source_frame)}', "
            f"f.target_frame='{_esc(f.target_frame)}';")
        for mid in f.member_mapping_ids:
            stmts.append(
                f"MATCH (f:MetaphorFrame {{id:'{_esc(f.id)}'}}), "
                f"(m:MetaphorMapping {{id:'{_esc(mid)}'}}) "
                f"MERGE (m)-[:IN_FRAME]->(f);")

    for c in shg.cascades:
        stmts.append(
            f"MERGE (c:MetaphorCascade {{id:'{_esc(c.id)}'}}) "
            f"SET c.name='{_esc(c.name)}', c.layer={c.layer}, "
            f"c.discourse={_jlist(c.discourse_domains)}, "
            f"c.typical_triggers={_jlist(c.typical_triggers)};")
        for fid in c.member_frame_ids:
            stmts.append(
                f"MATCH (c:MetaphorCascade {{id:'{_esc(c.id)}'}}), "
                f"(f:MetaphorFrame {{id:'{_esc(fid)}'}}) "
                f"MERGE (f)-[:IN_CASCADE]->(c);")

    return stmts


def shg_to_json(shg: MetaphorSHG, path: str):
    payload = {
        "edges": [e.to_dict() for e in shg.edges],
        "frames": [f.to_dict() for f in shg.frames],
        "cascades": [c.to_dict() for c in shg.cascades],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Neo4j 运行期驱动（路线图 §8.2 P2：从 schema/导出升级为可查询存储）
# ---------------------------------------------------------------------------
class Neo4jFatalError(RuntimeError):
    """认证类致命错误（401/403）。与 llm_backend/embeddings 同一纪律：响亮报错。"""


class Neo4jError(RuntimeError):
    """Cypher 执行错误 / 网络 / 响应格式异常。"""


class Neo4jStore:
    """通过 Neo4j **HTTP 事务端点**读写四层隐喻图（标准库 urllib，零额外依赖）。

    为什么不用官方 python driver：本项目坚持「零额外依赖」（README §3），
    Neo4j 自 4.x 起提供稳定的 HTTP 事务端点 ``POST /db/{db}/tx/commit``，
    标准库即可直连 —— 与 `llm_backend.OpenAIBackend` / `embeddings.
    OpenAICompatibleEmbedder` 是同一模式。

    用法：
        store = Neo4jStore(uri="http://127.0.0.1:7474",
                           user="neo4j", password="...")
        store.load_shg(shg)                  # 幂等写入（复用 shg_to_cypher）
        rows = store.run("MATCH (m:MetaphorMapping) RETURN m.id LIMIT 10")

    失败纪律（§7.2 静默失败防护）：401/403 → Neo4jFatalError（不重试不降级）；
    事务返回的 errors 数组非空 → Neo4jError（带上 Neo4j 的 code 与 message）；
    是否回退 JSON 导出由调用方决定，本类不做静默回退。
    """

    def __init__(self, uri: str = "http://127.0.0.1:7474",
                 user: str = "neo4j", password: str = "",
                 database: str = "neo4j", batch_size: int = 200,
                 timeout: float = 60.0):
        self.uri = uri.rstrip("/")
        if "//" not in self.uri:
            self.uri = "http://" + self.uri
        self.user = user
        self.password = password
        self.database = database
        self.batch_size = max(1, batch_size)
        self.timeout = timeout

    # ---- HTTP ----
    def _endpoint(self) -> str:
        return f"{self.uri}/db/{self.database}/tx/commit"

    def execute(self, statements: List[tuple]) -> List[list]:
        """在一个事务里执行 [(cypher, params), ...]，返回每条语句的结果行。

        statements 为空是 no-op（返回 []），不浪费一次 HTTP 往返。
        """
        if not statements:
            return []
        import base64
        token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        payload = json.dumps({"statements": [
            {"statement": c, "parameters": (p or {})} for c, p in statements
        ]}).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint(), data=payload, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Basic {token}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status in (401, 403):
                    raise Neo4jFatalError(f"{resp.status} 认证失败（检查用户名/密码）")
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Neo4jFatalError(
                    f"{e.code} 认证失败（检查用户名/密码）") from e
            raise Neo4jError(f"Neo4j HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Neo4jError(f"Neo4j 连接失败: {e}") from e

        errors = data.get("errors") or []
        if errors:
            first = errors[0]
            raise Neo4jError(f"Neo4j {first.get('code')}: {first.get('message')}")
        return [r.get("data", []) for r in data.get("results", [])]

    def run(self, cypher: str, params: dict = None) -> list:
        """单条 Cypher 查询，返回结果行。"""
        return self.execute([(cypher, params)])[0]

    # ---- 写入 ----
    def load_shg(self, shg: MetaphorSHG, with_constraints: bool = True) -> int:
        """幂等写入四层图（分批事务），返回写入语句数。

        复用 shg_to_cypher 的超边实体化建模（HAS_SOURCE/HAS_TARGET/HAS_GROUND/
        SPANS/IN_FRAME/IN_CASCADE），只去掉行尾分号 —— 事务端点不接受分号结尾。

        **schema 与数据必须分事务**：Neo4j 禁止在同一显式事务里先做 schema
        修改再写数据（Neo.ClientError.Transaction.ForbiddenDueToTransactionType
        —— 真库联测抓出，mock 测不到）。约束/索引语句逐条先行，数据分批随后。
        """
        stmts = shg_to_cypher(shg, with_constraints=with_constraints)
        cleaned = [(s.rstrip().rstrip(";"), {}) for s in stmts]
        schema = [(c, p) for c, p in cleaned
                  if c.startswith(("CREATE CONSTRAINT", "CREATE INDEX"))]
        data = [(c, p) for c, p in cleaned
                if not c.startswith(("CREATE CONSTRAINT", "CREATE INDEX"))]
        for c, p in schema:                      # 每条约束独立事务（幂等）
            self.execute([(c, p)])
        n = len(schema)
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i + self.batch_size]
            self.execute(batch)
            n += len(batch)
        return n

    def clear(self):
        self.run("MATCH (n) DETACH DELETE n")

    def counts(self) -> dict:
        """各标签节点数（导入后的健全性检查）。"""
        rows = self.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n "
            "ORDER BY label")
        return {r["row"][0]: r["row"][1] for r in rows if r["row"][0]}
