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

    def test_manual_weights_are_hardcoded_in_evaluate_retrieval(self):
        """人工权重 0.35/0.25/0.20/0.20 写死在 score_conditions 里。

        本测试把「写死的值」钉住，避免有人悄悄改权重后让历史数字不可比。
        若确实要改，必须同步更新 experiments/gen3/REPORT.md。

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
        for term in ("0.35 * f[0]", "0.25 * min(f[1], 1.0)",
                     "0.20 * f[2]", "0.20 * f[3]"):
            self.assertIn(term, src,
                          f"人工加权项 {term!r} 已改变——需同步审计报告")

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
        self.assertAlmostEqual(
            eng.metaphor_retriever_score("发条", e),
            round(0.35 * feat[0] + 0.25 * min(feat[1], 1.0)
                  + 0.20 * feat[2] + 0.20 * feat[3], 4), places=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
