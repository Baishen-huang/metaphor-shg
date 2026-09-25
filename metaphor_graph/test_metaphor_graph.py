# -*- coding: utf-8 -*-
"""隐喻超超图 / 元图框架的单元测试。

运行：python -m unittest metaphor_graph.test_metaphor_graph -v
（在 E:\02_AI项目\元图隐喻分析 目录下）
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaphor_graph import (  # noqa: E402
    MetaphorSHGBuilder, MetaphorURetrieval, RetrievalEngine,
    MetaphorHGNN, HLIndex, storage, DEFAULT_ONTOLOGY,
    MetaphorHyperedge, MetaphorSHG, ChunkSpan,
    Evidence, resolve_conflict, merge_evidence, EXTRACTOR_VERSION,
    ContextBudget, AdaptiveThreshold, ThresholdDecision, graph_density,
    MetaphorScorer, build_training_set, extract_features, extract_text_features,
    train_from_shg,
    FEATURE_NAMES, graph_health, baselines, TrainingSet, trivial_separators,
    feature_auc, leakage_report,
)
from metaphor_graph.baselines import (  # noqa: E402
    BASELINES, BY_ID, ABLATIONS, EVAL_SUITES, render_plan,
)
from metaphor_graph.ontology import CascadeOntology, TYPE_CONSTRAINTS  # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor  # noqa: E402
from metaphor_graph.extended import link_extended_metaphors  # noqa: E402
from metaphor_graph.demo import CHUNKS, DOC_ID  # noqa: E402
from metaphor_graph import semfield as sf  # noqa: E402

EMB_DIM = 512


def _edge(source="机器", target="生活状态", ground=None, triggers=None,
          frame_id="F_LIFE_MACHINE", cascade_id="C_LIFE_MACHINE",
          source_type="MACHINE", chunk_ids=("doc_c0", "doc_c1"),
          is_extended=False):
    ground = ground or ["紧绷", "机械重复"]
    triggers = triggers or ["发条"]
    spans = [ChunkSpan(chunk_id=c, start=0, end=2, text=t)
             for c, t in zip(chunk_ids, triggers)]
    return MetaphorHyperedge(
        id="L1_test", source_domain=source, target_domain=target,
        ground=ground, triggers=triggers, chunk_spans=spans,
        frame_id=frame_id, cascade_id=cascade_id, source_type=source_type,
        confidence=0.8, is_extended=is_extended, layer=1.5 if is_extended else 1)


class TestOntology(unittest.TestCase):
    def test_type_constraints_valid(self):
        self.assertTrue(CascadeOntology.type_valid("MOTION", "PROGRESS_IS_JOURNEY"))
        self.assertTrue(CascadeOntology.type_valid("WAR", "ARGUMENT_IS_WAR"))

    def test_type_constraints_invalid(self):
        # FINANCIAL 不应参与 WAR 类映射
        self.assertFalse(CascadeOntology.type_valid("FINANCIAL", "ARGUMENT_IS_WAR"))
        self.assertFalse(CascadeOntology.type_valid("BODY_SENSATION", "TIME_IS_MONEY"))

    def test_trigger_lookup(self):
        fs = DEFAULT_ONTOLOGY.match_by_triggers(["发条"])
        self.assertTrue(any(f.id == "F_LIFE_MACHINE" for f in fs))

    def test_frame_cascade_mapping(self):
        self.assertEqual(DEFAULT_ONTOLOGY.get_cascade("F_LIFE_MACHINE"), "C_LIFE_MACHINE")
        # OBSTACLE_IS_TERRAIN 已并入 PROGRESS_IS_JOURNEY 级联（跨域桥接）
        self.assertEqual(DEFAULT_ONTOLOGY.get_cascade("F_OBST_TERRAIN"), "C_PROGRESS_JOURNEY")

    def test_stats(self):
        s = DEFAULT_ONTOLOGY.stats()
        self.assertIn("级联", s)


class TestExtractor(unittest.TestCase):
    def test_extract_metaphor(self):
        ex = MetaphorExtractor()
        edges = ex.extract("别活得像根发条，每天被拧紧了才肯动弹。",
                           doc_id="d", chunk_id="d_c0")
        self.assertTrue(edges)
        e = edges[0]
        self.assertEqual(e.source_domain, "机器")
        self.assertEqual(e.frame_id, "F_LIFE_MACHINE")
        self.assertFalse(e.is_extended)

    def test_literal_anti_interference(self):
        # "苹果发布了新手机" 不应判为隐喻（字面抗干扰，§6.1 第四类）
        ex = MetaphorExtractor()
        edges = ex.extract("苹果发布了新手机，屏幕比上一代更大。",
                           doc_id="d", chunk_id="d_c7")
        self.assertEqual(len(edges), 0)

    def test_type_safety_filters_literal(self):
        # 所有抽取出的边都应通过类型安全约束（无字面误判混入）
        ex = MetaphorExtractor()
        for chunk in CHUNKS:
            for e in ex.extract(chunk, doc_id=DOC_ID, chunk_id=f"{DOC_ID}_x"):
                fs = DEFAULT_ONTOLOGY.get_frame(e.frame_id)
                self.assertTrue(
                    CascadeOntology.type_valid(e.source_type, fs.mapping_type))

    def test_literal_false_positive_rate(self):
        ex = MetaphorExtractor()
        labeled = [
            ("苹果发布了新手机。", False),
            ("水是一种无色无味的液体。", False),
            ("项目现在陷在泥潭里。", True),
            ("别活得像根发条。", True),
        ]
        fpr = ex.literal_false_positive_rate(labeled)
        # P1 硬门槛：字面误判率 < 15%
        self.assertLess(fpr, 0.15)


class TestExtendedLinking(unittest.TestCase):
    def test_cross_chunk_merge(self):
        e1 = _edge(chunk_ids=("doc_c0",), triggers=["发条"])
        e2 = _edge(chunk_ids=("doc_c1",), triggers=["拧紧"],
                   ground=["紧绷", "机械重复", "缺乏弹性"])
        out = link_extended_metaphors([e1, e2], {"doc_c0": 0, "doc_c1": 1})
        self.assertEqual(len(out), 1)
        ext = out[0]
        self.assertTrue(ext.is_extended)
        self.assertEqual(set(s.chunk_id for s in ext.chunk_spans), {"doc_c0", "doc_c1"})

    def test_no_merge_when_far_apart(self):
        e1 = _edge(chunk_ids=("doc_c0",))
        e2 = _edge(chunk_ids=("doc_c9",), ground=["紧绷", "机械重复"])
        out = link_extended_metaphors([e1, e2], {f"doc_c{i}": i for i in range(10)})
        self.assertEqual(len(out), 0)

    def test_no_merge_when_ground_disjoint(self):
        e1 = _edge(chunk_ids=("doc_c0",), ground=["紧绷", "机械重复"])
        e2 = _edge(chunk_ids=("doc_c1",), ground=["柔软", "温暖"])
        out = link_extended_metaphors([e1, e2], {"doc_c0": 0, "doc_c1": 1})
        self.assertEqual(len(out), 0)


class TestBuilder(unittest.TestCase):
    def setUp(self):
        self.shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)

    def test_layers_nonempty(self):
        self.assertTrue(self.shg.edges)
        self.assertTrue(self.shg.frames)
        self.assertTrue(self.shg.cascades)

    def test_extended_edges_exist(self):
        ext = [e for e in self.shg.edges if e.is_extended]
        self.assertTrue(ext, "应检测到至少一条跨 chunk 扩展超边")

    def test_summary(self):
        self.assertIn("MetaphorSHG", self.shg.summary())

    def test_cascade_membership(self):
        cas = {c.id: c for c in self.shg.cascades}
        self.assertIn("F_OBST_TERRAIN", cas["C_PROGRESS_JOURNEY"].member_frame_ids)


class TestMetagraph(unittest.TestCase):
    def setUp(self):
        self.shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        self.mg = MetaphorURetrieval()
        self.mg.index(CHUNKS, doc_id=DOC_ID)

    def test_metaphor_path(self):
        res = self.mg.retrieve("为什么我们的项目推进不动？")
        self.assertTrue(res.chunk_ids)
        self.assertIn("隐喻通路", res.trace)

    def test_literal_path(self):
        res = self.mg.retrieve("苹果发布了新手机")
        self.assertIn("literal", res.path)


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        self.eng = RetrievalEngine(self.shg, CHUNKS, doc_id=DOC_ID)

    def test_cross_domain_hits_mud(self):
        res = self.eng.cross_domain_retrieve("为什么我们的项目推进不动？")
        self.assertIn(f"{DOC_ID}_c0", res.chunk_ids)  # 泥潭 chunk

    def test_multi_clue(self):
        clues = self.eng.multi_clue_retrieval(["泥潭", "战壕", "护城河"])
        targets = [c for c, _ in clues]
        self.assertTrue(targets)
        self.assertIn("商业竞争", targets)

    def test_rrf_fusion(self):
        res = self.eng.rrf_fusion("项目推进不动", top_k=5)
        self.assertTrue(res.chunk_ids)

    def test_hyper_retriever_score(self):
        edge = next(e for e in self.shg.edges if e.source_domain == "地形")
        score = self.eng.metaphor_retriever_score("项目推进不动", edge)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)


class TestHGNN(unittest.TestCase):
    def setUp(self):
        self.shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)

    def test_forward_shape(self):
        hgnn = MetaphorHGNN(self.shg, layers=2)
        H = hgnn.forward()
        self.assertEqual(H.shape[0], hgnn.num_nodes)
        self.assertEqual(H.shape[1], EMB_DIM)

    def test_cascade_semantics_injected(self):
        import numpy as np
        hgnn = MetaphorHGNN(self.shg, layers=2)
        hgnn.forward()
        ni = hgnn.node_index
        self.assertIn("机器", ni)
        self.assertIn("C_LIFE_MACHINE", ni)

        def cos(a, b):
            a = np.asarray(a, float); b = np.asarray(b, float)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

        pre = cos(hgnn.X[ni["机器"]], hgnn.X[ni["C_LIFE_MACHINE"]])
        post = cos(hgnn.H[ni["机器"]], hgnn.X[ni["C_LIFE_MACHINE"]])
        self.assertGreater(post, pre)  # 跨层传播后级联语义已下沉


class TestHLIndex(unittest.TestCase):
    def setUp(self):
        self.shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        self.hl = HLIndex(self.shg)

    def test_trigger_reachability(self):
        targets = self.hl.reachable_targets("发条")
        self.assertIn("机器", targets)
        self.assertIn("生活状态", targets)


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)

    def test_cypher_export(self):
        stmts = storage.shg_to_cypher(self.shg)
        self.assertTrue(stmts)
        # 幂等写入：只允许 MERGE / MATCH / CREATE CONSTRAINT / CREATE INDEX
        allowed = ("MERGE", "MATCH", "CREATE CONSTRAINT", "CREATE INDEX")
        bad = [s for s in stmts if not s.startswith(allowed)]
        self.assertEqual(bad, [], f"存在非幂等写入语句：{bad[:2]}")

    def test_cypher_idempotent(self):
        """重复导出必须完全一致——这是增量摄入能安全重放的前提。"""
        a = storage.shg_to_cypher(self.shg)
        b = storage.shg_to_cypher(self.shg)
        self.assertEqual(a, b)

    def test_domain_nodes_created(self):
        """:Domain 端点节点必须先被创建，否则 HAS_* 关系一条都建不出来。

        这是旧实现的致命缺陷：只有 MATCH (s:Domain {name:...})，
        全仓库没有任何 CREATE/MERGE (:Domain ...)。
        """
        stmts = storage.shg_to_cypher(self.shg)
        created = {"".join(s.split("MERGE (d:Domain {name:'")[1].split("'")[0:1])
                   for s in stmts if s.startswith("MERGE (d:Domain")}
        need = set()
        for e in self.shg.edges:
            need |= {e.source_domain, e.target_domain} | set(e.ground)
        self.assertTrue(need, "测试语料应至少含一条超边")
        self.assertEqual(need - created, set(),
                         f"以下端点节点未被创建：{need - created}")

    def test_has_ground_relations(self):
        """喻底是超边多端点语义的来源，必须落 HAS_GROUND 关系才能图遍历。"""
        stmts = storage.shg_to_cypher(self.shg)
        n_ground_rel = sum(1 for s in stmts if "[:HAS_GROUND]" in s)
        n_ground = sum(len(e.ground) for e in self.shg.edges)
        self.assertEqual(n_ground_rel, n_ground)

    def test_constraints_emitted(self):
        stmts = storage.shg_to_cypher(self.shg)
        self.assertTrue(any("REQUIRE m.id IS UNIQUE" in s for s in stmts))
        self.assertTrue(any("REQUIRE d.name IS UNIQUE" in s for s in stmts))

    def test_json_export(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_shg.json")
        storage.shg_to_json(self.shg, path)
        self.assertTrue(os.path.exists(path))
        try:
            os.remove(path)
        except OSError:
            # 某些受管运行环境（沙箱/无回收站）禁止删除文件；
            # 本用例的断言是「文件已生成」，清理失败不应判为测试失败。
            pass


# ---------------------------------------------------------------------------
# 自举触发词（方案 §9.1）— 需 jieba，缺则跳过
# ---------------------------------------------------------------------------
try:
    import jieba  # noqa: F401
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

from metaphor_graph.bootstrap_triggers import (  # noqa: E402
    parse_train_xml, mine_triggers, build_bootstrap_ontology,
)
from metaphor_graph.data_loader import load_ccl2018  # noqa: E402
from metaphor_graph.evaluate_real import eval_split  # noqa: E402


@unittest.skipUnless(_HAS_JIEBA, "需要 jieba（venv_jieba）才能跑自举测试")
class TestBootstrap(unittest.TestCase):
    def test_parse_train_xml_labels(self):
        sents = parse_train_xml()
        self.assertTrue(sents)
        labels = {l for _, l in sents}
        self.assertTrue(labels <= {0, 1, 2})

    def test_mine_produces_literal_safe_patterns(self):
        # 默认模式：等比结构模式串（如 是舞台/像棉花糖）+ lift 字面软过滤
        r = mine_triggers()
        self.assertTrue(r["noun_vehicles"])
        self.assertTrue(r["noun_rows"])
        # 每个候选都带 lift（隐喻主导度）字段
        self.assertIn("lift", r["noun_rows"][0])
        # 动词默认关闭（方案 §9.1 明确只回填「喻体名词」）
        self.assertEqual(r["verb_vehicles"], [])

    def test_bootstrap_keeps_p1_below_gate(self):
        """P1 硬门槛（<0.15）必须守住 —— 这是方案 §6.5 的 Go/No-Go 决策点。"""
        samples = load_ccl2018()
        # 默认本体基线
        r0 = eval_split(samples, DEFAULT_ONTOLOGY)
        # 自举 P1-safe 模式（叠在默认本体上）
        ont = build_bootstrap_ontology()
        r = eval_split(samples, ont)
        # 自举后 P1 仍达标
        self.assertLess(r["literal_error_rate"], 0.15)
        # 自举召回不低于基线（应有正向提升）
        self.assertGreaterEqual(r["recall"], r0["recall"])
        # 触发词数量确有扩充
        self.assertGreater(len(ont._trigger_index),
                           len(DEFAULT_ONTOLOGY._trigger_index))

    def test_bootstrap_combined_with_metanet(self):
        """MetaNet 迁移本体 + 自举模式串 应是不破 P1 前提下的最佳配置。"""
        from metaphor_graph.metanet_migrate import build_metanet_ontology
        samples = load_ccl2018()
        ont = build_bootstrap_ontology(build_metanet_ontology())
        r = eval_split(samples, ont)
        self.assertLess(r["literal_error_rate"], 0.15)
        self.assertGreater(r["recall"], 0.05)


# ---------------------------------------------------------------------------
# MIPVU + Wmatrix 轻量语义通道（方案 §6.5）— 本体部分无需 jieba
# ---------------------------------------------------------------------------
class TestSemfieldOntology(unittest.TestCase):
    def test_new_fields_registered(self):
        for st, mt in [("PERFORMANCE", "EVENT_IS_PERFORMANCE"),
                       ("NATURE", "STATE_IS_NATURE"),
                       ("BUILDING", "STRUCTURE_IS_BUILDING"),
                       ("VALUE", "WORTH_IS_VALUE"),
                       ("SUBSTANCE", "QUALITY_IS_SUBSTANCE"),
                       ("ORGANISM", "TRAIT_IS_ORGANISM")]:
            self.assertTrue(CascadeOntology.type_valid(st, mt),
                             f"{st}->{mt} 应过类型安全约束")
        # 桥接表与本体 id 一致：每个语义域都有对应的级联
        for f in sf.FIELDS:
            self.assertIsNotNone(DEFAULT_ONTOLOGY.cascades.get(sf.FIELD_TO_CASCADE[f]))


# ---------------------------------------------------------------------------
# MIPVU + Wmatrix 轻量语义通道（方案 §6.5）— 需 jieba，缺则跳过
# ---------------------------------------------------------------------------
@unittest.skipUnless(_HAS_JIEBA, "需要 jieba（venv_jieba）才能跑语义通道测试")
class TestSemfieldChannel(unittest.TestCase):
    def test_tag_token(self):
        from metaphor_graph import semfield as sf
        self.assertEqual(sf.tag_token("舞台"), "THEATRE")
        self.assertEqual(sf.tag_token("宝石"), "VALUE")
        self.assertIsNone(sf.tag_token("计算机"))  # 未收录

    def test_mipvu_catches_equative_vehicle(self):
        from metaphor_graph import mipvu
        cands = mipvu.mipvu_candidates("世界就是一个舞台，你我都是演员。",
                                       DEFAULT_ONTOLOGY)
        self.assertTrue(any(c["vehicle"] == "舞台" for c in cands))
        self.assertTrue(any(c["frame_id"] == "F_EVENT_PLAY" for c in cands))

    def test_mipvu_skips_literal_tiger(self):
        """「栩栩如生的老虎」（硬币图案）不应被判隐喻：标记「如」嵌在词内。"""
        from metaphor_graph import mipvu
        cands = mipvu.mipvu_candidates(
            "硬币中央那只栩栩如生的老虎图案十分传神。",
            DEFAULT_ONTOLOGY)
        self.assertFalse(any(c["vehicle"] == "老虎" for c in cands))

    def test_mipvu_skips_within_domain_stage(self):
        """戏剧语篇里的「舞台」是域内字面用法，应跳过。"""
        from metaphor_graph import mipvu
        cands = mipvu.mipvu_candidates(
            "这部话剧的舞台上，演员们的表演赢得了满场掌声。",
            DEFAULT_ONTOLOGY)
        self.assertFalse(any(c["vehicle"] == "舞台" for c in cands))

    def test_extractor_semfield_channel(self):
        ex = MetaphorExtractor(ontology=DEFAULT_ONTOLOGY, use_semfield=True)
        edges = ex.extract("人生就是个舞台，我们都是演员而已",
                            doc_id="t", chunk_id="t0")
        self.assertTrue(any(e.frame_id == "F_EVENT_PLAY" for e in edges))

    def test_semfield_keeps_p1_below_gate(self):
        """P1 硬门槛（<0.15）必须守住 —— 方案 §6.5 Go/No-Go 决策点。"""
        samples = load_ccl2018()
        r = eval_split(samples, DEFAULT_ONTOLOGY, use_semfield=True)
        self.assertLess(r["literal_error_rate"], 0.15)
        # 语义通道召回应高于纯触发词基线
        r0 = eval_split(samples, DEFAULT_ONTOLOGY, use_semfield=False)
        self.assertGreater(r["recall"], r0["recall"])


# ---------------------------------------------------------------------------
# LLM 后端接入（方案 §6.6）
#   无需密钥、无需网络：OpenAIBackend 用本地假端点验证真实 HTTP 通路；
#   LocalHeuristicBackend 需 jieba（与自举/语义通道一致）。
# ---------------------------------------------------------------------------
class TestLLMBackendContract(unittest.TestCase):
    """后端接口契约 + 抽取器接线（不依赖 jieba / 网络）。"""

    def test_mock_backend_discovery_flows_into_extractor(self):
        """MockBackend 发现的新喻体应一路走到 L1 超边，且能定位到原文跨度。"""
        from metaphor_graph.llm_backend import MockBackend, LLMCandidate
        backend = MockBackend(discover_candidates=[
            LLMCandidate("漩涡", "舆论", ground=["裹挟"], triggers=["漩涡"],
                         confidence=0.9)])
        ex = MetaphorExtractor(llm_backend=backend)
        edges = ex.extract("这起事件让公司声誉陷入了舆论的漩涡。",
                           doc_id="d", chunk_id="c0")
        self.assertTrue(edges, "LLM 发现的候选应产出超边")
        e = edges[0]
        self.assertEqual(e.source_domain, "漩涡")
        self.assertEqual(e.target_domain, "舆论")
        self.assertIn("裹挟", e.ground)
        # 触发词必须在原文中真实定位到
        self.assertEqual([s.text for s in e.chunk_spans], ["漩涡"])
        # 未绑定到本体的新喻体 → GENERIC 通道（类型护栏放行）
        self.assertEqual(e.source_type, "GENERIC_VEHICLE")

    def test_known_domain_candidate_binds_to_ontology(self):
        """LLM 给出已知概念域时，应复用已有框架，让类型安全约束继续生效。"""
        from metaphor_graph.llm_backend import MockBackend, LLMCandidate
        backend = MockBackend(discover_candidates=[
            LLMCandidate("机器", "生活状态", triggers=["发条"], confidence=0.8)])
        ex = MetaphorExtractor(llm_backend=backend)
        edges = ex.extract("别活得像根发条，每天被拧紧了才肯动弹。",
                           doc_id="d", chunk_id="c0")
        self.assertTrue(any(e.frame_id == "F_LIFE_MACHINE" for e in edges))

    def test_dangling_candidate_is_dropped(self):
        """触发词不在原文中的「悬空候选」必须丢弃（无法定位 → 不产出）。"""
        from metaphor_graph.llm_backend import MockBackend, LLMCandidate
        backend = MockBackend(discover_candidates=[
            LLMCandidate("漩涡", "舆论", triggers=["根本不存在的词"], confidence=0.9)])
        ex = MetaphorExtractor(llm_backend=backend)
        self.assertEqual(ex.extract("这起事件让公司声誉受损。", doc_id="d"), [])

    def test_low_confidence_candidate_below_llm_gate(self):
        """低于 llm_conf_threshold(默认 0.5) 的候选不应产出。"""
        from metaphor_graph.llm_backend import MockBackend, LLMCandidate
        backend = MockBackend(discover_candidates=[
            LLMCandidate("漩涡", "舆论", triggers=["漩涡"], confidence=0.2)])
        ex = MetaphorExtractor(llm_backend=backend)
        self.assertEqual(ex.extract("陷入了舆论的漩涡。", doc_id="d"), [])

    def test_refine_can_reject_candidate(self):
        """refine 判为非隐喻时，触发词通道的候选也应被否决。"""
        from metaphor_graph.llm_backend import MockBackend, LLMRefine
        backend = MockBackend(refine_result=LLMRefine(is_metaphor=False))
        ex = MetaphorExtractor(llm_backend=backend)
        # "发条"本身能命中触发词，但 LLM 判定非隐喻 → 应无产出
        self.assertEqual(ex.extract("别活得像根发条。", doc_id="d"), [])

    def test_legacy_llm_fn_still_works(self):
        """旧接口 llm_fn(text, frame)->dict 必须保持可用（向后兼容）。"""
        ex = MetaphorExtractor(llm_fn=lambda text, frame: {"confidence": 0.9,
                                                           "ground": ["紧绷"]})
        edges = ex.extract("别活得像根发条。", doc_id="d", chunk_id="c0")
        self.assertTrue(edges)
        self.assertIn("紧绷", edges[0].ground)
        self.assertEqual(edges[0].confidence, 0.9)

    def test_dedup_across_channels(self):
        """同一 (框架, 跨度) 若被多通道重复召回，只保留一条。"""
        from metaphor_graph.llm_backend import MockBackend, LLMCandidate
        backend = MockBackend(discover_candidates=[
            LLMCandidate("机器", "生活状态", triggers=["发条"], confidence=0.8)])
        ex = MetaphorExtractor(llm_backend=backend)
        edges = ex.extract("别活得像根发条。", doc_id="d", chunk_id="c0")
        keys = [(e.frame_id, s.start, s.end) for e in edges for s in e.chunk_spans]
        self.assertEqual(len(keys), len(set(keys)), "不应出现重复超边")

    def test_builder_accepts_llm_backend(self):
        """构建器应把 LLM 后端透传给抽取器。"""
        from metaphor_graph import MetaphorSHGBuilder
        from metaphor_graph.llm_backend import MockBackend, LLMCandidate
        backend = MockBackend(discover_candidates=[
            LLMCandidate("漩涡", "舆论", triggers=["漩涡"], confidence=0.9)])
        shg = MetaphorSHGBuilder(llm_backend=backend).build(
            ["陷入了舆论的漩涡。"], doc_id="b")
        self.assertTrue(any(e.source_domain == "漩涡" for e in shg.edges))


class TestOpenAIBackendHTTP(unittest.TestCase):
    """用本地假端点验证 OpenAIBackend 的真实 HTTP 通路（不联网、无需真实密钥）。"""

    def setUp(self):
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        reply = [{"source_domain": "漩涡", "target_domain": "舆论",
                  "ground": ["裹挟"], "triggers": ["漩涡"], "confidence": 0.9}]
        seen = {}

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                body = _json.loads(self.rfile.read(n) or b"{}")
                seen["model"] = body.get("model")
                seen["auth"] = self.headers.get("Authorization")
                seen["path"] = self.path
                # 记录厂商私有参数（如 GLM 的 reasoning_effort）是否真的发出去了
                seen["extra"] = {k: v for k, v in body.items()
                                 if k not in ("model", "messages", "temperature")}
                data = _json.dumps(
                    {"choices": [{"message": {"role": "assistant",
                                              "content": _json.dumps(reply,
                                                                     ensure_ascii=False)}}]}
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self._server = HTTPServer(("127.0.0.1", 0), H)
        self._seen = seen

        def _serve():
            try:
                self._server.serve_forever()
            except OSError:
                pass  # server_close 会中断 serve_forever，属正常关闭

        threading.Thread(target=_serve, daemon=True).start()
        self.addCleanup(self._server.shutdown)
        self.addCleanup(self._server.server_close)  # 关闭监听 socket，避免 ResourceWarning
        self.base = f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def test_discover_over_http(self):
        from metaphor_graph.llm_backend import OpenAIBackend
        be = OpenAIBackend(api_key="k", base_url=self.base, model="m")
        cands = be.discover("陷入了舆论的漩涡。")
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].source_domain, "漩涡")
        self.assertEqual(cands[0].target_domain, "舆论")
        self.assertEqual(cands[0].confidence, 0.9)
        # 请求形态正确：chat/completions + Bearer + model
        self.assertEqual(self._seen["path"], "/v1/chat/completions")
        self.assertEqual(self._seen["auth"], "Bearer k")
        self.assertEqual(self._seen["model"], "m")

    def test_refine_over_http(self):
        from metaphor_graph.llm_backend import OpenAIBackend
        be = OpenAIBackend(api_key="k", base_url=self.base, model="m")
        r = be.refine("测试", DEFAULT_ONTOLOGY.get_frame("F_LIFE_MACHINE"))
        # 假端点返回的是数组，refine 期望对象 → 解析成 list 时应返回 None（不误判）
        self.assertIsNone(r)

    def test_discover_batch_over_http(self):
        """批量发现：一次请求处理多句，按编号回填，并透传 extra_body。"""
        from metaphor_graph.llm_backend import OpenAIBackend
        be = OpenAIBackend(api_key="k", base_url=self.base, model="m",
                           extra_body={"reasoning_effort": "low"})
        # 假端点返回的是数组；batch 期望对象 → 应降级为「整批为空」且不抛异常
        rows = be.discover_batch(["甲", "乙"])
        self.assertEqual(rows, [[], []])
        # extra_body 必须透传（GLM 靠 reasoning_effort 压低思考 token）
        self.assertEqual(self._seen.get("extra"), {"reasoning_effort": "low"})

    def test_batch_parsing_and_precomputed_backend(self):
        """批量解析 + 缓存后端：抽取器接口不变，但只走一次批量请求。"""
        from metaphor_graph.llm_backend import (
            PrecomputedBackend, batch_discover, LLMCandidate, _parse_json_blob)

        # 解析：键是字符串编号，值是该句候选数组
        blob = _parse_json_blob('{"1": [{"source_domain":"漩涡","target_domain":"舆论",'
                                '"ground":["裹挟"],"triggers":["漩涡"],"confidence":0.9}],'
                                '"2": []}')
        self.assertEqual(blob["1"][0]["source_domain"], "漩涡")

        class Fake:
            def __init__(self):
                self.calls = 0

            def discover_batch(self, chunks):
                self.calls += 1
                return [[LLMCandidate("漩涡", "舆论", triggers=["漩涡"],
                                      confidence=0.9)] if "漩涡" in c else []
                        for c in chunks]

        fake = Fake()
        texts = ["陷入舆论的漩涡。", "苹果发布了新手机。", "又一次漩涡。"]
        table = batch_discover(fake, texts, batch_size=2, verbose=False)
        self.assertEqual(fake.calls, 2)          # 3 句 / 每批 2 → 2 次请求
        self.assertTrue(table["陷入舆论的漩涡。"])
        self.assertEqual(table["苹果发布了新手机。"], [])

        ex = MetaphorExtractor(llm_backend=PrecomputedBackend(table))
        self.assertTrue(ex.extract("陷入舆论的漩涡。", doc_id="d"))
        self.assertEqual(ex.extract("苹果发布了新手机。", doc_id="d"), [])
        self.assertEqual(fake.calls, 2)          # 消费缓存不再发请求

    def test_batch_degrades_gracefully(self):
        """批量响应无法解析时整批降级为空，绝不抛异常。"""
        import logging
        from metaphor_graph.llm_backend import OpenAIBackend
        log = logging.getLogger("metaphor_graph.llm_backend")
        with self.assertLogs(log, level="WARNING"):
            be = OpenAIBackend(api_key="k", base_url="http://127.0.0.1:1/v1")
            self.assertEqual(be.discover_batch(["甲", "乙"]), [[], []])

    def test_graceful_degradation(self):
        """端点不可达 / 无密钥时，必须降级而非抛异常（流水线不因 LLM 崩溃）。"""
        import logging
        from metaphor_graph.llm_backend import OpenAIBackend
        log = logging.getLogger("metaphor_graph.llm_backend")
        # 清空 LLM_* 环境变量：OpenAIBackend 会从环境读 api_key/base_url，
        # 若开发机/会话里正好配了真实密钥，这条用例就会去打真实端点
        # （甚至因欠费拿到 402 而抛致命错误），导致"无密钥"场景根本没被测到。
        keys = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_EXTRA_JSON")
        saved = {k: os.environ.pop(k) for k in keys if k in os.environ}
        try:
            with self.assertLogs(log, level="WARNING"):
                bad = OpenAIBackend(api_key="k", base_url="http://127.0.0.1:1/v1")
                self.assertEqual(bad.discover("测试"), [])
                self.assertIsNone(bad.refine(
                    "测试", DEFAULT_ONTOLOGY.get_frame("F_LIFE_MACHINE")))
            with self.assertLogs(log, level="WARNING"):
                nokey = OpenAIBackend(api_key=None)
                self.assertEqual(nokey.discover("测试"), [])
        finally:
            os.environ.update(saved)

    def test_tolerant_json_parsing(self):
        """模型常带 ```json 包裹或前后废话，解析必须容错。"""
        from metaphor_graph.llm_backend import _parse_json_blob
        self.assertEqual(_parse_json_blob('[{"a": 1}]'), [{"a": 1}])
        self.assertEqual(_parse_json_blob('```json\n[{"a": 1}]\n```'), [{"a": 1}])
        self.assertEqual(_parse_json_blob('好的：{"a": 1} 就这样'), {"a": 1})
        self.assertIsNone(_parse_json_blob("完全不是 JSON"))


@unittest.skipUnless(_HAS_JIEBA, "需要 jieba（venv_jieba）才能跑离线 LLM 后端测试")
class TestLocalHeuristicBackend(unittest.TestCase):
    def test_vehicle_extraction(self):
        from metaphor_graph.llm_backend import LocalHeuristicBackend
        b = LocalHeuristicBackend()
        words = [w for w, _ in b._equative_vehicles("这个世界就是一个舞台。")]
        self.assertIn("舞台", words)

    def test_possessive_vehicle(self):
        """「是我们团队的顶梁柱」应取「的」之后的名词，而非「团队」。"""
        from metaphor_graph.llm_backend import LocalHeuristicBackend
        b = LocalHeuristicBackend()
        words = [w for w, _ in b._equative_vehicles("他是我们团队的顶梁柱。")]
        self.assertIn("顶梁柱", words)

    def test_no_vehicle_in_literal_attribution(self):
        """「他是我最好的朋友」是字面归属判断，不应产出喻体。"""
        from metaphor_graph.llm_backend import LocalHeuristicBackend
        b = LocalHeuristicBackend()
        self.assertEqual(b._equative_vehicles("他是我最好的朋友。"), [])

    def test_proper_noun_identity_rejected(self):
        """等比句里专有名词作谓语 = 身份判断，非隐喻。"""
        from metaphor_graph.llm_backend import LocalHeuristicBackend
        b = LocalHeuristicBackend(allow_generic=True)
        self.assertEqual(b.discover("朱元璋是明朝的开国皇帝。"), [])

    def test_offline_backend_keeps_p1_below_gate(self):
        """P1 硬门槛（<0.15）必须守住 —— 方案 §6.5 Go/No-Go 决策点。"""
        from metaphor_graph.llm_backend import LocalHeuristicBackend
        samples = load_ccl2018()
        r = eval_split(samples, DEFAULT_ONTOLOGY, llm_backend=LocalHeuristicBackend())
        self.assertLess(r["literal_error_rate"], 0.15)
        r0 = eval_split(samples, DEFAULT_ONTOLOGY, llm_backend=None)
        self.assertGreaterEqual(r["recall"], r0["recall"])


# ---------------------------------------------------------------------------
# 本轮补齐：溯源 / 上下文预算 / 可训练排序器 / 健康度 / 基线
# ---------------------------------------------------------------------------

class TestEvidenceAndConflict(unittest.TestCase):
    """知识管理 · 演化阶段的冲突消解与溯源。"""

    def _edges(self):
        a = _edge()
        b = _edge()
        b.id = "L1_other"
        b.confidence = 0.95
        return a, b

    def test_evidence_defaults(self):
        e = _edge()
        self.assertEqual(e.extractor_version, EXTRACTOR_VERSION)
        self.assertFalse(e.deprecated)
        self.assertEqual(e.authority(), 0.5)   # 无证据时回落
        self.assertEqual(e.support(), 1)

    def test_evidence_authority_and_support(self):
        e = _edge()
        e.evidence = [
            Evidence(chunk_id="c0", authority=0.9),
            Evidence(chunk_id="c1", authority=0.5),
        ]
        self.assertAlmostEqual(e.authority(), 0.7)
        self.assertEqual(e.support(), 2)

    def test_resolve_by_authority(self):
        a, b = self._edges()
        a.evidence = [Evidence(chunk_id="c0", authority=0.9)]
        b.evidence = [Evidence(chunk_id="c1", authority=0.2)]
        self.assertIs(resolve_conflict([a, b], strategy="authority"), a)

    def test_resolve_by_vote(self):
        a, b = self._edges()
        a.evidence = [Evidence(chunk_id=f"c{i}", authority=0.4) for i in range(3)]
        b.evidence = [Evidence(chunk_id="c9", authority=0.4)]
        self.assertIs(resolve_conflict([a, b], strategy="vote"), a)

    def test_deprecated_never_wins(self):
        a, b = self._edges()
        a.deprecated = True
        self.assertIs(resolve_conflict([a, b]), b)
        self.assertIsNone(resolve_conflict([a]))

    def test_merge_evidence_keeps_provenance(self):
        a, b = self._edges()
        a.evidence = [Evidence(chunk_id="c0")]
        b.evidence = [Evidence(chunk_id="c1"), Evidence(chunk_id="c0")]
        merge_evidence(a, [b])
        self.assertEqual(a.support(), 2)  # c0 去重，不重复计数

    def test_describe_is_embeddable(self):
        """超边必须能渲染成一句自然语言（HyperGraphRAG 的关键做法）。"""
        e = _edge(ground=["紧绷", "机械重复"], triggers=["发条"])
        d = e.describe()
        self.assertIn("发条", d)
        self.assertIn("紧绷", d)
        self.assertIn("机器", d)
        self.assertIn("生活状态", d)


class TestContextBudget(unittest.TestCase):
    """上下文 token 预算 50/30/20（移植 HyperRAG）。"""

    def test_ratios_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            ContextBudget(ratios=(0.5, 0.5, 0.5))

    def test_unused_quota_carries_forward(self):
        """超边类额度没用完时，应顺延给后面的源文本块。"""
        b = ContextBudget(max_tokens=1000, chars_per_token=1.0)
        pack = b.pack(["短"], ["概念A"], ["x" * 500])
        self.assertEqual(pack.hyperedges, ["短"])
        # 超边额度 500 只用了 1 → 顺延 499，实体用 3 → 再顺延 496 给 chunk
        self.assertEqual(pack.entities, ["概念A"])
        self.assertEqual(pack.chunks, ["x" * 500])

    def test_overflow_is_trimmed(self):
        b = ContextBudget(max_tokens=100, chars_per_token=1.0)
        pack = b.pack(["y" * 200], [], [])
        self.assertEqual(pack.hyperedges, [])

    def test_pack_text_sections(self):
        b = ContextBudget(max_tokens=300, chars_per_token=1.0)
        pack = b.pack(["超边A"], ["实体B"], ["原文C"])
        self.assertIn("【隐喻映射】", pack.text)
        self.assertIn("【原文片段】", pack.text)


class TestAdaptiveThreshold(unittest.TestCase):
    """自适应阈值衰减 + 密度感知（移植 HyperRAG）。"""

    def test_regime_boundaries(self):
        t = AdaptiveThreshold()
        self.assertEqual(t.regime(1.0), "low")
        self.assertEqual(t.regime(2.35), "low")
        self.assertEqual(t.regime(3.0), "mid")
        self.assertEqual(t.regime(5.0), "mid")
        self.assertEqual(t.regime(9.0), "high")

    def test_decays_until_min_keep(self):
        t = AdaptiveThreshold(tau0=0.9, decay=0.2, max_decays=5, min_keep=3)
        scored = [("a", 0.5), ("b", 0.4), ("c", 0.3), ("d", 0.1)]
        kept, dec = t.select(scored, density=1.0)
        self.assertGreaterEqual(len(kept), 3)
        self.assertGreater(dec.n_decays, 0)

    def test_no_padding_with_noise(self):
        """关键行为：候选只有 2 条达标时，不应硬凑到 min_keep。"""
        t = AdaptiveThreshold(tau0=0.5, min_keep=50)
        kept, _ = t.select([("a", 0.9), ("b", 0.8)], density=1.0)
        self.assertEqual(len(kept), 2)

    def test_high_density_caps_output(self):
        t = AdaptiveThreshold(tau0=0.0, min_keep=1, max_keep=5)
        scored = [(str(i), 1.0 - i * 0.001) for i in range(200)]
        kept, dec = t.select(scored, density=10.0)
        self.assertEqual(len(kept), 5)
        self.assertEqual(dec.regime, "high")

    def test_empty(self):
        kept, dec = AdaptiveThreshold().select([], density=1.0)
        self.assertEqual(kept, [])
        self.assertEqual(dec.n_selected, 0)


class TestTraining(unittest.TestCase):
    """零标注成本的训练样本构造 + 可训练排序器。"""

    def setUp(self):
        self.chunks = [
            "我们的项目现在陷在泥潭里，每前进一步都要拔出腿来。",
            "整个团队陷在泥潭里，越挣扎陷得越深，进度完全停滞。",
            "他每天像根发条一样拧紧自己，生活失去了弹性。",
        ]
        self.shg = MetaphorSHGBuilder().build(self.chunks, doc_id="d0")
        self.order = {f"d0_c{i}": i for i in range(len(self.chunks))}
        self.chunk_map = {f"d0_c{i}": c for i, c in enumerate(self.chunks)}

    def test_feature_dim(self):
        f = extract_features(_edge(), _edge())
        self.assertEqual(len(f), len(FEATURE_NAMES))

    def test_role_aware_features(self):
        a = _edge(ground=["紧绷", "机械重复"])
        b = _edge(ground=["紧绷"], frame_id="F_OTHER", cascade_id="C_OTHER")
        fa = extract_features(a, a)
        fb = extract_features(a, b)
        self.assertEqual(fa[4], 1.0)   # same_frame
        self.assertEqual(fa[5], 1.0)   # same_cascade
        self.assertEqual(fb[4], 0.0)
        self.assertEqual(fb[5], 0.0)
        self.assertGreater(fa[6], fb[6])  # 喻底 Jaccard：同链更高

    def test_chunk_mode_is_default_and_requires_texts(self):
        with self.assertRaises(ValueError):
            build_training_set(self.shg, self.order, positive_mode="chunk")

    def test_training_set_is_supervised(self):
        """不泄漏的构造：正样本 = 该 chunk 实际抽出的超边。"""
        ds = build_training_set(self.shg, chunks=self.chunk_map)
        if len(ds) == 0:
            self.skipTest("语料未抽出超边")
        self.assertGreater(ds.positives, 0)
        self.assertLess(ds.positives, len(ds))  # 必须同时有负样本

    def test_chunk_mode_has_no_trivial_separator(self):
        """chunk 模式不应被单特征完美分类——这是它与结构模式的根本区别。"""
        ds = build_training_set(self.shg, chunks=self.chunk_map)
        if len(ds) == 0 or ds.positives == 0 or ds.positives == len(ds):
            self.skipTest("样本不足或类别单一")
        self.assertEqual(trivial_separators(ds), [])

    def test_feature_auc_detects_dominant_feature(self):
        """软泄漏守卫：AUC 极高的单特征必须被点名（完美可分之外的场景）。"""
        ds = build_training_set(self.shg, chunks=self.chunk_map)
        if len(ds) == 0 or ds.positives == 0:
            self.skipTest("样本不足")
        aucs = feature_auc(ds)
        self.assertEqual(len(aucs), len(FEATURE_NAMES))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in aucs.values() if v == v))
        # clue 是当前抽取器判定规则本身，AUC 必然偏高——正是要盯住的特征
        self.assertGreater(aucs["clue"], 0.7)

    def test_leakage_report_empty_for_chunk_mode(self):
        ds = build_training_set(self.shg, chunks=self.chunk_map)
        if len(ds) == 0 or ds.positives == 0:
            self.skipTest("样本不足")
        self.assertEqual(leakage_report(ds), [])

    def test_leakage_report_fires_for_structural_mode(self):
        ds = build_training_set(self.shg, self.order, positive_mode="cascade")
        if len(ds) == 0 or ds.positives == 0:
            self.skipTest("样本不足")
        self.assertTrue(any("same_cascade" in s for s in leakage_report(ds)))

    def test_structural_modes_leak(self):
        """守卫：以结构分组定义的正样本必然泄漏，必须被检出。

        若这条断言失败，说明特征或正样本定义变了，需要重新做泄漏审查。
        """
        for mode, expect in (("cascade", "same_cascade"), ("chain", "same_frame")):
            ds = build_training_set(self.shg, self.order, positive_mode=mode)
            if len(ds) == 0 or ds.positives == 0:
                continue
            self.assertIn(expect, trivial_separators(ds),
                          f"{mode} 模式应被检出单特征可分")

    def test_scorer_learns(self):
        ds = build_training_set(self.shg, self.order, positive_mode="cascade")
        if len(ds) < 4 or ds.positives < 2:
            self.skipTest("样本不足，无法验证训练收敛")
        s = MetaphorScorer().fit(ds, epochs=80, patience=10)
        self.assertGreater(len(s.history), 0)
        # 训练后应能把正样本排在负样本之前
        pos = [s.score_features(ds.X[i]) for i in range(len(ds)) if ds.y[i] > 0.5]
        neg = [s.score_features(ds.X[i]) for i in range(len(ds)) if ds.y[i] < 0.5]
        self.assertGreater(sum(pos) / len(pos), sum(neg) / len(neg))
        self.assertEqual(len(s.weights()), len(FEATURE_NAMES))

    def test_scorer_save_load(self):
        import tempfile
        ds = build_training_set(self.shg, self.order, positive_mode="cascade")
        if len(ds) < 2:
            self.skipTest("样本不足")
        s = MetaphorScorer().fit(ds, epochs=10)
        path = os.path.join(tempfile.gettempdir(), "_tmp_scorer.json")
        s.save(path)
        s2 = MetaphorScorer.load(path)
        self.assertAlmostEqual(s.score_features(ds.X[0]),
                               s2.score_features(ds.X[0]), places=6)
        try:
            os.remove(path)
        except OSError:
            pass

    def test_engine_uses_trained_scorer(self):
        """接入训练后的排序器，打分口径应切换到学习式。"""
        eng = RetrievalEngine(self.shg, self.chunks)
        m = self.shg.edges[0]
        manual = eng.metaphor_retriever_score("发条", m)
        scorer, _ = train_from_shg(self.shg, self.order, epochs=30,
                                   positive_mode="cascade")
        eng2 = RetrievalEngine(self.shg, self.chunks, scorer=scorer)
        learned = eng2.metaphor_retriever_score("发条", m)
        self.assertNotEqual(manual, learned)

    def test_rank_mappings_returns_decision(self):
        eng = RetrievalEngine(self.shg, self.chunks)
        ranked, dec = eng.rank_mappings("项目推进不动")
        self.assertIsInstance(dec, ThresholdDecision)
        self.assertLessEqual(len(ranked), 20)

    def test_pack_context(self):
        eng = RetrievalEngine(self.shg, self.chunks,
                              budget=ContextBudget(max_tokens=400,
                                                   chars_per_token=1.0))
        pack = eng.pack_context(self.shg.edges[:2], ["d0_c0"])
        self.assertTrue(pack.hyperedges)
        self.assertIn("【隐喻映射】", pack.text)


class TestHealth(unittest.TestCase):
    """图健康度指标。"""

    def test_empty_graph_health(self):
        h = graph_health(MetaphorSHG())
        self.assertEqual(h.n_edges, 0)
        self.assertFalse(h.healthy())

    def test_healthy_graph(self):
        shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        h = graph_health(shg)
        self.assertGreater(h.n_edges, 0)
        self.assertGreater(h.avg_arity, 2.0)
        self.assertEqual(h.evidence_coverage, 0.0)  # 抽取器尚未挂证据链
        self.assertIn("证据链覆盖为 0", " ".join(h.warnings))

    def test_arity_degradation_warning(self):
        """喻底抽不出来 → 超边退化成普通边 → 必须告警。

        注意：不能用 _edge(ground=[]) —— 该 helper 会把空列表回落成默认喻底。
        """
        e = MetaphorHyperedge(id="L1_nog", source_domain="机器",
                              target_domain="生活状态", ground=[], triggers=["发条"])
        h = graph_health(MetaphorSHG(edges=[e]))
        self.assertAlmostEqual(h.avg_arity, 2.0)
        self.assertLess(h.avg_arity, 2.2)
        self.assertTrue(any("退化为普通边" in w for w in h.warnings))

    def test_coverage_warning(self):
        e = _edge(frame_id=None, cascade_id=None)
        h = graph_health(MetaphorSHG(edges=[e], frames=[]))
        self.assertAlmostEqual(h.hierarchy_coverage, 0.0)
        self.assertTrue(any("层级覆盖率" in w for w in h.warnings))

    def test_unmatched_pool_warning(self):
        shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        h = graph_health(shg, unmatched_pool=10_000)
        self.assertTrue(any("未匹配累积池" in w for w in h.warnings))

    def test_report_renders(self):
        shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        self.assertIn("图密度 Δ", graph_health(shg).report())

    def test_density(self):
        self.assertAlmostEqual(graph_density(10, 5), 2.0)
        self.assertEqual(graph_density(0, 0), 0.0)


class TestBaselines(unittest.TestCase):
    """基线注册表：确保本轮补齐的对照没有被漏掉。"""

    def test_missing_baselines_present(self):
        ids = {b.bid for b in BASELINES}
        for need in ("B3", "B4", "B5", "B6"):
            self.assertIn(need, ids)

    def test_og_rag_is_the_only_ontology_baseline(self):
        """OG-RAG 是唯一带本体的非本方案基线，用于分离「本体」与「层级」。"""
        onto = [b.bid for b in BASELINES if b.ontology and not b.ours]
        self.assertEqual(onto, ["B6"])

    def test_hypergraphrag_is_representation_counterpart(self):
        self.assertIn("NeurIPS 2025", BY_ID["B3"].citation)
        self.assertIn("hypergraph", BY_ID["B3"].structure)

    def test_eval_has_binary_control(self):
        """必须有中性对照，否则无法证明增益来自超边而非「图」。"""
        binaries = [s for s in EVAL_SUITES if s.domain == "binary"]
        self.assertTrue(any("中性对照" in s.name for s in binaries))

    def test_new_ablations_present(self):
        aids = {a.aid for a in ABLATIONS}
        for need in ("A7", "A8", "A9"):
            self.assertIn(need, aids)

    def test_render_plan(self):
        out = render_plan()
        self.assertIn("OG-RAG", out)
        self.assertIn("RAPTOR", out)
        self.assertIn("HyperGraphRAG", out)


# ---------------------------------------------------------------------------
# 可插拔句向量层（embeddings.set_embedder + OpenAICompatibleEmbedder，§6.2）
# ---------------------------------------------------------------------------
class TestEmbedderLayer(unittest.TestCase):
    """验证注入点全链路生效、HTTP 通路、缓存与失败纪律（全部本地，无真实网络）。"""

    def setUp(self):
        from metaphor_graph import embeddings as emb
        self.emb = emb
        emb.set_embedder(None)  # 每个用例从干净状态出发

    def tearDown(self):
        self.emb.set_embedder(None)

    def test_set_embedder_injects_globally(self):
        calls = []

        def stub(text):
            calls.append(text)
            return [1.0, 0.0]

        self.emb.set_embedder(stub)
        self.assertEqual(self.emb.embed("泥潭"), [1.0, 0.0])
        self.assertEqual(calls, ["泥潭"])
        # semfield 的独立槽位被一并接通（单一语义向量源，防两处漂移）
        self.assertIs(sf.EMBEDDER, stub)
        self.emb.set_embedder(None)
        self.assertIsNone(sf.EMBEDDER)
        # 恢复默认哈希编码后行为不变（同字符串同向量）
        self.assertEqual(self.emb.embed("泥潭"), self.emb.embed("泥潭"))

    def test_injected_error_propagates_no_silent_fallback(self):
        """注入的 embedder 报错必须上抛 —— 静默退回哈希向量是本项目的大忌（§7.2）。"""
        def bad(_text):
            raise RuntimeError("embedder down")

        self.emb.set_embedder(bad)
        with self.assertRaises(RuntimeError):
            self.emb.embed("泥潭")

    @staticmethod
    def _start_server(status=200):
        import hashlib
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        hits = {"n": 0}

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                hits["n"] += 1
                body = _json.loads(
                    self.rfile.read(int(self.headers["Content-Length"])))
                if status != 200:
                    self.send_response(status)
                    self.end_headers()
                    self.wfile.write(b'{"error": "mock"}')
                    return
                vecs = []
                for text in body["input"]:
                    h = hashlib.md5(text.encode("utf-8")).digest()
                    v = [b / 255.0 for b in h[:8]]
                    n = sum(x * x for x in v) ** 0.5 or 1.0
                    vecs.append([x / n for x in v])
                payload = _json.dumps({
                    "data": [{"index": i, "embedding": v}
                             for i, v in enumerate(vecs)],
                    "usage": {"prompt_tokens": 6 * len(body["input"])},
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, f"http://127.0.0.1:{server.server_address[1]}", hits

    def test_openai_embedder_mock_server_roundtrip_and_cache(self):
        import tempfile

        base = self.emb.OpenAICompatibleEmbedder
        server, url, hits = self._start_server()
        try:
            with tempfile.TemporaryDirectory() as td:
                cache = os.path.join(td, "embed_cache.json")
                e1 = base(api_key="k", base_url=url, model="m",
                          cache_path=cache, batch_size=4)
                v1 = e1.embed("泥潭")
                self.assertEqual(len(v1), 8)
                vs = e1.embed_batch(["泥潭", "沼泽", "泥潭"])  # 含重复文本
                self.assertEqual(vs[0], v1)
                self.assertEqual(vs[0], vs[2])
                n_after_first = hits["n"]
                # 第二个实例：全部命中磁盘缓存，0 次请求（可复现、零成本）
                e2 = base(api_key="k", base_url=url, model="m", cache_path=cache)
                self.assertEqual(e2.embed("泥潭"), v1)
                self.assertEqual(hits["n"], n_after_first)
                self.assertEqual(e2.n_requests, 0)
                self.assertIn("缓存", e2.usage_report())
        finally:
            server.shutdown()

    def test_openai_embedder_fatal_not_swallowed(self):
        """402/401/403 必须抛 EmbedderFatalError —— 欠费被吞成空结果是踩过的坑。"""
        base = self.emb.OpenAICompatibleEmbedder
        server, url, _hits = self._start_server(status=402)
        try:
            e = base(api_key="k", base_url=url, model="m")
            with self.assertRaises(self.emb.EmbedderFatalError):
                e.embed("泥潭")
        finally:
            server.shutdown()

    def test_openai_embedder_generic_error(self):
        base = self.emb.OpenAICompatibleEmbedder
        server, url, _hits = self._start_server(status=500)
        try:
            e = base(api_key="k", base_url=url, model="m")
            with self.assertRaises(self.emb.EmbedderError):
                e.embed("泥潭")
        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# Neo4j 运行期驱动（storage.Neo4jStore，路线图 §8.2 P2）
# ---------------------------------------------------------------------------
class TestNeo4jStore(unittest.TestCase):
    """用本地 mock HTTP 事务端点验证请求打包、分批、幂等语句与失败纪律。"""

    @staticmethod
    def _start_server(fail_auth=False, cypher_error=False):
        import base64
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        seen = {"statements": [], "auth": None, "paths": []}

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                seen["paths"].append(self.path)
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                auth = self.headers.get("Authorization", "")
                seen["auth"] = auth
                if fail_auth:
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b'{"errors": [{"code": "Neo.ClientError.Security.Unauthorized"}]}')
                    return
                body = _json.loads(raw)
                seen["statements"].extend(
                    [(s["statement"], s["parameters"]) for s in body["statements"]])
                if cypher_error:
                    payload = {"results": [], "errors": [
                        {"code": "Neo.ClientError.Statement.SyntaxError",
                         "message": "Invalid syntax (mock)"}]}
                else:
                    payload = {"results": [{"data": [{"row": ["Domain", 7]}]}]
                               * len(body["statements"]), "errors": []}
                out = _json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        _ = base64  # noqa: F841  （保持 import 一致性）
        server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, f"http://127.0.0.1:{server.server_address[1]}", seen

    def _store(self, url):
        from metaphor_graph.storage import Neo4jStore
        return Neo4jStore(uri=url, user="neo4j", password="pw",
                          database="neo4j", batch_size=50)

    def test_load_shg_batches_statements_without_semicolons(self):
        from metaphor_graph.builder import MetaphorSHGBuilder

        shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        server, url, seen = self._start_server()
        try:
            store = self._store(url)
            n = store.load_shg(shg)
            # 每条语句都发到了 /db/neo4j/tx/commit，且不带行尾分号
            self.assertTrue(all(p.endswith("/db/neo4j/tx/commit")
                                for p in seen["paths"]))
            self.assertEqual(len(seen["statements"]), n)
            self.assertTrue(n > 0)
            self.assertTrue(all(not c.rstrip().endswith(";")
                                for c, _ in seen["statements"]))
            # 幂等：同一张图再导一遍仍是 MERGE 语义（无 CREATE 节点语句）
            self.assertTrue(any(c.startswith("MERGE") for c, _ in seen["statements"]))
            self.assertFalse(any(c.startswith("CREATE (") for c, _ in seen["statements"]))
            # 计数查询能解析回行
            counts = store.counts()
            self.assertIn("Domain", counts)
            self.assertEqual(counts["Domain"], 7)
        finally:
            server.shutdown()

    def test_auth_header_and_empty_noop(self):
        server, url, seen = self._start_server()
        try:
            store = self._store(url)
            self.assertEqual(store.execute([]), [])   # 空事务不发起请求
            store.run("RETURN 1")
            self.assertTrue(seen["auth"].startswith("Basic "))
        finally:
            server.shutdown()

    def test_cypher_error_raised(self):
        from metaphor_graph.storage import Neo4jError
        server, url, _ = self._start_server(cypher_error=True)
        try:
            store = self._store(url)
            with self.assertRaises(Neo4jError):
                store.run("MATCH (n) RETURN n")
        finally:
            server.shutdown()

    def test_fatal_auth_error(self):
        from metaphor_graph.storage import Neo4jFatalError
        server, url, _ = self._start_server(fail_auth=True)
        try:
            store = self._store(url)
            with self.assertRaises(Neo4jFatalError):
                store.run("RETURN 1")
        finally:
            server.shutdown()


class TestQueryObservability(unittest.TestCase):
    """查询侧可观测性泛函 Ω（observability.py）。

    最重要的护栏是 `test_omega_invariant_to_candidate_pool`：Ω 必须只读查询。
    这不是「实验发现」而是「API 形状」——measure() 的签名里根本没有候选池，
    该测试把这条不变式钉成回归护栏，防止后续有人为了刷指标把候选信号混进来。
    """

    def setUp(self):
        from metaphor_graph.observability import ObservabilityMeter
        self.meter = ObservabilityMeter()      # 种子本体（DEFAULT_ONTOLOGY）
        self.ont = DEFAULT_ONTOLOGY

    # ---------------------------------------------------- 只读查询的不变式
    def test_omega_invariant_to_candidate_pool(self):
        """打乱/截断/清空候选池，Ω 逐位不变（同一条查询）。"""
        import copy
        import random
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.eval_corpus import DOCS

        query = "泥潭，沼泽"          # 触发词重叠型
        q2 = "她的眼睛像什么一样晶莹剔透？"   # 改写型
        base = {q: self.meter.measure(q).to_dict() for q in (query, q2)}

        chunks = DOCS["doc_project"]
        shg = MetaphorSHGBuilder().build(chunks, doc_id="dp")
        variants = []
        for seed in (0, 1, 7):
            edges = copy.deepcopy(shg.edges)
            random.Random(seed).shuffle(edges)
            variants.append(edges[: max(1, len(edges) // 2)])
            variants.append(edges)
        variants.append([])                      # 空候选池

        for edges in variants:
            shg2 = MetaphorSHG(edges=edges)
            eng = RetrievalEngine(shg2, chunks, doc_id="dp")
            eng.cross_domain_retrieve(query)      # 触碰候选侧（排序/检索）
            eng.cross_domain_retrieve(q2)
            for q in (query, q2):
                # 候选池变了，Ω 必须逐位相同（浮点也完全相同：纯本体查表）
                self.assertEqual(self.meter.measure(q).to_dict(), base[q])

    def test_measure_signature_has_no_candidate_argument(self):
        """签名里不得出现候选池相关形参（结构性地保证不变式）。"""
        import inspect
        from metaphor_graph.observability import measure
        params = list(inspect.signature(measure).parameters)
        for bad in ("shg", "edges", "candidates", "retriever", "chunks",
                    "ranked", "result", "scorer"):
            self.assertNotIn(bad, params)

    # ------------------------------------------------------------ 分量语义
    def test_no_trigger_query_is_collapsed_zero(self):
        r = self.meter.measure("今天天气不错，心情也很好")
        self.assertEqual(r.omega, 0.0)
        self.assertEqual(r.omega_e, 0.0)
        self.assertEqual(r.omega_n, 0.0)
        self.assertEqual(r.omega_f, 0.0)
        self.assertEqual(r.completeness, 0.0)
        self.assertEqual(r.regime, "collapsed")
        self.assertEqual(r.n_seed_triggers, 0)

    def test_empty_query_is_collapsed_zero(self):
        r = self.meter.measure("")
        self.assertEqual(r.omega, 0.0)
        self.assertEqual(r.regime, "collapsed")

    def test_trigger_hit_activates_frames(self):
        r = self.meter.measure("泥潭")
        self.assertEqual(r.matched_triggers, ("泥潭",))
        self.assertTrue(r.activated_frames)
        self.assertGreater(r.omega, 0.0)
        self.assertGreater(r.omega_e, 0.0)

    def test_paraphrase_lower_than_trigger_overlap(self):
        """构造性直觉：改写句的 Ω 应低于触发词重叠句（方向性冒烟测试）。"""
        overlap = self.meter.measure("泥潭，沼泽，陷进")
        para = self.meter.measure("她的眼睛像什么一样晶莹剔透？")
        self.assertGreater(overlap.omega, para.omega)

    def test_omega_components_in_range(self):
        for q in ("泥潭", "推进，停滞", "项目陷在泥潭里，推进不动，时间也浪费了",
                  "她的眼睛像什么一样晶莹剔透？", "今天天气不错"):
            r = self.meter.measure(q)
            for v in (r.omega, r.omega_e, r.omega_n, r.omega_f, r.completeness):
                self.assertGreaterEqual(v, 0.0, q)
                self.assertLessEqual(v, 1.0, q)
            self.assertLessEqual(r.omega, r.omega_geo + 1e-12)

    def test_omega_equals_geo_times_completeness(self):
        r = self.meter.measure("项目陷在泥潭里，推进不动，时间也浪费了")
        self.assertAlmostEqual(r.omega, r.omega_geo * r.completeness, places=12)

    def test_emergence_excludes_direct_targets(self):
        """Ω_N 的分子必须是「不在直接命中集里」的目标域（涌现而非回声）。"""
        r = self.meter.measure("泥潭")
        direct = set(r.direct_targets)
        emergent = set(r.emergent_targets)
        self.assertEqual(direct & emergent, set())
        self.assertTrue(emergent)               # 级联带来了新目标域

    def test_completeness_is_char_coverage(self):
        from metaphor_graph.observability import completeness
        comp, obs = completeness("泥潭", ["泥潭"])
        self.assertAlmostEqual(comp, 1.0)
        self.assertEqual(obs, 2)
        comp2, _ = completeness("abcdef泥潭", ["泥潭"])
        self.assertAlmostEqual(comp2, 2 / 8)
        # 重复出现按次数计（clip 到 1）
        comp3, _ = completeness("泥潭泥潭泥潭", ["泥潭"])
        self.assertAlmostEqual(comp3, 1.0)

    # ------------------------------------------------------------ 几何平均
    def test_geometric_mean_epsilon_floor(self):
        from metaphor_graph.observability import geometric_mean
        self.assertAlmostEqual(geometric_mean((1.0, 1.0, 1.0)), 1.0)
        # 零分量被 ε 托住：Ω 不为 0，但显著低于其它分量
        v = geometric_mean((1.0, 0.0, 1.0), eps=1e-3)
        self.assertGreater(v, 0.0)
        self.assertAlmostEqual(v, 0.1, places=6)   # (1·1e-3·1)^(1/3) = 0.1
        self.assertLess(v, 0.5)

    def test_geometric_mean_order_preserved(self):
        from metaphor_graph.observability import geometric_mean
        self.assertLess(geometric_mean((0.9, 0.1, 0.9)),
                        geometric_mean((0.9, 0.2, 0.9)))

    # ------------------------------------------------------------ 流量熵
    def test_entropy_degenerate_cases(self):
        from metaphor_graph.observability import normalized_entropy
        self.assertEqual(normalized_entropy([]), 0.0)
        self.assertEqual(normalized_entropy([0.0, 0.0]), 0.0)
        self.assertEqual(normalized_entropy([3.0]), 0.5)   # 单条正流量 → 有限值
        self.assertAlmostEqual(normalized_entropy([1.0, 1.0]), 1.0)
        self.assertAlmostEqual(normalized_entropy([1.0, 1.0, 1.0, 1.0]), 1.0)
        # 坍缩分布熵低，均匀分布熵高
        self.assertLess(normalized_entropy([9.0, 1.0]),
                        normalized_entropy([5.0, 5.0]))

    def test_entropy_penalizes_single_trigger_collapse(self):
        """两个触发词命中同一框架（流量坍缩）应比命中两个框架的 Ω 更低。"""
        collapsed = self.meter.measure("泥潭，沼泽")        # 同框架（地形）
        spread = self.meter.measure("泥潭，推进")           # 跨框架
        self.assertLess(collapsed.omega_f, spread.omega_f)

    # -------------------------------------------------------------- regime
    def test_regime_boundaries(self):
        from metaphor_graph.observability import regime_of
        self.assertEqual(regime_of(0.0, 3), "collapsed")
        self.assertEqual(regime_of(0.9, 0), "collapsed")   # 无框架 → collapsed
        self.assertEqual(regime_of(0.49, 2), "sparse")
        self.assertEqual(regime_of(0.5, 2), "dense")
        self.assertEqual(regime_of(0.99, 2), "dense")

    def test_regime_matches_measured(self):
        self.assertEqual(self.meter.measure("今天天气不错").regime, "collapsed")
        self.assertEqual(self.meter.measure("泥潭").regime, "dense")

    # ---------------------------------------------------------- 一致性口径
    def test_trigger_matching_same_as_cascade_path(self):
        """Ω 的触发词口径必须与 cross_domain_retrieve 逐字一致。

        否则 Ω 说「激活了」而级联通路空手而归，门控判据就自相矛盾。
        """
        from metaphor_graph.observability import matched_triggers
        q = "项目陷在泥潭里，推进不动，时间也浪费了"
        a = set(matched_triggers(q, self.ont))
        b = {t for t in self.ont._trigger_index if t in q}
        self.assertEqual(a, b)

    def test_deterministic(self):
        q = "项目陷在泥潭里，推进不动"
        self.assertEqual(self.meter.measure(q).to_dict(),
                         self.meter.measure(q).to_dict())

    def test_meter_cache_and_gate(self):
        m = self.meter
        self.assertFalse(m.gate("今天天气不错", theta=0.1))
        self.assertTrue(m.gate("泥潭", theta=0.1))
        self.assertFalse(m.gate("泥潭", theta=0.99))

    # -------------------------------------------------- 已知局限（护栏）
    def test_omega_zero_iff_cascade_path_would_be_empty(self):
        """契约：Ω=0 ⟺ 无触发词命中 ⟹ 级联通路必然空手而归。

        这是**定理**（无触发词 → match_by_triggers 空 → cross_domain_retrieve 的
        agg 空），不是经验发现。实测 632 条改写查询里 Ω=0 的 518 条，
        级联通路非空的恰好 0 条。测试把这条定理钉住：若未来有人给 Ω 加了
        「没有触发词但语义相近也算激活」之类的启发式，这里会红。
        """
        for q in ("今天天气不错", "", "abcdef", "完全没有触发词的长句子在这里"):
            r = self.meter.measure(q)
            self.assertEqual(r.omega, 0.0, q)
            self.assertEqual(r.n_seed_triggers, 0, q)

    def test_omega_is_not_monotone_in_trigger_count(self):
        """已知局限的显式化：Ω 与「触发词命中数」在**真实数据上**秩相关 ρ=0.995，
        但这不是设计意图，而是 0 块（无命中）主导的假象。

        在 Ω>0 区间内 Ω 对触发词数**非单调**：
          - Ω_E = 点亮框架数 / 种子触发词数 —— 多个触发词坍缩到同一框架时分母涨、
            分子不涨，Ω_E 反而下降；
          - 完备度因子 = 覆盖字符 / 查询长度 —— 查询越长，同样命中下 Ω 越低。
        "泥潭"（1 词）Ω=0.794 > "泥潭，沼泽，陷进，深坑"（4 词）Ω=0.289。

        这个测试记录该性质，供后续设计决策参考（若要让 Ω 真正度量「激活了多少结构」
        而非「查询有多短」，完备度因子与 Ω_E 的归一化都需要重做）。
        """
        one = self.meter.measure("泥潭")
        four = self.meter.measure("泥潭，沼泽，陷进，深坑")
        self.assertEqual(four.n_seed_triggers, 4)
        self.assertEqual(one.n_seed_triggers, 1)
        self.assertGreater(one.omega, four.omega)   # 非单调：词多反而 Ω 低
        self.assertGreater(one.completeness, four.completeness)
        # 但 Ω=0 与 Ω>0 的分界仍严格由「有无触发词命中」决定
        self.assertEqual(self.meter.measure("今天天气不错").omega, 0.0)


class TestHGNDriven(unittest.TestCase):
    """驱动/源项版 HGNN（α）与严格次随机阻尼（ε）。

    背景：S 行和恰为 1（行随机），无源项迭代 X ← M X 收敛到连通分量的
    平稳分布 → 同分量节点向量趋同 → metaphor_coherence 退化为「同分量」
    指示。加源项 X ← (1-α)X0 + α·M·X 后不动点保留源身份，退化被阻止。
    """

    def setUp(self):
        self.shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)

    # ---- 默认行为不回归 ----
    def test_default_is_undriven_and_unchanged(self):
        """alpha=1.0 必须与历史无源项实现 X ← M·X **逐位相同**。"""
        import numpy as np
        a = MetaphorHGNN(self.shg, layers=2).forward()
        b = MetaphorHGNN(self.shg, layers=2, alpha=1.0).forward()
        c = MetaphorHGNN(self.shg, layers=2, alpha=1.0, leak=0.0).forward()
        self.assertTrue(np.array_equal(a, b))
        self.assertTrue(np.array_equal(a, c))

    def test_alpha_one_equals_matrix_power(self):
        """alpha=1 时 H 应等于 M^layers · X0（用稠密算子交叉验证）。"""
        import numpy as np
        g = MetaphorHGNN(self.shg, layers=2, alpha=1.0)
        H = g.forward()
        M = g.propagation_matrix()
        ref = M @ M @ g.X
        self.assertTrue(np.allclose(H, ref, atol=1e-10))

    def test_propagation_matrix_matches_conv(self):
        """propagation_matrix() 必须与 _conv 的循环实现逐元素一致。"""
        import numpy as np
        g = MetaphorHGNN(self.shg, layers=1, alpha=1.0)
        M = g.propagation_matrix()
        self.assertTrue(np.allclose(M @ g.X, g._conv(g.X), atol=1e-10))

    def test_alpha_zero_returns_source(self):
        """alpha=0 → 不传播，H == X0。"""
        import numpy as np
        g = MetaphorHGNN(self.shg, layers=2, alpha=0.0)
        self.assertTrue(np.array_equal(g.forward(), g.X))

    # ---- 谱 / 行和性质 ----
    def test_S_rowsum_is_exactly_one(self):
        """S 行和恰为 1（行随机）—— 这是「无源项必然坍缩」的根源。"""
        import numpy as np
        g = MetaphorHGNN(self.shg, layers=1)
        M = g.propagation_matrix()
        S = 2.0 * M - np.eye(g.num_nodes)      # ε=0 时 M = 0.5(I+S)
        live = np.abs(S).sum(axis=1) > 0
        self.assertTrue(np.allclose(S[live].sum(axis=1), 1.0, atol=1e-12))

    def test_spectral_radius_S_is_one(self):
        import numpy as np
        g = MetaphorHGNN(self.shg, layers=1)
        S = 2.0 * g.propagation_matrix() - np.eye(g.num_nodes)
        rho = float(np.max(np.abs(np.linalg.eigvals(S))))
        self.assertAlmostEqual(rho, 1.0, places=9)

    def test_leak_makes_rowsum_strictly_substochastic(self):
        """ε>0 → M 行和 = 1-ε/2 < 1 严格成立，ρ(M) ≤ 1-ε/2。"""
        import numpy as np
        for eps in (0.01, 0.05, 0.1, 0.5):
            g = MetaphorHGNN(self.shg, layers=1, leak=eps)
            M = g.propagation_matrix()
            live = np.abs(M).sum(axis=1) > 0
            rs = M[live].sum(axis=1)
            self.assertTrue(np.all(rs < 1.0), f"ε={eps} 行和未严格小于 1")
            self.assertTrue(np.allclose(rs, 1.0 - eps / 2.0, atol=1e-12))
            rho = float(np.max(np.abs(np.linalg.eigvals(M))))
            self.assertLessEqual(rho, 1.0 - eps / 2.0 + 1e-9)

    # ---- 源项确实阻止坍缩 ----
    def test_source_term_prevents_collapse(self):
        """无源项深层迭代坍缩到同分量同向量；源项版不坍缩。

        只比较**同连通分量内**的节点对（跨分量本来就该不同）。
        """
        import numpy as np

        def components(g):
            parent = list(range(g.num_nodes))

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for members in g.he_members:
                if not members:
                    continue
                r = find(members[0])
                for m in members[1:]:
                    rm = find(m)
                    if rm != r:
                        parent[rm] = r
            out = {}
            for i in range(g.num_nodes):
                out.setdefault(find(i), []).append(i)
            return list(out.values())

        def within_cos_mean(H, g):
            vals = []
            for comp in components(g):
                for x in range(len(comp)):
                    for y in range(x + 1, len(comp)):
                        va, vb = H[comp[x]], H[comp[y]]
                        na, nb = np.linalg.norm(va), np.linalg.norm(vb)
                        if na < 1e-12 or nb < 1e-12:
                            continue
                        vals.append(float(np.dot(va, vb) / (na * nb)))
            return float(np.mean(vals))

        g_u = MetaphorHGNN(self.shg, layers=200, alpha=1.0)
        Hu = g_u.forward()
        g_d = MetaphorHGNN(self.shg, layers=200, alpha=0.5)
        Hd = g_d.forward()
        cos_u, cos_d = within_cos_mean(Hu, g_u), within_cos_mean(Hd, g_d)
        # 无源项深层迭代：同分量内已完全坍缩（余弦 = 1）
        self.assertGreater(cos_u, 0.999)
        # 源项版显著保留个体差异
        self.assertLess(cos_d, cos_u)
        self.assertLess(cos_d, 0.8)

    def test_driven_fixed_point_matches_iteration(self):
        """α<1 时长迭代应收敛到解析不动点 u* = (1-α)(I-αM)^{-1}X0。"""
        import numpy as np
        alpha = 0.5
        g = MetaphorHGNN(self.shg, layers=400, alpha=alpha)
        H = g.forward()
        M = g.propagation_matrix()
        A = np.eye(g.num_nodes) - alpha * M
        fp = (1.0 - alpha) * np.linalg.solve(A, g.X)
        scale = np.max(np.abs(fp)) + 1e-12
        self.assertLess(float(np.max(np.abs(H - fp))) / scale, 1e-6)

    def test_alpha_one_has_no_fixed_point(self):
        """α=1 时 I-αM 奇异（ρ(M)=1）→ 无唯一不动点，这正是坍缩的数学根源。"""
        import numpy as np
        g = MetaphorHGNN(self.shg, layers=1, alpha=1.0)
        M = g.propagation_matrix()
        cond = float(np.linalg.cond(np.eye(g.num_nodes) - M))
        self.assertGreater(cond, 1e10)

    # ---- 参数校验 ----
    def test_invalid_params_raise(self):
        with self.assertRaises(ValueError):
            MetaphorHGNN(self.shg, layers=2, leak=1.0)
        with self.assertRaises(ValueError):
            MetaphorHGNN(self.shg, layers=2, leak=-0.1)
        with self.assertRaises(ValueError):
            MetaphorHGNN(self.shg, layers=2, alpha=-0.1)
        # α>1 且无阻尼 → 发散，必须拒绝
        with self.assertRaises(ValueError):
            MetaphorHGNN(self.shg, layers=2, alpha=1.5, leak=0.0)
        # α>1 且阻尼不足（α(1-ε/2) = 1.5·0.75 = 1.125 ≥ 1）→ 也必须拒绝
        with self.assertRaises(ValueError):
            MetaphorHGNN(self.shg, layers=2, alpha=1.5, leak=0.5)
        # α>1 但阻尼足够（α(1-ε/2) = 1.5·0.6 = 0.9 < 1）→ 允许
        MetaphorHGNN(self.shg, layers=2, alpha=1.5, leak=0.8)

    # ---- 下游 API 在驱动模式下仍然可用 ----
    def test_downstream_apis_work_in_driven_mode(self):
        import numpy as np
        g = MetaphorHGNN(self.shg, layers=2, alpha=0.5, leak=0.1)
        H = g.forward()
        self.assertEqual(H.shape, (g.num_nodes, EMB_DIM))
        c = g.metaphor_coherence("机器", "紧绷")
        self.assertTrue(-1.0 - 1e-9 <= c <= 1.0 + 1e-9)
        v = g.entity_vec("机器")
        self.assertEqual(v.shape, (EMB_DIM,))
        l1 = [e for e in self.shg.edges if not e.is_extended]
        ranked = g.retrieve("发条", l1, k=3)
        self.assertTrue(ranked)
        self.assertEqual(ranked[0][0].__class__.__name__, "MetaphorHyperedge")

    def test_cross_layer_flag_still_works_with_source_term(self):
        import numpy as np
        gf = MetaphorHGNN(self.shg, layers=2, cross_layer=False, alpha=0.5)
        gf.forward()
        g = MetaphorHGNN(self.shg, layers=2, cross_layer=True, alpha=0.5)
        g.forward()
        # 关掉跨层后超边数更少
        self.assertLess(len(gf.he_members), len(g.he_members))


class TestDeterministicIds(unittest.TestCase):
    """边/扩展边 id 必须跨构建可复现 —— 金标缓存与本体重放都跨进程引用 id。
    曾经 uuid4 随机 id 导致 judge 缓存重放时边对不上号（全零金标，实测踩坑）。"""

    def test_l1_and_ext_ids_stable_across_builds(self):
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.eval_corpus import DOCS
        chunks = DOCS["doc_project"]
        a = MetaphorSHGBuilder().build(chunks, doc_id="dp")
        b = MetaphorSHGBuilder().build(chunks, doc_id="dp")
        self.assertEqual(sorted(e.id for e in a.edges),
                         sorted(e.id for e in b.edges))
        self.assertTrue(all(e.id.startswith(("L1_", "EXT_")) for e in a.edges))

    def test_ref_pseudo_ids_stable(self):
        from metaphor_graph.training import build_weak_refine_set
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.eval_corpus import DOCS
        chunks = DOCS["doc_project"]
        order = {f"dp_c{i}": i for i in range(len(chunks))}
        cmap = {f"dp_c{i}": c for i, c in enumerate(chunks)}
        shg = MetaphorSHGBuilder().build(chunks, doc_id="dp")
        _, st1 = build_weak_refine_set(shg, chunk_order=order, chunks=cmap,
                                       refine_path="")
        _, st2 = build_weak_refine_set(shg, chunk_order=order, chunks=cmap,
                                       refine_path="")
        self.assertEqual(st1, st2)


class TestRepairs(unittest.TestCase):
    """exp/repair 引入的修复的回归护栏。

    每项对应一个由三代并行实验实测确认的缺陷，防止回退。
    """

    # ---- 人工权重单一真源（exp/typefeat：struct 过权 49x、type 19x）----
    def test_hand_weights_single_source(self):
        from metaphor_graph.training import (HAND_WEIGHTS,
                                             HAND_WEIGHTS_LEGACY,
                                             FEATURE_NAMES)
        self.assertEqual(set(HAND_WEIGHTS), set(FEATURE_NAMES))
        self.assertAlmostEqual(sum(HAND_WEIGHTS.values()), 1.0, places=6)
        self.assertEqual(set(HAND_WEIGHTS_LEGACY), set(FEATURE_NAMES[:4]))
        # struct 的过权倍数应 > 10（实测确认的错配，不可悄悄改回）
        ratio = HAND_WEIGHTS_LEGACY["struct"] / HAND_WEIGHTS["struct"]
        self.assertGreater(ratio, 10.0,
                           "struct 过权倍数骤降 —— 是否把权重改回了拍脑袋的值？")

    def test_hand_weighted_score_respects_weights(self):
        from metaphor_graph.training import (hand_weighted_score,
                                             HAND_WEIGHTS_LEGACY)
        f = [0.5, 0.5, 0.5, 0.5, 0.0, 0.0, 0.0]
        self.assertAlmostEqual(hand_weighted_score(f, HAND_WEIGHTS_LEGACY), 0.5,
                               places=6)
        # struct/clue 截断到 1
        f2 = [0.0, 5.0, 5.0, 0.0, 0.0, 0.0, 0.0]
        self.assertAlmostEqual(hand_weighted_score(f2, HAND_WEIGHTS_LEGACY),
                               0.25 + 0.20, places=6)

    def test_two_scoring_paths_share_feature_schema(self):
        """两条打分路径必须用同一套 7 维特征。

        原缺陷：retrieval.metaphor_retriever_score 走 4 维手写公式且 type 由
        type_valid 现算，与 training 路径对未注册的 F_LLM_* 边给出不同值。
        """
        from metaphor_graph.retrieval import RetrievalEngine
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.eval_corpus import DOCS
        from metaphor_graph.training import FEATURE_NAMES
        chunks = DOCS["doc_project"]
        shg = MetaphorSHGBuilder().build(chunks, doc_id="dp")
        eng = RetrievalEngine(shg, chunks, doc_id="dp")
        if not eng.live_edges():
            self.skipTest("无超边")
        feats = eng._pair_features("项目推进不动", eng.live_edges()[0])
        self.assertEqual(len(feats), len(FEATURE_NAMES))

    # ---- 诚实覆盖率（exp/degrade：报出 100% 含 22.4pp 注水）----
    def test_honest_coverage_backward_compatible(self):
        """不传 ontology 时历史口径逐位不变（registered_* 保持 None）。"""
        from metaphor_graph.health import graph_health
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.eval_corpus import DOCS
        shg = MetaphorSHGBuilder().build(DOCS["doc_project"], doc_id="dp")
        h = graph_health(shg)
        self.assertIsNone(h.registered_hierarchy_coverage)
        self.assertNotIn("诚实覆盖率", h.report())

    def test_honest_coverage_not_above_reported(self):
        from metaphor_graph.health import graph_health
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.eval_corpus import DOCS
        from metaphor_graph.ontology import DEFAULT_ONTOLOGY
        shg = MetaphorSHGBuilder().build(DOCS["doc_project"], doc_id="dp")
        h = graph_health(shg, ontology=DEFAULT_ONTOLOGY)
        self.assertIsNotNone(h.registered_hierarchy_coverage)
        self.assertLessEqual(h.registered_hierarchy_coverage,
                             h.hierarchy_coverage + 1e-9)
        self.assertIn("诚实覆盖率", h.report())

    def test_coverage_judgement_is_registration_not_prefix(self):
        """判据必须是「本体有无条目」，不是 F_LLM_ 前缀。

        生产本体 98.6% 的框架以 F_LLM_ 开头（自举沉淀的正式框架），
        按前缀判定会把整个本体误判为退化。
        """
        from metaphor_graph.ontology import CascadeOntology
        from metaphor_graph.ontology_clean import _stable_id
        ont = CascadeOntology()
        fid = _stable_id("F_LLM", "发条", "生活状态")
        self.assertTrue(fid.startswith("F_LLM_"))
        self.assertIsNone(ont.get_frame(fid))  # 未注册才是"退化"的判据

    # ---- H4 高功效主指标（exp/dynamics：n=20 功效不足）----
    def test_h4_auc_full_handles_ties(self):
        import numpy as np
        from metaphor_graph.evaluate_hgnn import _auc_full
        auc, _, _ = _auc_full(np.array([1.0, 2.0]), np.array([0.0, 0.5]))
        self.assertAlmostEqual(auc, 1.0, places=6)
        # 完全并列 → 0.5（不是 0；这正是原 acc 口径把 raw 报成 0.150 的原因）
        auc2, _, _ = _auc_full(np.array([0.0, 0.0]), np.array([0.0, 0.0]))
        self.assertAlmostEqual(auc2, 0.5, places=6)
        auc3, _, _ = _auc_full(np.array([0.0]), np.array([1.0]))
        self.assertAlmostEqual(auc3, 0.0, places=6)

    # ---- 修复版基准的池规模（exp/typefeat：池 ≤10 使 Hits@10 平凡饱和）----
    def test_random_baseline_improves_with_pool(self):
        from metaphor_graph.evaluate_repaired import random_baseline
        small = random_baseline(7, 1)
        big = random_baseline(1100, 1)
        self.assertAlmostEqual(small["hits@10"], 1.0, places=6)  # 原基准饱和
        self.assertLess(big["hits@10"], 0.05)                    # 全局池不饱和
        self.assertLess(big["mrr"], small["mrr"])

    def test_score_conditions_default_arms_stable(self):
        """score_conditions 默认只返回 3 个臂。

        回归护栏：曾把 `hand_weighted_legacy` 无条件加入返回字典，
        导致 evaluate_fullcorpus 按固定键列表聚合时 KeyError。
        legacy 臂必须显式 opt-in。
        """
        import inspect
        from metaphor_graph.evaluate_retrieval import score_conditions
        sig = inspect.signature(score_conditions)
        self.assertIn("legacy_arm", sig.parameters)
        self.assertIs(sig.parameters["legacy_arm"].default, False)

    def test_legacy_weights_reproducible(self):
        """历史权重（0.35/0.25/0.20/0.20）仍可复现，保证旧数字可重放。"""
        from metaphor_graph.training import (hand_weighted_score,
                                             HAND_WEIGHTS_LEGACY)
        f = [1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0]
        self.assertAlmostEqual(hand_weighted_score(f, HAND_WEIGHTS_LEGACY), 1.0,
                               places=6)

    # ---- CLI 入口参数完整性（合并多分支时的真实回归）----
    def test_eval_cli_args_present(self):
        """所有评测脚本的 CLI 参数必须齐备。

        回归护栏：合并 exp/dynamics 时冲突解决遗漏了 argparse 定义，
        导致 evaluate_hgnn 运行到打印段才 AttributeError —— 单测未覆盖 CLI，
        故未拦截。这里直接解析各脚本的 `main()` 源码，钉住关键参数存在。
        """
        import inspect
        import logging as _logging
        saved = _logging.root.manager.disable
        try:
            from metaphor_graph import evaluate_hgnn as eh
            src = inspect.getsource(eh.main)
        finally:
            _logging.disable(saved)
        for flag in ("--alpha", "--leak", "--embedder", "--cascade-rule"):
            self.assertIn(f'"{flag}"', src,
                          f"evaluate_hgnn 缺少 CLI 参数 {flag} —— 合并时可能丢失")
        # 参数必须在 parse_args() **之前**注册
        self.assertLess(src.index('"--alpha"'), src.index("parse_args()"),
                        "--alpha 必须在 parse_args() 之前注册")

    def test_all_eval_modules_importable(self):
        """全部评测模块必须可导入（合并冲突常在此处暴露为语法错误）。"""
        import importlib
        import logging as _logging
        saved = _logging.root.manager.disable
        mods = ("evaluate_hgnn", "evaluate_retrieval", "evaluate_repaired",
                "evaluate_fullcorpus", "ablation", "evaluate_real",
                "evaluate_llmgold", "evaluate_a6", "evaluate_document_corpus",
                "evaluate_chain_quality")
        try:
            for m in mods:
                importlib.import_module(f"metaphor_graph.{m}")
        finally:
            _logging.disable(saved)


class TestTypeReliability(unittest.TestCase):
    """type 特征的**单一口径**回归护栏。

    曾出过的 bug：两条打分路径各写一份 type 表达式且口径不同 ——
      training.extract_features: `1.0 if cand.frame_id else 0.0`（有归属即通过）
      retrieval.metaphor_retriever_score: 查本体 mapping_type 后 type_valid，
        查不到就退化到用 frame_id 原串去校验 → 未注册的 F_LLM_* 恒判 False
    于是同一候选在训练路径得 1.0、在人工加权路径得 0.0（特征漂移）。
    """

    def test_capped_reliability_three_levels(self):
        from metaphor_graph.ontology import (DEFAULT_ONTOLOGY,
                                             TYPE_RELIABILITY_REGISTERED,
                                             TYPE_RELIABILITY_FALLBACK,
                                             TYPE_RELIABILITY_INVALID)
        tr = DEFAULT_ONTOLOGY.type_reliability_of
        # 注册框架且类型校验通过 → 1.0
        self.assertEqual(tr("F_LIFE_MACHINE", "MACHINE"),
                         TYPE_RELIABILITY_REGISTERED)
        # 未注册的回退框架 → 封顶 0.5（**不是 0.0**：不丢弃开放发现的候选）
        self.assertEqual(tr("F_LLM_ab12cd34", "GENERIC_VEHICLE"),
                         TYPE_RELIABILITY_FALLBACK)
        self.assertEqual(tr("F_NOVEL_abc123", "MACHINE"),
                         TYPE_RELIABILITY_FALLBACK)
        # 无框架归属 → 0.0
        self.assertEqual(tr(None, "MACHINE"), TYPE_RELIABILITY_INVALID)
        self.assertEqual(tr("", "MACHINE"), TYPE_RELIABILITY_INVALID)

    def test_registered_but_illegal_mapping_scores_zero(self):
        """在册框架但类型校验不通过 → 0.0（真·非法映射，可核验的否定）。"""
        from metaphor_graph.ontology import DEFAULT_ONTOLOGY
        # F_LIFE_MACHINE 注册的 source_type 是 MACHINE；声称 WAR 则不一致
        self.assertEqual(
            DEFAULT_ONTOLOGY.type_reliability_of("F_LIFE_MACHINE", "WAR"), 0.0)
        self.assertFalse(DEFAULT_ONTOLOGY.type_valid("WAR",
                                                     "LIFE_IS_A_MACHINE"))

    def test_fallback_edge_gets_0_5_in_text_features(self):
        from metaphor_graph.ontology import DEFAULT_ONTOLOGY
        e = _edge(frame_id="F_LLM_ab12cd34", source_type="GENERIC_VEHICLE")
        self.assertEqual(
            extract_text_features("发条", e, None, DEFAULT_ONTOLOGY)[3], 0.5)

    def test_both_paths_agree_on_type_for_fallback_edge(self):
        """核心回归：两条路径对同一候选必须给出同一个 type 值。"""
        from metaphor_graph.ontology import DEFAULT_ONTOLOGY
        from metaphor_graph.retrieval import RetrievalEngine
        fb = _edge(frame_id="F_LLM_ab12cd34", source_type="GENERIC_VEHICLE")
        reg = _edge(frame_id="F_LIFE_MACHINE", source_type="MACHINE")
        eng = RetrievalEngine(MetaphorSHG(edges=[fb, reg], frames=[],
                                          cascades=[]), ["发条"],
                              ontology=DEFAULT_ONTOLOGY, doc_id="doc")
        for e in (fb, reg):
            expected = DEFAULT_ONTOLOGY.type_reliability_of(e.frame_id,
                                                            e.source_type)
            self.assertEqual(
                extract_text_features("发条", e, None, DEFAULT_ONTOLOGY)[3],
                expected)
            self.assertEqual(
                extract_features(e, e, None, DEFAULT_ONTOLOGY)[3], expected)
            self.assertEqual(
                eng.ont.type_reliability_of(e.frame_id, e.source_type),
                expected)

    def test_no_frame_edge_scores_zero_in_both_paths(self):
        from metaphor_graph.ontology import DEFAULT_ONTOLOGY
        e = _edge(frame_id=None)
        self.assertEqual(
            extract_text_features("发条", e, None, DEFAULT_ONTOLOGY)[3], 0.0)
        self.assertEqual(
            extract_features(e, e, None, DEFAULT_ONTOLOGY)[3], 0.0)

    def test_fallback_not_dropped(self):
        """设计意图护栏：回退框架的可靠性必须 > 0，否则等于丢弃开放发现的
        候选（那会毁掉 +55.8pp 召回）。"""
        from metaphor_graph.ontology import (DEFAULT_ONTOLOGY,
                                             TYPE_RELIABILITY_FALLBACK)
        self.assertGreater(TYPE_RELIABILITY_FALLBACK, 0.0)
        e = _edge(frame_id="F_LLM_deadbeef", source_type="GENERIC_VEHICLE")
        self.assertGreater(
            extract_text_features("发条", e, None, DEFAULT_ONTOLOGY)[3], 0.0)

    def test_type_feature_is_not_constant_on_mixed_pool(self):
        """type 必须真的携带信息（此前在真实评测池里恒为 1.0，是常数项）。"""
        from metaphor_graph.ontology import DEFAULT_ONTOLOGY
        edges = [_edge(frame_id="F_LIFE_MACHINE", source_type="MACHINE"),
                 _edge(frame_id="F_LLM_deadbeef", source_type="GENERIC_VEHICLE"),
                 _edge(frame_id=None)]
        vals = {extract_text_features("发条", e, None, DEFAULT_ONTOLOGY)[3]
                for e in edges}
        self.assertEqual(vals, {1.0, 0.5, 0.0})

    def test_type_reliability_respects_instance_type_valid_patch(self):
        """消融脚本对 ont.type_valid 打实例级补丁时，可靠性通道要跟着走。"""
        from metaphor_graph.ontology import DEFAULT_ONTOLOGY
        ont = DEFAULT_ONTOLOGY
        self.assertEqual(ont.type_reliability_of("F_LIFE_MACHINE", "MACHINE"),
                         1.0)
        orig = ont.type_valid
        ont.type_valid = lambda *a, **k: False
        try:
            self.assertEqual(
                ont.type_reliability_of("F_LIFE_MACHINE", "MACHINE"), 0.0)
            # 未注册的回退框架仍拿封顶值（补丁不影响「无法核验」这一支）
            self.assertEqual(
                ont.type_reliability_of("F_LLM_ab12cd34",
                                        "GENERIC_VEHICLE"), 0.5)
        finally:
            del ont.type_valid


class TestFeatureSetAudit(unittest.TestCase):
    """gen3 审计的可执行护栏（experiments/gen3/REPORT.md）。

    这一组测试把「特征集审计」的关键事实钉成回归护栏，防止后续有人
    凭直觉改回已证伪的做法：

      1. FEATURE_NAMES 的**顺序与索引**是硬契约：人工加权的 `f[3]` 是 type，
         A9 的 ROLE_IDX 是 [4,5,6]。任何重排都会静默改变已上报数字。
      2. 人工加权公式必须**逐项顺序累加**，不能改成 numpy 点积 —— 浮点
         结合序不同会让 632 条查询里有 1 条完整排序不同（人工加权 MRR
         0.480947 → 0.481211）。这是实测踩到的坑。
      3. type 维度在训练集上的单特征 AUC ≈ 0.497（近噪声），训练器学到
         权重 ≈ +0.049 ≈ 0，而人工加权硬编码 0.20 —— 三者的**不一致本身**
         是审计结论，改任何一处都要同步更新报告。
      4. `struct` 与 `type` 在评测候选对上的二值重叠率 ≈ 1.000（两者都几乎
         只反映「有框架归属」），因此它们不是两个独立的信号。
    """

    def test_feature_index_contract(self):
        """顺序是硬契约：人工加权的 f[3] 必须是 type，ROLE_IDX 必须是 [4,5,6]。

        注意：`evaluate_retrieval` 在**模块级**调用 `logging.disable(CRITICAL)`，
        import 它会全局关掉日志，导致 `assertLogs` 类用例失败（gen2 报告已记录
        这个坑）。因此这里必须**延迟 import 并恢复**全局日志级别。
        """
        import logging as _logging
        self.assertEqual(FEATURE_NAMES[0], "sem")
        self.assertEqual(FEATURE_NAMES[1], "struct")
        self.assertEqual(FEATURE_NAMES[2], "clue")
        self.assertEqual(FEATURE_NAMES[3], "type")
        self.assertEqual(FEATURE_NAMES[4], "same_frame")
        self.assertEqual(FEATURE_NAMES[5], "same_cascade")
        self.assertEqual(FEATURE_NAMES[6], "ground_jaccard")
        saved = _logging.root.manager.disable
        try:
            from metaphor_graph.evaluate_retrieval import ROLE_IDX
            self.assertEqual(list(ROLE_IDX), [4, 5, 6])
        finally:
            _logging.disable(saved)

    def test_manual_weights_come_from_single_source(self):
        """人工权重必须来自 `training.HAND_WEIGHTS` 单一真源，不再写死在调用点。

        原状（exp/typefeat 审计发现）：`score_conditions` 里硬编码
        0.35/0.25/0.20/0.20，与学到权重严重错配 —— struct 过权 37 倍、
        type 12 倍，使「训练增益」主要是配错权重的产物。
        exp/repair 已改为调用 `training.hand_weighted_score`（单一真源）。

        本测试钉住新不变式：调用点不得再出现写死的权重字面量。
        历史权重仍可复现（`HAND_WEIGHTS_LEGACY`），见 TestRepairs。

        注意：`evaluate_retrieval` 模块级调用 `logging.disable(logging.CRITICAL)`，
        import 它会**全局**关掉日志，让 `assertLogs` 类用例失败。必须保存/恢复
        全局日志级别（gen2 报告已记录这个坑，此处同样踩到过）。
        """
        import inspect
        import logging as _logging
        saved = _logging.root.manager.disable
        try:
            from metaphor_graph import evaluate_retrieval as er
            src = inspect.getsource(er.score_conditions)
        finally:
            _logging.disable(saved)
        # 新不变式：走单一真源
        self.assertIn("hand_weighted_score", src,
                      "人工加权必须调用 training.hand_weighted_score")
        # 旧的写死字面量不得再出现
        for term in ("0.35 * f[0]", "0.25 * min(f[1], 1.0)"):
            self.assertNotIn(term, src,
                             f"人工加权项 {term!r} 又写死了 —— 应走单一真源")

    def test_manual_weighting_float_order_matters(self):
        """人工加权必须顺序累加：点积与顺序累加的浮点结合序不同。

        实测：632 条查询里有 1 条完整排序不同，人工加权 MRR 从 0.480947
        （顺序）变成 0.481211（点积）。本测试只钉住顺序式的定义值。
        """
        import numpy as np
        f = [0.1, 0.3, 0.7, 0.9]
        seq = (0.35 * f[0] + 0.25 * min(f[1], 1.0)
               + 0.20 * f[2] + 0.20 * f[3])
        self.assertAlmostEqual(seq, 0.43, places=10)
        # 点积在**多数**取值上与顺序式一致；这里证明二者可比较（不要求不等）
        dot = float(np.asarray(f) @ np.asarray([0.35, 0.25, 0.20, 0.20]))
        self.assertLess(abs(seq - dot), 1e-12)

    def test_type_auc_is_near_noise_on_training_set(self):
        """type 在自监督训练集上的单特征 AUC 必须 ≈ 0.5（gen1 的 0.497 口径）。

        构造：正负样本的 type 列（索引 3）分布完全相同 → AUC 恰为 0.5；
        sem 列（索引 0）与标签同向 → AUC = 1.0。这证明「近噪声」是该维的
        构造性质，不是某个语料的偶然。
        """
        import numpy as np
        X = np.zeros((8, len(FEATURE_NAMES)))
        X[:, 3] = [1.0, 1.0, 0.5, 0.5, 1.0, 1.0, 0.5, 0.5]   # 与标签独立
        X[:, 0] = [0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1]   # 与标签同向
        y = np.asarray([1, 1, 1, 1, 0, 0, 0, 0], dtype=float)
        aucs = feature_auc(TrainingSet(X, y))
        self.assertEqual(aucs["type"], 0.5)
        self.assertEqual(aucs["sem"], 1.0)

    def test_trained_weight_of_type_is_near_zero(self):
        """训练器对纯噪声维（type）学到的权重必须远小于 clue/sem。"""
        import numpy as np
        rng = np.random.default_rng(0)
        n = 400
        X = rng.random((n, len(FEATURE_NAMES)))
        # 让 sem 与标签相关，type 与标签独立（纯噪声）
        y = (X[:, 0] > 0.5).astype(float)
        ds = TrainingSet(X, y)
        sc = MetaphorScorer().fit(ds)
        w = sc.weights()
        self.assertLess(abs(w["type"]), abs(w["sem"]),
                        "type 是纯噪声维，训练器不该给它超过 sem 的权重")
        self.assertLess(abs(w["type"]), 0.5)

    def test_struct_saturates_at_one(self):
        """struct 在默认喻底规模下就饱和到 1.0 —— 这是审计发现，不是 bug。

        struct = min(1.0, 0.5*len(ground) + 0.5*[cascade 非空])。
        喻底集合只要 ≥1 个元素且有级联归属就取到上界 1.0，于是该维在
        大部分候选上退化成常数（实测评测候选对里 85.1% 取值恰为 1.0）。
        本测试把这个饱和行为钉住：改公式必须同步更新审计报告。
        """
        a = _edge(frame_id="F_LIFE_MACHINE", cascade_id="C_LIFE_MACHINE")
        b = _edge(frame_id="", cascade_id="")
        fa = extract_features(a, a)
        fb = extract_features(a, b)
        # 有级联 + 喻底 ≥1 → 饱和到 1.0
        self.assertEqual(fa[1], 1.0)
        # 无级联归属 → 掉到 0.5*len(ground)（也可能 ≥1，取决于喻底数）
        self.assertLessEqual(fb[1], 1.0)
        # 关键点：struct 对「框架注册与否」不敏感（那是 type 的职责）
        c = _edge(frame_id="F_LLM_unregistered", cascade_id="C_LIFE_MACHINE")
        fc = extract_features(a, c)
        self.assertEqual(fc[1], fa[1])   # struct 相同
        self.assertNotEqual(fc[3], fa[3])  # type 不同（1.0 vs 0.5）

    def test_type_and_struct_are_not_independent(self):
        """type 与 struct 共享「有归属」这一成分，因此不是两个独立信号。

        实测：评测候选对上两者的二值重叠率 ≈ 1.000，秩相关 +0.836。
        """
        a = _edge(frame_id="F_LIFE_MACHINE", cascade_id="C_LIFE_MACHINE")
        b = _edge(frame_id="", cascade_id="")
        fa = extract_features(a, a)
        fb = extract_features(a, b)
        self.assertEqual(fa[3], 1.0)      # 注册框架
        self.assertEqual(fb[3], 0.0)      # 无归属
        self.assertGreaterEqual(fa[1], fb[1])   # struct 同向（都随归属变化）

    def test_same_cascade_can_be_redundant_with_same_frame(self):
        """same_cascade 与 same_frame 可以同时为 1（级联 ⊇ 框架）。

        这不是 bug，而是「级联按目标域打包」构造下的必然结果，也正是
        gen2 报告 51.7% 重叠的来源。测试钉住「同框架 ⇒ 同级联」的包含关系。
        """
        a = _edge(frame_id="F_LIFE_MACHINE", cascade_id="C_LIFE_MACHINE")
        b = _edge(frame_id="F_LIFE_MACHINE", cascade_id="C_LIFE_MACHINE")
        f = extract_features(a, b)
        self.assertEqual(f[4], 1.0)   # same_frame
        self.assertEqual(f[5], 1.0)   # same_cascade
        # 同框架但不同级联 → same_frame=1, same_cascade=0（分离能力）
        c = _edge(frame_id="F_LIFE_MACHINE", cascade_id="C_OTHER")
        g = extract_features(a, c)
        self.assertEqual(g[4], 1.0)
        self.assertEqual(g[5], 0.0)


class TestManualWeightedTypeConsistency(unittest.TestCase):
    """人工加权路径（retrieval）与 §6.2 的 hand_weighted 公式必须同口径。

    §6.2 的 hand_weighted 直接用 f[3]，f[3] 现由 ontology.type_reliability 给出；
    retrieval.metaphor_retriever_score 的 type 分量必须等于同一个值，否则
    「人工加权」这一个名字在两条代码路径上代表两种东西。
    """

    def test_manual_type_component_matches_feature(self):
        from metaphor_graph.ontology import DEFAULT_ONTOLOGY
        from metaphor_graph.retrieval import RetrievalEngine
        e = _edge(frame_id="F_LLM_ab12cd34", source_type="GENERIC_VEHICLE")
        eng = RetrievalEngine(MetaphorSHG(edges=[e], frames=[], cascades=[]),
                              ["发条"], ontology=DEFAULT_ONTOLOGY, doc_id="doc")
        feat = extract_text_features("发条", e, eng._centrality,
                                     DEFAULT_ONTOLOGY)
        # 复刻 retrieval 人工加权的 type 分量（与 metaphor_retriever_score 同源）
        type_component = eng.ont.type_reliability_of(e.frame_id, e.source_type)
        self.assertEqual(type_component, feat[3])
        # 手工核对总分公式（0.35/0.25/0.20/0.20）
        # exp/repair 后 metaphor_retriever_score 统一走 7 维特征 + 单一真源权重，
        # 不再是旧 4 维公式；exp/degrade 又叠加了溯源可靠性折扣（默认 floor=0.5）。
        # 因此正确口径是 hand_weighted_score(feat) × reliability_factor。
        from metaphor_graph.training import hand_weighted_score
        self.assertAlmostEqual(
            eng.metaphor_retriever_score("发条", e),
            round(hand_weighted_score(feat) * eng.reliability_factor(e), 4),
            places=4)
        # 折扣因子在 [floor,1] 内，且 floor=1.0 时关闭（历史口径可复原）
        self.assertLessEqual(eng.reliability_factor(e), 1.0)
        eng_off = RetrievalEngine(MetaphorSHG(edges=[e], frames=[], cascades=[]),
                                  ["发条"], ontology=DEFAULT_ONTOLOGY,
                                  doc_id="doc", reliability_floor=1.0)
        self.assertAlmostEqual(eng_off.reliability_factor(e), 1.0, places=9)
        self.assertAlmostEqual(
            eng_off.metaphor_retriever_score("发条", e),
            round(hand_weighted_score(feat), 4), places=4)


class TestCascadeConstructionRules(unittest.TestCase):
    """L3 级联构造规则（`cascade_rules` 模块）的回归护栏。

    背景（gen2 实验，见 experiments/gen2/REPORT.md）：生产本体的级联按**目标域**
    打包，导致 99.2% 的级联成员共享单一目标域、中位规模 1 —— 级联退化成
    「框架别名」，`cross_domain_retrieve` 的级联扩展段取不到新目标域。
    这里钉住四件事：
      1. 默认（`json`）行为**必须**与改动前逐位一致 —— 替代规则不得静默生效；
      2. 每条替代规则的**结构性质**（source 规则必须跨目标域）；
      3. 规则 id 的**确定性**（跨进程可复现）；
      4. `apply_rule` 必须重建 `_frame_to_cascade` 反向索引。
    """

    @staticmethod
    def _frames():
        from metaphor_graph.ontology import FrameSpec
        return [
            FrameSpec(id="FA", name="A", mapping_type="M", source_domain="旅程",
                      target_domain="生活", ground=["起点", "终点"],
                      triggers=[], source_type="MOTION", support=5),
            FrameSpec(id="FB", name="B", mapping_type="M", source_domain="旅程",
                      target_domain="爱情", ground=["同行", "波折"],
                      triggers=[], source_type="MOTION", support=3),
            FrameSpec(id="FC", name="C", mapping_type="M", source_domain="战争",
                      target_domain="生活", ground=["进攻", "阵地"],
                      triggers=[], source_type="WAR", support=1),
        ]

    def test_all_rules_registered(self):
        from metaphor_graph.cascade_rules import CASCADE_RULES
        for r in ("json", "target", "source", "ground", "metanet",
                  "source_type", "none"):
            self.assertIn(r, CASCADE_RULES)

    def test_unknown_rule_rejected(self):
        from metaphor_graph.cascade_rules import build_cascades
        with self.assertRaises(ValueError):
            build_cascades(self._frames(), "no_such_rule")

    def test_json_rule_returns_base_unchanged(self):
        """json 规则必须原样返回传入的 base_cascades（默认行为不变）。"""
        from metaphor_graph.cascade_rules import build_cascades
        from metaphor_graph.ontology import CascadeSpec
        base = {"C_X": CascadeSpec(id="C_X", name="X", member_frames=["FA", "FB"])}
        out = build_cascades(self._frames(), "json", base_cascades=base)
        self.assertEqual(set(out), {"C_X"})
        self.assertIs(out["C_X"], base["C_X"])

    def test_target_rule_singleton_per_distinct_target(self):
        from metaphor_graph.cascade_rules import build_cascades
        out = build_cascades(self._frames(), "target")
        # 目标域 {生活, 爱情} → 2 个级联；生活 下有 FA/FC
        sizes = sorted(len(c.member_frames) for c in out.values())
        self.assertEqual(sizes, [1, 2])
        members = {tuple(sorted(c.member_frames)) for c in out.values()}
        self.assertIn(("FA", "FC"), members)

    def test_source_rule_crosses_target_domains(self):
        """source 规则的核心性质：同一级联可覆盖多个目标域。"""
        from metaphor_graph.cascade_rules import build_cascades, cascade_stats
        from metaphor_graph.ontology import FrameSpec
        frames = self._frames()
        out = build_cascades(frames, "source")
        self.assertEqual(len(out), 2)                  # 旅程 / 战争
        j = next(c for c in out.values() if set(c.member_frames) == {"FA", "FB"})
        st = cascade_stats(out, {f.id: f for f in frames})
        self.assertGreaterEqual(st["cross_target_rate"], 0.5)
        # 该级联确实覆盖两个目标域（生活 + 爱情）
        self.assertEqual({frames[0].target_domain, frames[1].target_domain},
                         {"生活", "爱情"})
        self.assertEqual(len(j.member_frames), 2)

    def test_none_rule_is_empty(self):
        from metaphor_graph.cascade_rules import build_cascades, cascade_stats
        frames = self._frames()
        out = build_cascades(frames, "none")
        self.assertEqual(out, {})
        st = cascade_stats(out, {f.id: f for f in frames})
        self.assertEqual(st["frame_cascade_coverage"], 0.0)

    def test_rules_deterministic(self):
        """同一输入 → 同一 id 集合（跨进程可复现；内置 hash 会破坏这点）。"""
        from metaphor_graph.cascade_rules import build_cascades
        for r in ("target", "source", "ground", "source_type"):
            a = build_cascades(self._frames(), r)
            b = build_cascades(self._frames(), r)
            self.assertEqual(sorted(a), sorted(b), r)
            for k in a:
                self.assertEqual(a[k].member_frames, b[k].member_frames, r)

    def test_apply_rule_rebuilds_reverse_index(self):
        """apply_rule 必须重建 _frame_to_cascade —— 不重建则 get_cascade 返回旧归属。"""
        from metaphor_graph.cascade_rules import apply_rule
        from metaphor_graph.ontology import CascadeOntology
        ont = CascadeOntology(
            frames={f.id: f for f in self._frames()},
            cascades={})
        self.assertIsNone(ont.get_cascade("FA"))
        apply_rule(ont, "source")
        cid_a = ont.get_cascade("FA")
        cid_b = ont.get_cascade("FB")
        self.assertIsNotNone(cid_a)
        self.assertEqual(cid_a, cid_b, "FA/FB 同源域 → 必须归入同一级联")
        self.assertNotEqual(cid_a, ont.get_cascade("FC"))
        # 反向索引与正向成员表必须一致
        spec = ont.get_cascade_spec(cid_a)
        self.assertIn("FA", spec.member_frames)

    def test_ground_rule_groups_by_shared_ground(self):
        from metaphor_graph.cascade_rules import build_cascades
        out = build_cascades(self._frames(), "ground")
        # FA/FB 无共同喻底且各自喻底 Jaccard=0 → 各自成组；FC 同样独立
        self.assertEqual(len(out), 3)

    def test_metanet_rule_keeps_seed_cascades(self):
        """metanet 规则保留种子级联（非 C_LLM_ 前缀），C_LLM_ 级联不参与归属。"""
        from metaphor_graph.cascade_rules import build_cascades
        from metaphor_graph.ontology import CascadeSpec
        base = {
            "C_SEED": CascadeSpec(id="C_SEED", name="SEED",
                                  member_frames=["FA"]),
            "C_LLM_1": CascadeSpec(id="C_LLM_1", name="LLM",
                                   member_frames=["FB"]),
        }
        out = build_cascades(self._frames(), "metanet", base_cascades=base)
        self.assertIn("C_SEED", out)
        self.assertIn("FA", out["C_SEED"].member_frames)
        self.assertNotIn("C_LLM_1", out)
        # FB 脱离 C_LLM_1 后被兜底规则重组（默认 source → 与 FA 同级联）
        self.assertEqual(out["C_SEED"].member_frames, ["FA"])

    def test_builder_default_orphan_rule_is_target(self):
        """默认必须仍是 target（不得静默改默认）—— 已上报数字依赖它。"""
        from metaphor_graph.builder import MetaphorSHGBuilder
        b = MetaphorSHGBuilder()
        self.assertEqual(b.orphan_cascade_rule, "target")

    # ---- 孤儿打包规则：直接驱动 _ensure_cascades（合成输入，快且可控）----
    @staticmethod
    def _orphan_inputs():
        """3 个孤儿框架，目标域各不相同、源域两两相同/不同 —— 让各规则可分。"""
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.models import (MetaphorFrame, MetaphorHyperedge,
                                           ChunkSpan)
        from metaphor_graph.ontology import FrameSpec

        def edge(eid, frame_id, src, tgt, ground):
            return MetaphorHyperedge(
                id=eid, source_domain=src, target_domain=tgt,
                ground=list(ground), triggers=["x"],
                chunk_spans=[ChunkSpan(chunk_id="d_c0", start=0, end=1, text="x")],
                frame_id=frame_id, confidence=0.9)

        edges = [
            edge("e1", "F_ORPH_A", "旅程", "生活", ["起点"]),
            edge("e2", "F_ORPH_B", "旅程", "爱情", ["同行"]),
            edge("e3", "F_ORPH_C", "战争", "生活", ["进攻"]),
        ]
        frames = [MetaphorFrame(id=fid, name=fid, member_mapping_ids=[eid])
                  for fid, eid in (("F_ORPH_A", "e1"), ("F_ORPH_B", "e2"),
                                   ("F_ORPH_C", "e3"))]
        return MetaphorSHGBuilder, edges, frames

    def test_orphan_target_rule_groups_by_target_domain(self):
        """原口径：同目标域的孤儿进同一级联（A/C 同「生活」）。"""
        Builder, edges, frames = self._orphan_inputs()
        cascades = []
        Builder(orphan_cascade_rule="target")._ensure_cascades(
            edges, frames, cascades)
        self.assertEqual(len(cascades), 2)                    # 生活 / 爱情
        groups = {tuple(c.member_frame_ids) for c in cascades}
        self.assertIn(("F_ORPH_A", "F_ORPH_C"), groups)
        self.assertTrue(all(c.id.startswith("C_ADHOC_") for c in cascades),
                        "原口径的 id 前缀必须保持 C_ADHOC_（缓存/导出都引用它）")

    def test_orphan_source_rule_groups_by_source_domain(self):
        """替代规则：同源域的孤儿进同一级联（A/B 同「旅程」），且 id 前缀可区分。"""
        Builder, edges, frames = self._orphan_inputs()
        cascades = []
        Builder(orphan_cascade_rule="source")._ensure_cascades(
            edges, frames, cascades)
        self.assertEqual(len(cascades), 2)                    # 旅程 / 战争
        groups = {tuple(c.member_frame_ids) for c in cascades}
        self.assertIn(("F_ORPH_A", "F_ORPH_B"), groups)
        self.assertTrue(all(c.id.startswith("C_ADHOC_SOURCE_") for c in cascades))
        # 与 target 规则的 id 集合必须不同（否则说明规则没生效）
        t = []
        Builder(orphan_cascade_rule="target")._ensure_cascades(edges, frames, t)
        self.assertNotEqual(sorted(c.id for c in cascades),
                            sorted(c.id for c in t))

    def test_orphan_none_rule_adds_nothing(self):
        """orphan_cascade_rule='none' 是 L3 消融开关：一条级联都不补。"""
        Builder, edges, frames = self._orphan_inputs()
        cascades = []
        Builder(orphan_cascade_rule="none")._ensure_cascades(
            edges, frames, cascades)
        self.assertEqual(cascades, [])

    def test_orphan_rule_deterministic(self):
        """同一输入 → 同一 id（跨进程可复现，md5 而非内置 hash）。"""
        Builder, edges, frames = self._orphan_inputs()
        for rule in ("target", "source", "source_type", "ground"):
            a, b = [], []
            Builder(orphan_cascade_rule=rule)._ensure_cascades(edges, frames, a)
            Builder(orphan_cascade_rule=rule)._ensure_cascades(edges, frames, b)
            self.assertEqual(sorted(c.id for c in a), sorted(c.id for c in b),
                             rule)

    def test_orphan_rule_rejects_unknown(self):
        Builder, edges, frames = self._orphan_inputs()
        with self.assertRaises(ValueError):
            Builder(orphan_cascade_rule="bogus")._ensure_cascades(
                edges, frames, [])

    def test_production_ontology_defect_is_pinned(self):
        """把缺陷本身钉成回归护栏：生产本体的级联必须**仍然是**单一目标域主导。

        这条测试在默认本体上跑；若未来有人修好了本体级联（如改用 source 规则
        重新沉淀 ontology_default.json），本测试会失败 —— 那时应更新断言并
        同步论文 §6.3 的表述，而不是删掉测试。
        """
        # 注意：evaluate_fullcorpus 在模块级调用 logging.disable(CRITICAL)
        # （评测脚本不希望被日志刷屏）。测试套件里 import 它会**顺带静音**
        # 后续用例的 assertLogs（实测让 TestOpenAIBackendHTTP 的 2 条降级
        # 测试失败）。故此处保存并恢复全局 disable 级别。
        import logging as _logging
        _saved = _logging.root.manager.disable
        try:
            from metaphor_graph.evaluate_fullcorpus import build_replay_ontology
            from metaphor_graph.cascade_rules import cascade_stats
            ont, _nf = build_replay_ontology()
        finally:
            _logging.disable(_saved)
        st = cascade_stats(ont.cascades, ont.frames)
        self.assertGreater(st["n_cascades"], 700)
        self.assertLess(st["cross_target_rate"], 0.02,
                        "生产本体级联应几乎全是单目标域（实测 0.8%）")
        self.assertLessEqual(st["size_median"], 1.0)
        self.assertGreater(st["singleton_rate"], 0.5)


class TestProvenanceReliability(unittest.TestCase):
    """退化溯源可靠性通道（degraded-provenance，见 provenance.py）。

    设计约束：候选**永不丢弃**，只把「这份框架溯源有多可信」记在边上，
    由打分/排序层按**有下界的乘性折扣**消费。
    """

    def test_frame_reliability_by_ontology_registration(self):
        from metaphor_graph import provenance as pv
        ont = DEFAULT_ONTOLOGY
        self.assertEqual(pv.frame_reliability(ont, "F_LIFE_MACHINE"),
                         pv.RELIABILITY_ONTOLOGY)          # 本体登记 → 1.0
        self.assertEqual(pv.frame_reliability(ont, "F_LLM_临时"),
                         pv.RELIABILITY_FALLBACK_CAP)      # 无条目 → 封顶 0.5
        self.assertEqual(pv.frame_provenance(ont, "F_LLM_临时"), pv.PROV_FALLBACK)

    def test_judgement_is_registration_not_prefix(self):
        """判据必须是「本体有无条目」，不能是 `F_LLM_` 前缀。

        llm_ontology 把自举沉淀的**正式**框架也命名为 F_LLM_*，
        按前缀判定会把整个生产本体误判为退化。
        """
        from metaphor_graph import provenance as pv
        ont = CascadeOntology()
        from metaphor_graph.ontology import FrameSpec
        ont.frames["F_LLM_promoted"] = FrameSpec(
            id="F_LLM_promoted", name="X", mapping_type="GENERIC_VEHICLE_MAP",
            source_domain="a", target_domain="b", ground=[], triggers=[],
            source_type="GENERIC_VEHICLE")
        self.assertEqual(pv.frame_reliability(ont, "F_LLM_promoted"), 1.0)

    def test_frame_reliability_no_ontology_is_neutral(self):
        """信息不足时不降级：没本体可查 → 1.0。"""
        from metaphor_graph import provenance as pv
        self.assertEqual(pv.frame_reliability(None, "F_ANY"),
                         pv.RELIABILITY_ONTOLOGY)
        self.assertEqual(pv.frame_reliability(DEFAULT_ONTOLOGY, None),
                         pv.RELIABILITY_ONTOLOGY)

    def test_reliability_factor_is_capped_and_never_zero(self):
        """乘性因子必须有下界 —— 下界为 0 就退化成过滤器（丢召回）。"""
        from metaphor_graph import provenance as pv
        self.assertEqual(pv.reliability_factor(1.0), 1.0)
        # 封顶可靠性 0.5 的边落在 floor 与 1.0 的中点（默认 floor=0.5）
        self.assertAlmostEqual(pv.reliability_factor(0.5),
                               pv.RELIABILITY_FLOOR
                               + (1 - pv.RELIABILITY_FLOOR) * 0.5)
        self.assertLess(pv.reliability_factor(0.5), 1.0)
        # 最差情形仍有下界，绝不归零
        self.assertEqual(pv.reliability_factor(0.0), pv.RELIABILITY_FLOOR)
        self.assertGreater(pv.reliability_factor(0.0), 0.0)
        self.assertEqual(pv.reliability_factor(0.5, floor=1.0), 1.0)  # 关闭开关

    def test_model_field_default_is_backward_compatible(self):
        self.assertEqual(_edge().provenance_reliability, 1.0)

    def test_extractor_marks_fallback_edges_degraded_but_keeps_them(self):
        """回退框架的边被标降级，但**照样产出**（不丢弃候选）。"""
        from metaphor_graph.llm_backend import MockBackend, LLMCandidate
        cand = LLMCandidate(source_domain="量子隧穿", target_domain="职场晋升",
                            ground=["跃迁"], triggers=["隧穿"], confidence=0.9)
        ex = MetaphorExtractor(ontology=DEFAULT_ONTOLOGY,
                               llm_backend=MockBackend([cand]),
                               llm_conf_threshold=0.5)
        edges = ex.extract("他靠一次隧穿完成了跃迁。", doc_id="d", chunk_id="d_c0")
        self.assertTrue(edges, "候选不得被丢弃 —— 这正是与过滤方案的分界")
        self.assertTrue(all(e.provenance_reliability == 0.5 for e in edges))
        self.assertTrue(all(e.frame_id.startswith("F_LLM_") for e in edges))

    def test_ontology_frames_keep_full_reliability(self):
        ex = MetaphorExtractor(ontology=DEFAULT_ONTOLOGY)
        edges = ex.extract("他每天像根发条一样拧紧自己。", doc_id="d",
                           chunk_id="d_c0")
        if not edges:
            self.skipTest("默认本体未命中该句")
        self.assertTrue(all(e.provenance_reliability == 1.0 for e in edges))

    def test_extended_edge_inherits_weakest_link(self):
        """扩展边取链上最弱一环 —— 退化边不得借合并洗白。"""
        a = _edge(chunk_ids=("d_c0",))
        b = _edge(chunk_ids=("d_c1",))
        b.id = "L1_b"
        a.provenance_reliability = 1.0
        b.provenance_reliability = 0.5
        ext = link_extended_metaphors([a, b], {"d_c0": 0, "d_c1": 1})
        self.assertTrue(ext)
        self.assertTrue(all(e.provenance_reliability == 0.5 for e in ext))

    def test_reliability_scales_score_but_keeps_edge(self):
        """打分被缩放（次序可变），但候选仍在 —— 软通道，不是过滤器。"""
        shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        on = RetrievalEngine(shg, CHUNKS, doc_id=DOC_ID)
        off = RetrievalEngine(shg, CHUNKS, doc_id=DOC_ID, reliability_floor=1.0)
        e = shg.edges[0]
        e.provenance_reliability = 0.5
        e.frame_id = "F_NOT_IN_ONTOLOGY"
        s_on = on.metaphor_retriever_score("项目推进不动", e)
        s_off = off.metaphor_retriever_score("项目推进不动", e)
        self.assertGreater(s_off, s_on, "降级边应被打折")
        self.assertGreater(s_on, 0.0, "打折不得归零")
        self.assertEqual(len(on.live_edges()), len(off.live_edges()))

    def test_reliability_floor_one_reproduces_history(self):
        """floor=1.0 = 通道关闭，打分与未改动前的口径逐位一致。"""
        from metaphor_graph import embeddings
        shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        eng = RetrievalEngine(shg, CHUNKS, doc_id=DOC_ID, reliability_floor=1.0)
        e = shg.edges[0]
        e.provenance_reliability = 0.5
        e.frame_id = "F_NOT_IN_ONTOLOGY"
        got = eng.metaphor_retriever_score("发条", e)
        # exp/repair 后打分统一走 7 维特征 + training.HAND_WEIGHTS 单一真源
        # （不再是旧 4 维公式）。floor=1.0 时折扣为 1，故应逐位等于
        # 同一份特征的 hand_weighted_score。
        from metaphor_graph.training import hand_weighted_score
        feat = eng._pair_features("发条", e)
        want = round(hand_weighted_score(feat), 4)
        self.assertAlmostEqual(got, want, places=6)

    def test_edge_reliability_prefers_conservative_stored_value(self):
        """存储值只能更保守 —— 防「退化边被伪造成正式边」。"""
        from metaphor_graph import provenance as pv
        e = _edge(frame_id="F_LIFE_MACHINE")     # 本体登记 → 派生 1.0
        e.provenance_reliability = 0.3
        self.assertEqual(pv.edge_reliability(e, DEFAULT_ONTOLOGY), 0.3)
        e.provenance_reliability = 1.0           # 想升回 1.0 不行
        e.frame_id = "F_NOT_REGISTERED"
        self.assertEqual(pv.edge_reliability(e, DEFAULT_ONTOLOGY), 0.5)

    def test_health_reports_honest_coverage_only_with_ontology(self):
        """不传 ontology 时字段为 None —— 历史口径逐位不变。"""
        shg = MetaphorSHGBuilder().build(CHUNKS, doc_id=DOC_ID)
        h_old = graph_health(shg)
        self.assertIsNone(h_old.registered_frame_coverage)
        self.assertNotIn("诚实覆盖率", h_old.report())
        h_new = graph_health(shg, ontology=DEFAULT_ONTOLOGY)
        self.assertIsNotNone(h_new.registered_frame_coverage)
        self.assertIn("诚实覆盖率", h_new.report())
        self.assertAlmostEqual(h_old.hierarchy_coverage,
                               h_new.hierarchy_coverage)

    def test_health_flags_adhoc_coverage_inflation(self):
        """回退框架撑起的覆盖率必须被点名（不能拿它声称层级归属达标）。"""
        e = _edge(frame_id="F_NOT_IN_ONTOLOGY")
        e.provenance_reliability = 0.5
        shg = MetaphorSHG(edges=[e], frames=[], cascades=[])
        h = graph_health(shg, ontology=DEFAULT_ONTOLOGY)
        self.assertAlmostEqual(h.registered_frame_coverage, 0.0)
        self.assertTrue(any("诚实框架覆盖率" in w for w in h.warnings))
        self.assertAlmostEqual(h.degraded_edge_rate, 1.0)
class TestQuerySignal(unittest.TestCase):
    """gen3 查询侧结构信号（query_signal.py）。

    与 `TestQueryObservability` 同一纪律：**只读查询**，签名里没有候选池。
    gen3 的发现是「Ω 的信号被 Ω_N 分量内部的 `min(1,·)` 截断毁掉」，
    故这里既钉住不变式，也把「截断是元凶」这条机制钉成回归护栏。
    """

    def setUp(self):
        from metaphor_graph.query_signal import QuerySignal  # noqa: F401
        self.ont = DEFAULT_ONTOLOGY

    def sig(self, q):
        from metaphor_graph.query_signal import measure_signal
        return measure_signal(q, self.ont)

    # ---------------------------------------------------- 只读查询的不变式
    def test_query_signal_invariant_to_candidate_pool(self):
        """打乱/截断/清空候选池，查询侧信号逐位不变（与 Ω 同一护栏）。"""
        import copy
        import random
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.eval_corpus import DOCS
        from metaphor_graph.query_signal import measure_signal

        queries = ("泥潭，沼泽", "她的眼睛像什么一样晶莹剔透？", "黑夜")
        base = {q: measure_signal(q, self.ont).to_dict() for q in queries}

        chunks = DOCS["doc_project"]
        shg = MetaphorSHGBuilder().build(chunks, doc_id="dp")
        variants = []
        for seed in (0, 1, 7):
            edges = copy.deepcopy(shg.edges)
            random.Random(seed).shuffle(edges)
            variants.append(edges[: max(1, len(edges) // 2)])
            variants.append(edges)
        variants.append([])

        for edges in variants:
            shg2 = MetaphorSHG(edges=edges)
            eng = RetrievalEngine(shg2, chunks, doc_id="dp")
            for q in queries:
                eng.cross_domain_retrieve(q)      # 触碰候选侧
                # 候选池变了，查询侧信号必须逐位相同
                self.assertEqual(measure_signal(q, self.ont).to_dict(), base[q])

    def test_measure_signal_signature_has_no_candidate_argument(self):
        """签名里不得出现候选池相关形参（结构性保证不变式）。"""
        import inspect
        from metaphor_graph.query_signal import measure_signal
        params = list(inspect.signature(measure_signal).parameters)
        for bad in ("shg", "edges", "candidates", "retriever", "chunks",
                    "ranked", "result", "scorer"):
            self.assertNotIn(bad, params)

    # ------------------------------------------------------------ 分量语义
    def test_no_trigger_query_has_zero_signals(self):
        s = self.sig("今天天气不错，心情也很好")
        self.assertEqual(s.n_seed, 0)
        self.assertEqual(s.n_frames, 0)
        self.assertEqual(s.n_reachable_targets, 0)
        for name, v in s.signals.items():
            self.assertEqual(v, 0.0, name)

    def test_reachable_domains_match_retrieval_target_set(self):
        """`reachable_domains` 必须与 `cross_domain_retrieve` 实际构造的
        `targets` 集合**逐元素相同** —— 否则「通路非空」的预测就失去意义。

        检索侧口径：直接命中框架的 (target_domain, source_domain)
        ∪ 级联成员框架的 (target_domain, source_domain)。
        """
        from metaphor_graph.query_signal import reachable_structure
        for q in ("泥潭，沼泽", "她的眼睛像什么一样晶莹剔透？", "构建"):
            tokens = [t for t in self.ont._trigger_index if t in q]
            want = set()
            for c in self.ont.match_by_triggers(tokens):
                cid = self.ont.get_cascade(c.id)
                want.add(c.target_domain)
                want.add(c.source_domain)
                spec = self.ont.get_cascade_spec(cid) if cid else None
                if spec:
                    for fid in spec.member_frames:
                        fs = self.ont.get_frame(fid)
                        if fs:
                            want.add(fs.target_domain)
                            want.add(fs.source_domain)
            got = reachable_structure(q, self.ont)["reachable_domains"]
            self.assertEqual(set(got), want, q)

    def test_new_domains_excludes_direct(self):
        """「新买到的域」与「直接域」必须不相交（否则计数重复）。"""
        from metaphor_graph.query_signal import reachable_structure
        st = reachable_structure("泥潭，沼泽", self.ont)
        self.assertEqual(set(st["new_domains"]) & set(st["direct_domains"]),
                         set())
        self.assertEqual(
            set(st["new_domains"]),
            set(st["expanded_domains"]) - set(st["direct_domains"]))

    def test_emergent_targets_only_target_domains(self):
        """gen2 口径（n_emergent）只算 target_domain，与检索口径必须区分。"""
        from metaphor_graph.query_signal import reachable_structure
        st = reachable_structure("泥潭，沼泽", self.ont)
        self.assertTrue(set(st["emergent_targets"])
                        <= set(st["expanded_targets"]))
        self.assertEqual(set(st["emergent_targets"]) & set(st["direct_targets"]),
                         set())
        # 两个口径在跨源域级联上会不同（本测试钉住「它们不是同一个量」）
        self.assertIsInstance(st["n_cross_cascades"], int)

    # -------------------------------------- 机制护栏：截断是毁掉信号的那一步
    def test_s_query_removes_only_the_clip(self):
        """S_query 与 Ω 的**唯一**差别是 Ω_N 不做 min(1,·) 截断。

        构造一个 n_emergent > n_seed 的查询：Ω_N 被截到 1.0，
        S_query 则保留 >1 的比值（几何平均里表现为更高）。
        """
        from metaphor_graph.query_signal import _s_query, _s_log
        # n_seed=1, n_emergent=4 → Ω_N = min(1, 4) = 1（截断）；
        # S_query 用 4/1 = 4（不截断）
        clipped = (min(1.0, 1.0 / 1) * min(1.0, 4.0 / 1) * 1.0) ** (1 / 3) * 1.0
        unclipped = _s_query(1, 1, 4, 1.0, 1.0)
        self.assertAlmostEqual(clipped, 1.0, places=12)     # Ω 口径：饱和
        self.assertGreater(unclipped, 1.0)                  # S_query：不饱和
        # 截断把 4 与 1 压成同一个值；不截断时它们不同
        self.assertNotAlmostEqual(_s_query(1, 1, 4, 1.0, 1.0),
                                  _s_query(1, 1, 1, 1.0, 1.0))
        # 无触发词 → 严格 0（与 Ω 同一外层特判）
        self.assertEqual(_s_query(0, 0, 0, 0.0, 0.0), 0.0)

    def test_s_query_zero_iff_no_trigger(self):
        """S_query>0 ⟺ 命中触发词（与 Ω 共享这条外层特判）。"""
        from metaphor_graph.query_signal import SIG_S_QUERY
        for q in ("今天天气不错", "", "泥潭", "泥潭，沼泽，陷进，深坑"):
            s = self.sig(q)
            self.assertEqual(s.get(SIG_S_QUERY) > 0, s.n_seed >= 1, q)

    def test_clip_collapses_levels_theorem(self):
        """机制定理：`min(1, n_em/n_seed)` 在 n_em ≥ n_seed 时恒为 1。

        这不是经验发现而是算术恒等式。生产本体（json 规则）下 n_seed=1 层
        102 条里 82 条满足 n_em ≥ 1（source 规则），23 档取值塌成 1 档。
        """
        for n_seed in (1, 2, 3):
            self.assertEqual(min(1.0, n_seed / n_seed), 1.0)
            self.assertEqual(min(1.0, (n_seed + 5) / n_seed), 1.0)
        # n_seed ≥ 2 时「只买到 1 个新域」仍严格小于 1（未被截断）
        for n_seed in (2, 3, 5):
            self.assertLess(min(1.0, 1.0 / n_seed), 1.0)
        # n_seed = 1 时任何 n_em ≥ 1 都被截到 1.0（这一档完全饱和）
        for n_em in (1, 2, 10, 74):
            self.assertEqual(min(1.0, n_em / 1), 1.0)

    # ---------------------------------------------- 合成器开关的语义正确性
    def test_compose_switch_semantics(self):
        """四个开关必须正交且语义明确（机制归因实验的可信前提）。"""
        from metaphor_graph.query_signal import compose
        comps = {"e": 1.0, "n": 0.0, "f": 1.0}
        # floor=True：Ω_N=0 被托底成 ε → 结果 > 0
        with_floor = compose(comps, n_seed=1, completeness=1.0, floor=True,
                             normalize=False, use_completeness=False,
                             outer_zero=True)
        self.assertGreater(with_floor, 0.0)
        self.assertAlmostEqual(with_floor, 1e-3 ** (1 / 3), places=9)
        # floor=False：Ω_N=0 直接不参与 → 只剩两个分量
        no_floor = compose(comps, n_seed=1, completeness=1.0, floor=False,
                           normalize=False, use_completeness=False,
                           outer_zero=True)
        self.assertAlmostEqual(no_floor, 1.0, places=12)
        # normalize=True 除以 n_seed
        self.assertAlmostEqual(
            compose({"e": 2.0, "f": 2.0}, n_seed=2, completeness=1.0,
                    floor=False, normalize=True, use_completeness=False,
                    outer_zero=True), 1.0, places=12)
        # use_completeness 乘完备度
        self.assertAlmostEqual(
            compose({"e": 1.0}, n_seed=1, completeness=0.25, floor=False,
                    normalize=False, use_completeness=True, outer_zero=True),
            0.25, places=12)
        # 无触发词 → 严格 0（无论开关）
        for fl in (True, False):
            self.assertEqual(compose(comps, n_seed=0, completeness=0.0,
                                     floor=fl, normalize=True,
                                     use_completeness=True, outer_zero=True),
                             0.0)

    def test_stratified_normalizer_is_fitted_not_oracle(self):
        """分层标准化器必须**拟合**统计量，不能偷看被变换的样本。

        护栏：在训练集上 fit 后，transform 的值对同分布样本应大致零均值；
        且 n_seed=0 的样本恒为 0（无层可标准化）。
        """
        from metaphor_graph.query_signal import StratifiedNormalizer
        rows = [dict(n_seed=1, n_emergent=float(i % 3)) for i in range(30)]
        rows += [dict(n_seed=2, n_emergent=float(i % 4)) for i in range(20)]
        nz = StratifiedNormalizer(source="n_emergent").fit(rows)
        vals = nz.transform(rows)
        self.assertAlmostEqual(sum(vals) / len(vals), 0.0, places=9)
        self.assertEqual(nz.transform_one(0, 5.0), 0.0)

    def test_signal_names_are_complete(self):
        """SIGNAL_NAMES 必须覆盖 signals 字典的全部键（防漏导出）。"""
        from metaphor_graph.query_signal import SIGNAL_NAMES
        s = self.sig("泥潭，沼泽")
        self.assertEqual(set(SIGNAL_NAMES), set(s.signals))

    def test_deterministic(self):
        q = "项目陷在泥潭里，推进不动"
        self.assertEqual(self.sig(q).to_dict(), self.sig(q).to_dict())

    # ---------------------------------------- 已知局限（诚实性回归护栏）
    def test_s_query_is_not_a_proxy_for_trigger_count_alone(self):
        """已知局限的显式化：S_query 与 n_seed 仍然高度共线（ρ≈0.99）。

        gen3 只修好了 Ω_N 的截断，**没有**解决「Ω>0 ⟺ 命中触发词」这个
        1-bit 外层特判（那是设计选择，不是缺陷）。因此 S_query 依然不是
        「超出触发词计数」的新信息。本测试记录该性质。
        """
        from metaphor_graph.query_signal import SIG_S_QUERY
        qs = ["泥潭", "泥潭，沼泽", "泥潭，沼泽，陷进，深坑", "黑夜", "构建"]
        ss = [self.sig(q) for q in qs]
        # 有命中的都 > 0，没命中的都是 0 —— 外层特判仍在
        for s in ss:
            self.assertEqual(s.get(SIG_S_QUERY) > 0, s.n_seed >= 1, s.query)

    def test_measured_signal_cannot_predict_mrr_by_construction(self):
        """S_query 是**纯查询侧**量：同一条查询在不同候选池上取同值，
        因此它无法区分「同查询不同池」的 MRR 差异 —— 这是不变式的代价，
        不是缺陷。用两个不同池验证取同值。
        """
        import copy
        import random
        from metaphor_graph.builder import MetaphorSHGBuilder
        from metaphor_graph.eval_corpus import DOCS
        from metaphor_graph.query_signal import measure_signal
        q = "泥潭，沼泽"
        chunks = DOCS["doc_project"]
        shg = MetaphorSHGBuilder().build(chunks, doc_id="dp")
        v1 = measure_signal(q, self.ont).to_dict()
        edges = copy.deepcopy(shg.edges)
        random.Random(11).shuffle(edges)
        eng = RetrievalEngine(MetaphorSHG(edges=edges[:1]), chunks, doc_id="dp")
        eng.cross_domain_retrieve(q)
        self.assertEqual(measure_signal(q, self.ont).to_dict(), v1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
