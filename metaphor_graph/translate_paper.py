# -*- coding: utf-8 -*-
"""论文初稿中文 → 英文批量翻译（A1，GLM 分节翻译 + 缓存 + 结构保持）。

- 按一级标题（\\n## ）切分章节；超长章节再按 4500 字符二次切分（段落边界）。
- 提示词约束：学术机翻译风；**保持 Markdown 结构**（表格/代码块/加粗/列表）、
  数字与引用原样、代码与命令行不翻译。
- 每片翻译落盘缓存（data/llm_cache_translate.json），重跑零请求。

运行（需 LLM_API_KEY=智谱）：
    python -m metaphor_graph.translate_paper
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.evaluate_real import build_llm_backend
from metaphor_graph.llm_backend import _parse_json_blob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "论文初稿.md")
DST = os.path.join(ROOT, "论文初稿_en.md")
CACHE = os.path.join(ROOT, "data", "llm_cache_translate.json")

T_SYSTEM = ("You are a professional academic translator for NLP conference papers. "
            "Translate the given Chinese markdown fragment into English. "
            "Rules: 1) preserve ALL markdown structure exactly (tables, code blocks, "
            "bold, lists, headings level); 2) keep every number, citation marker, "
            "and Chinese corpus example sentence in its original form inside the "
            "text flow; 3) do NOT translate shell commands, code, or file paths; "
            "4) formal ACL-style academic English; 5) output ONLY the translated "
            "markdown, no commentary.")
T_USER = "Translate the following markdown fragment to English:\n\n{fragment}"


def _raw_chat(backend, system, user) -> str:
    import urllib.request
    payload = {"model": backend.model,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "temperature": 0.2}
    if backend.extra_body:
        payload.update(backend.extra_body)
    req = urllib.request.Request(
        backend.endpoint, data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {backend.api_key}"})
    with urllib.request.urlopen(req, timeout=backend.timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    backend._accumulate_usage(data.get("usage"))
    return str(data["choices"][0]["message"]["content"]).strip()


def split_sections(text: str) -> list:
    """按一级标题切分；首块为标题+导语。"""
    parts = text.split("\n## ")
    out = [parts[0]]
    for p in parts[1:]:
        out.append("## " + p)
    return out


def split_long(sec: str, limit: int = 4500) -> list:
    """超长章节按段落边界二次切分。"""
    if len(sec) <= limit:
        return [sec]
    lines = sec.split("\n")
    chunks, buf = [], ""
    for ln in lines:
        if len(buf) + len(ln) + 1 > limit and buf:
            chunks.append(buf)
            buf = ln
        else:
            buf = (buf + "\n" + ln).strip()
    if buf:
        chunks.append(buf)
    return chunks


def main():
    if not os.environ.get("LLM_API_KEY"):
        raise SystemExit("需要 LLM_API_KEY（智谱）")
    backend = build_llm_backend()
    backend.model = "glm-5.3-flash"
    backend.timeout = 300.0
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, "r", encoding="utf-8") as f:
            cache = json.load(f)

    text = open(SRC, encoding="utf-8").read()
    secs = split_sections(text)
    frags = []
    for sec in secs:
        frags.extend(split_long(sec))
    print(f"待翻译分片：{len(frags)} 片（缓存 {len(cache)}）")

    out_parts = []
    for i, frag in enumerate(frags):
        key = hashlib.md5(frag.encode("utf-8")).hexdigest()[:12]
        if key in cache:
            out_parts.append(cache[key])
            print(f"  [{i+1}/{len(frags)}] 缓存命中", flush=True)
            continue
        en = None
        for attempt in range(3):
            try:
                out = _raw_chat(backend, T_SYSTEM, T_USER.format(fragment=frag))
                # 反解析再序列化，防答案外包裹文字
                parsed = _parse_json_blob(out)
                en = parsed if isinstance(parsed, str) else out
                break
            except Exception as e:
                print(f"  [{i+1}] 重试{attempt+1}: {type(e).__name__} {str(e)[:50]}",
                      flush=True)
                time.sleep(5 * (attempt + 1))
        if en is None:
            en = frag            # 失败保底：保留中文原文（可见，不静默丢）
            print(f"  ⚠️ [{i+1}] 翻译失败，保留原文")
        cache[key] = en
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
        out_parts.append(en)
        print(f"  [{i+1}/{len(frags)}] 翻译完成（{len(frag)}→{len(en)} 字符）",
              flush=True)

    with open(DST, "w", encoding="utf-8") as f:
        f.write("\n\n".join(out_parts))
    real = backend
    if hasattr(real, "usage_report"):
        print("LLM 用量:", real.usage_report())
    print(f"英文稿 → {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
