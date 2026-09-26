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
    """§6.1 三通路 × 改写型查询（来源：evaluate_repaired，全局池 1,100）。"""
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    names = ["字面包含通路", "触发词级联通路", "语义超图通路"]
    # ⚠️ 口径已修正（实测）：原图用 0.000/0.042/1.000，其中 1.000 是池 ≤10 的
    # **平凡饱和**（池 ≤10 时 Recall@10 对任何返回全候选的排序器恒为 1.0）。
    # 修复后基准（全局池 1,100，改写型 n=777）实测 Hits@10：
    vals = [0.0000, 0.0206, 0.1918]
    bars = ax.bar(names, vals, color=[C_GREY, C_BAD, C_MAIN], width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.008, f"{v:.4f}",
                ha="center", fontsize=10)
    ax.set_ylabel("Hits@10（全局池 1,100；随机基线 0.0091）")
    ax.set_title("三通路：改写型查询（触发词被程序化切断，n=777）\n"
                 "语义超图 0.1918 = 级联的 9.3 倍；字面通路完全失效（非空率 0/777）")
    ax.set_ylim(0, 0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_paths.png"), dpi=200)
    plt.close(fig)


def fig3_a6():
    """§6.4 A6 知识源消融（来源：evaluate_a6 n=652）。"""
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    names = ["专属隐喻级联\n（+语义超图排序）", "通用常识关联\n（ConceptNet 替代口径）"]
    # ⚠️ 口径已修正（实测）：隐喻臂原为硬编码 top_k=5，而常识臂**无上限** ——
    # 两臂预算不对等，低估隐喻臂 17pp（0.8287）。改为 top_k=20（与无上限等价）
    # 后为 1.000。注：该 1.000 受池 ≤10 平凡饱和限制，结论依**相对比较**成立。
    vals = [1.000, 0.095]
    bars = ax.bar(names, vals, color=[C_MAIN, C_BAD], width=0.45)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}",
                ha="center", fontsize=10)
    ax.set_ylabel("Recall@10（两臂预算对等后）")
    ax.set_title("A6 知识源消融：常识关联替换专属级联后下降 10.5 倍（n=652）\n"
                 "（隐喻臂 1.000 受池 ≤10 平凡饱和限制；结论依相对比较成立）")
    ax.set_ylim(0, 1.15)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_a6.png"), dpi=200)
    plt.close(fig)


def fig4_ranker():
    """§6.2 排序器条件化 × 查询族 × 锚定口径（来源：evaluate_repaired，全局池 1,100）。"""
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    # ⚠️ 口径已修正（实测）：原图用旧基准（池 7–10）的 0.995/0.502/0.707 等，
    # 而该基准下**随机排序的 MRR 期望即达 0.37**（量程被吃掉 37%）。
    # 改用修复后基准（全局池 1,100，随机基线 0.0069）的四族数据。
    groups = ["重叠型\nanchored", "重叠型\ndeanchor", "改写型\nanchored", "改写型\ndeanchor"]
    hand = [0.8953, 0.3620, 0.1172, 0.0882]
    trained = [0.9037, 0.3488, 0.1341, 0.0809]
    x = range(len(groups))
    w = 0.35
    ax.bar([i - w / 2 for i in x], hand, w, label="人工加权", color=C_GREY)
    ax.bar([i + w / 2 for i in x], trained, w, label="自监督训练", color=C_MAIN)
    for i, (h, t) in enumerate(zip(hand, trained)):
        ax.text(i - w / 2, h + 0.015, f"{h:.3f}", ha="center", fontsize=8.5)
        ax.text(i + w / 2, t + 0.015, f"{t:.3f}", ha="center", fontsize=8.5)
    ax.annotate("训练增益只在\nanchored 为正", (0.55, 0.98), fontsize=9,
                color=C_MAIN, ha="center")
    ax.annotate("deanchor\n一致为负", (2.55, 0.98), fontsize=9,
                color=C_BAD, ha="center")
    ax.set_xticks(list(x))
    ax.set_xticklabels(groups, fontsize=9)
    ax.set_ylabel("MRR@10（全局池 1,100；随机基线 0.0069）")
    ax.set_title("排序器增益的条件化：查询族 × 锚定口径\n"
                 "训练器学到的是「复现构造锚点」，去锚定后一致为负")
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
