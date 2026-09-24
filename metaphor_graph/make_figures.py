# -*- coding: utf-8 -*-
"""论文图表生成（A3）——从已记录的实验结果生成 PNG 图。

数字全部来自仓库已记录的实验（每个图函数注释标明来源与复现命令）；
重跑实验后须同步更新本脚本中的数值。

运行：python -m metaphor_graph.make_figures   → figures/*.png
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "figures")
os.makedirs(OUT, exist_ok=True)

C_MAIN, C_ALT, C_BAD, C_GREY = "#2b6cb0", "#38a169", "#c53030", "#a0aec0"


def fig1_pareto():
    """§5.1 抽取帕累托（来源：evaluate_real，README §6.7/§5.1）。"""
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    pts = [
        ("规则侧天花板", 9.7, 7.9, C_ALT),
        ("LLM 开放发现\n(0.85+refine)", 69.6, 9.2, C_MAIN),
        ("LLM 不设防\n(阈值0.5)", 89.6, 32.9, C_BAD),
    ]
    for name, rec, p1, c in pts:
        ax.scatter(rec, p1, s=120, color=c, zorder=3)
        ax.annotate(name, (rec, p1), textcoords="offset points",
                    xytext=(8, 6), fontsize=9)
    ax.axhline(15, color=C_BAD, ls="--", lw=1)
    ax.text(70, 16.5, "P1 硬门槛 15%", color=C_BAD, fontsize=9)
    ax.plot([9.7, 69.6], [7.9, 9.2], color=C_MAIN, ls=":", lw=1)
    ax.set_xlabel("隐喻句召回（%）")
    ax.set_ylabel("字面误判率 P1（%）")
    ax.set_title("抽取帕累托：LLM 开放发现外推前沿（CCL2018 n=1100）")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_pareto.png"), dpi=200)
    plt.close(fig)


def fig2_paths():
    """§6.1 三通路 × 改写型查询（来源：evaluate_llmgold n=632）。"""
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    names = ["字面包含通路", "触发词级联通路", "语义超图通路"]
    vals = [0.000, 0.042, 1.000]
    bars = ax.bar(names, vals, color=[C_GREY, C_BAD, C_MAIN], width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}",
                ha="center", fontsize=10)
    ax.set_ylabel("Recall@10（LLM 非构造金标）")
    ax.set_title("三通路召回：改写型查询（触发词被程序化切断，n=632）")
    ax.set_ylim(0, 1.15)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_paths.png"), dpi=200)
    plt.close(fig)


def fig3_a6():
    """§6.4 A6 知识源消融（来源：evaluate_a6 n=652）。"""
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    names = ["专属隐喻级联\n（+语义超图排序）", "通用常识关联\n（ConceptNet 替代口径）"]
    vals = [0.783, 0.095]
    bars = ax.bar(names, vals, color=[C_MAIN, C_BAD], width=0.45)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}",
                ha="center", fontsize=10)
    ax.set_ylabel("Recall@10（LLM 非构造金标）")
    ax.set_title("A6 知识源消融：常识关联替换专属级联后下降 8 倍（n=652）")
    ax.set_ylim(0, 0.95)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_a6.png"), dpi=200)
    plt.close(fig)


def fig4_ranker():
    """§6.2 排序器条件化 + 表示质量（来源：evaluate_fullcorpus / evaluate_llmgold）。"""
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    groups = ["重叠型查询\n（哈希向量）", "改写型查询\n（哈希向量）", "改写型查询\n（真实句向量）"]
    hand = [0.995, 0.502, 0.707]
    trained = [0.998, 0.547, 0.758]
    x = range(len(groups))
    w = 0.35
    ax.bar([i - w / 2 for i in x], hand, w, label="人工加权", color=C_GREY)
    ax.bar([i + w / 2 for i in x], trained, w, label="自监督训练", color=C_MAIN)
    for i, (h, t) in enumerate(zip(hand, trained)):
        ax.text(i - w / 2, h + 0.015, f"{h:.3f}", ha="center", fontsize=8.5)
        ax.text(i + w / 2, t + 0.015, f"{t:.3f}", ha="center", fontsize=8.5)
    ax.annotate("+4.5pp\n(训练增益)", (1.18, 0.60), fontsize=9, color=C_MAIN)
    ax.annotate("+21pp\n(真实向量)", (2.18, 0.80), fontsize=9, color=C_MAIN)
    ax.set_xticks(list(x))
    ax.set_xticklabels(groups, fontsize=9)
    ax.set_ylabel("MRR@10（LLM 非构造金标）")
    ax.set_title("排序器增益的条件化：查询分布 × 表示质量")
    ax.set_ylim(0, 1.1)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig4_ranker.png"), dpi=200)
    plt.close(fig)


def fig5_chain():
    """§6.6 L1.5 密度与质量闭环（来源：evaluate_document_corpus / evaluate_chain_quality）。"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 3.9))
    # 左：密度
    names = ["独立短句\n(CCL2018)", "连贯文档\n(106 篇)"]
    dens = [0.6, 6.3]
    bars = ax1.bar(names, dens, color=[C_GREY, C_MAIN], width=0.45)
    for b, v in zip(bars, dens):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.12, f"{v:.1f}",
                 ha="center", fontsize=10)
    ax1.set_ylabel("扩展链 / 百条 L1")
    ax1.set_title("密度：连贯文档 10×")
    ax1.set_ylim(0, 7.6)
    # 右：双段管线质量
    stages = ["候选生成\n(ground1)", "+文本延续判据\n(vehicle_repeat)", "+LLM 语义校验\n(跨模型 judge)"]
    prec = [16.7, None, 63.6]
    xs = [0, 1, 2]
    ax2.plot([0, 2], [16.7, 63.6], "o-", color=C_MAIN, lw=1.5)
    ax2.text(1, 30, "文本级信号\n无效 (52→49)\n诚实负面", ha="center", fontsize=8.5, color=C_GREY)
    for x, v in zip(xs[:1] + xs[2:], [16.7, 63.6]):
        ax2.text(x, v + 2.5, f"{v:.1f}%", ha="center", fontsize=10)
    ax2.text(2, 71.5, "跨模型配对 71.4%", ha="center", fontsize=8.5, color=C_ALT)
    ax2.set_xticks(xs)
    ax2.set_xticklabels(stages, fontsize=8.5)
    ax2.set_ylabel("严格 MIPVU 口径链精度（%）")
    ax2.set_title("双段管线：密度换精度")
    ax2.set_ylim(0, 82)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig5_chain.png"), dpi=200)
    plt.close(fig)


def main():
    fig1_pareto()
    fig2_paths()
    fig3_a6()
    fig4_ranker()
    fig5_chain()
    print(f"图表生成完成 → {OUT}")
    for fn in sorted(os.listdir(OUT)):
        print("  ", fn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
