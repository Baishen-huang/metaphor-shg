# -*- coding: utf-8 -*-
"""LLM 后端接入演示（方案 §6.6）。

三种模式，均可在 `E:\\02_AI项目\\元图隐喻分析` 下直接跑：

    python -m metaphor_graph.demo_llm
        离线模式（默认）：用 LocalHeuristicBackend，无需密钥即可跑通全链路。

    python -m metaphor_graph.demo_llm --mock-server
        **端到端验证真实 HTTP 通路**：本地起一个假的 OpenAI 兼容端点，
        让 OpenAIBackend 真的发一次 HTTP 请求、解析响应、产出抽取结果。
        不需要任何真实密钥，用于证明「接真模型」这条链路是通的。

    LLM_API_KEY=sk-xxx LLM_BASE_URL=https://api.openai.com/v1 \\
    LLM_MODEL=gpt-4o-mini python -m metaphor_graph.demo_llm
        真实大模型模式：调用你自己的 OpenAI 兼容端点（OpenAI / DeepSeek / 通义 /
        本地 vLLM / Ollama 均可）。
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaphor_graph import MetaphorSHGBuilder  # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor  # noqa: E402
from metaphor_graph.llm_backend import (  # noqa: E402
    LocalHeuristicBackend, OpenAIBackend, MockBackend, LLMCandidate, LLMRefine,
)

SAMPLES = [
    "社会就是个大舞台，人人都在演自己的角色。",
    "他像一只老虎一样凶猛，我们都躲着他。",
    "这个项目现在陷在泥潭里，每前进一步都要拔出腿来。",
    "苹果发布了新手机，屏幕比上一代更大。",          # 字面，不应判为隐喻
    "朱元璋是明朝的开国皇帝。",                      # 身份判断句，不应判为隐喻
]


def banner(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


def show(backend, name):
    banner(f"抽取结果 —— {name}")
    ex = MetaphorExtractor(llm_backend=backend, use_semfield=True)
    total = 0
    for s in SAMPLES:
        edges = ex.extract(s, doc_id="demo", chunk_id="c")
        total += len(edges)
        tag = "隐喻" if edges else "—"
        print(f"\n  [{tag}] {s}")
        for e in edges:
            spans = [sp.text for sp in e.chunk_spans]
            print(f"        {e.source_domain} → {e.target_domain}"
                  f"   喻底={e.ground}  触发={e.triggers}{spans}"
                  f"  frame={e.frame_id}  conf={e.confidence}")
    print(f"\n  合计产出 {total} 条 L1 超边（其中字面句应产出 0 条）")
    return ex


# ---------------------------------------------------------------------------
# 本地假端点：用于端到端验证 OpenAIBackend 的真实 HTTP 通路
# ---------------------------------------------------------------------------
_MOCK_REPLY = [
    {"source_domain": "漩涡", "target_domain": "舆论",
     "ground": ["裹挟", "无法自拔"], "triggers": ["漩涡"], "confidence": 0.9},
    {"source_domain": "机器", "target_domain": "生活状态",
     "ground": ["紧绷"], "triggers": ["发条"], "confidence": 0.8},
]


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        print(f"    [mock server] 收到请求: model={body.get('model')} "
              f"messages={len(body.get('messages', []))}")
        payload = {
            "choices": [{"message": {
                "role": "assistant",
                "content": json.dumps(_MOCK_REPLY, ensure_ascii=False)}}],
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # 静音
        pass


def run_mock_server_mode():
    banner("端到端验证：OpenAIBackend 的真实 HTTP 通路（本地假端点）")
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"  本地假端点已启动: http://127.0.0.1:{port}/v1")
    try:
        backend = OpenAIBackend(api_key="test-key",
                                base_url=f"http://127.0.0.1:{port}/v1",
                                model="mock-model")
        cands = backend.discover("这起事件让公司声誉陷入了舆论的漩涡。")
        print(f"\n  discover() 返回 {len(cands)} 条候选（真的走了 HTTP 请求 + JSON 解析）:")
        for c in cands:
            print(f"    - {c.source_domain} → {c.target_domain} "
                  f"ground={c.ground} triggers={c.triggers} conf={c.confidence}")

        ex = MetaphorExtractor(llm_backend=backend)
        text = "这起事件让公司声誉陷入了舆论的漩涡。"
        edges = ex.extract(text, doc_id="d", chunk_id="c0")
        print(f"\n  抽取器据 LLM 候选产出 {len(edges)} 条 L1 超边:")
        for e in edges:
            print(f"    - {e.source_domain} → {e.target_domain} "
                  f"frame={e.frame_id} source_type={e.source_type} conf={e.confidence}")
        assert edges, "LLM 候选应能产出超边"

        # 优雅降级：密钥缺失 / 端点不可达时不能抛异常
        bad = OpenAIBackend(api_key="k", base_url="http://127.0.0.1:1/v1")
        print(f"\n  端点不可达时降级: discover 返回 {bad.discover('测试')!r}（不抛异常 ✅）")
        nokey = OpenAIBackend(api_key=None)
        print(f"  无密钥时降级:     discover 返回 {nokey.discover('测试')!r}（不抛异常 ✅）")
        print("\n  ✅ 真实 HTTP 通路验证通过")
    finally:
        server.shutdown()


def main():
    args = sys.argv[1:]
    if "--mock-server" in args:
        run_mock_server_mode()
        return

    if os.environ.get("LLM_API_KEY"):
        backend = OpenAIBackend()
        name = f"OpenAIBackend（真实端点 model={backend.model}）"
    else:
        backend = LocalHeuristicBackend()
        name = "LocalHeuristicBackend（离线近似，未设 LLM_API_KEY）"
        print("\n提示：未检测到 LLM_API_KEY，使用离线后端演示。"
              "设 LLM_API_KEY / LLM_BASE_URL 后本脚本会自动切换为真实大模型；"
              "加 --mock-server 可验证真实 HTTP 通路（无需密钥）。")

    ex = show(backend, name)

    banner("构建四层隐喻超超图（LLM 发现的候选也进图）")
    shg = MetaphorSHGBuilder(llm_backend=backend).build(SAMPLES, doc_id="llm_demo")
    print(f"  {shg.summary()}")
    print(f"  L3 级联: {[c.id for c in shg.cascades]}")

    banner("MockBackend：演示接口契约（单测同款）")
    mb = MockBackend(
        discover_candidates=[LLMCandidate("迷宫", "人生抉择",
                                          ground=["出路"], triggers=["迷宫"])],
        refine_result=LLMRefine(is_metaphor=True, confidence=0.85, ground=["出路"]),
    )
    edges = MetaphorExtractor(llm_backend=mb).extract(
        "人生就像一座迷宫，到处都是死胡同。", doc_id="d", chunk_id="c")
    for e in edges:
        print(f"  {e.source_domain} → {e.target_domain} conf={e.confidence}")

    banner("✅ LLM 后端演示完成")


if __name__ == "__main__":
    main()
