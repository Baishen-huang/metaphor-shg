# -*- coding: utf-8 -*-
"""零依赖统计工具（scipy 不在本环境，故自实现）。

全部实现都做了**并列（tie）修正**——Ω 取值高度离散（大量 0 与精确重复值），
不做并列修正的秩检验会高估显著性。
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple


# ------------------------------------------------------------------ 基础
def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def median(xs: Sequence[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def stdev(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def quantile(xs: Sequence[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def describe(xs: Sequence[float]) -> Dict[str, float]:
    n = len(xs)
    return dict(n=n, mean=mean(xs), sd=stdev(xs), median=median(xs),
                q25=quantile(xs, 0.25), q75=quantile(xs, 0.75),
                min=min(xs) if xs else float("nan"),
                max=max(xs) if xs else float("nan"),
                zero_frac=(sum(1 for x in xs if x == 0.0) / n if n else float("nan")))


# -------------------------------------------------------------- 秩 / 相关
def _rank(xs: Sequence[float]) -> List[float]:
    """平均秩（并列取均值）。"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Tuple[float, float, int]:
    """Spearman ρ + 双尾 p（t 近似，df=n-2）。返回 (rho, p, n)。"""
    assert len(xs) == len(ys)
    n = len(xs)
    if n < 3:
        return float("nan"), float("nan"), n
    rx, ry = _rank(xs), _rank(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return float("nan"), float("nan"), n
    rho = num / (dx * dy)
    rho = max(-1.0, min(1.0, rho))
    if abs(rho) >= 1.0:
        return rho, 0.0, n
    t = rho * math.sqrt((n - 2) / (1 - rho ** 2))
    return rho, 2 * (1 - _t_cdf(abs(t), n - 2)), n


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    mx, my = mean(xs), mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx > 0 and dy > 0 else float("nan")


def point_biserial(binary: Sequence[int], cont: Sequence[float]
                   ) -> Tuple[float, float, int]:
    """二值 × 连续 的点二列相关（等价于对二值变量做 Pearson）。返回 (r, p, n)。"""
    r = pearson([float(b) for b in binary], cont)
    n = len(binary)
    if not (r == r) or n < 3 or abs(r) >= 1.0:
        return r, 0.0 if abs(r) >= 1.0 else float("nan"), n
    t = r * math.sqrt((n - 2) / (1 - r ** 2))
    return r, 2 * (1 - _t_cdf(abs(t), n - 2)), n


def auc(a: Sequence[float], b: Sequence[float]) -> float:
    """P(X_a > X_b) + 0.5·P(=) —— 与 Mann-Whitney U 同一统计量（AUC 视角）。"""
    if not a or not b:
        return float("nan")
    ranks = _rank(list(a) + list(b))
    ra = sum(ranks[:len(a)])
    return (ra - len(a) * (len(a) + 1) / 2.0) / (len(a) * len(b))


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """Cliff's δ = 2·AUC − 1，值域 [−1,1]。"""
    return 2 * auc(a, b) - 1


def mann_whitney(a: Sequence[float], b: Sequence[float]
                 ) -> Tuple[float, float, float]:
    """Mann-Whitney U 双尾 p（正态近似 + 并列方差修正 + 连续性修正）。

    返回 (U, z, p)。样本量大且并列多，正态近似是标准做法（本环境无 scipy）。
    """
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return float("nan"), float("nan"), float("nan")
    allv = list(a) + list(b)
    ranks = _rank(allv)
    r1 = sum(ranks[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2.0
    mu = n1 * n2 / 2.0
    # 并列修正
    tie_term = 0.0
    i = 0
    s = sorted(allv)
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        t = j - i + 1
        if t > 1:
            tie_term += t ** 3 - t
        i = j + 1
    N = n1 + n2
    var = (n1 * n2 / 12.0) * ((N + 1) - tie_term / (N * (N - 1))) if N > 1 else 0.0
    if var <= 0:
        return u1, float("nan"), float("nan")
    z = (u1 - mu - 0.5 * (1 if u1 > mu else -1)) / math.sqrt(var)
    return u1, z, 2 * (1 - _norm_cdf(abs(z)))


def wilcoxon_paired(a: Sequence[float], b: Sequence[float]
                    ) -> Tuple[float, float, int]:
    """配对 Wilcoxon 符号秩检验（正态近似，并列修正）。返回 (z, p, n_nonzero)。"""
    assert len(a) == len(b)
    d = [x - y for x, y in zip(a, b)]
    d = [v for v in d if v != 0.0]
    n = len(d)
    if n < 2:
        return float("nan"), float("nan"), n
    ranks = _rank([abs(v) for v in d])
    w_plus = sum(r for r, v in zip(ranks, d) if v > 0)
    mu = n * (n + 1) / 4.0
    tie_term = 0.0
    s = sorted(abs(v) for v in d)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        t = j - i + 1
        if t > 1:
            tie_term += t ** 3 - t
        i = j + 1
    var = n * (n + 1) * (2 * n + 1) / 24.0 - tie_term / 48.0
    if var <= 0:
        return float("nan"), float("nan"), n
    z = (w_plus - mu - 0.5 * (1 if w_plus > mu else -1)) / math.sqrt(var)
    return z, 2 * (1 - _norm_cdf(abs(z))), n


def sign_test(wins: int, n: int) -> float:
    """精确二项双尾 p（p=0.5）。"""
    if n == 0:
        return float("nan")
    k = min(wins, n - wins)
    tot = sum(math.comb(n, i) for i in range(0, k + 1)) * 2 / (2 ** n)
    return min(1.0, tot)


# ------------------------------------------------------------ 分布函数
def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _t_cdf(t: float, df: int) -> float:
    """Student-t CDF，用不完全 Beta 的连分式（Numerical Recipes betacf）。"""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    ib = _betai(df / 2.0, 0.5, x)
    return 1.0 - 0.5 * ib if t > 0 else 0.5 * ib


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta + b * math.log(1 - x) + a * math.log(x)) \
        * _betacf(b, a, 1 - x) / b


def _betacf(a: float, b: float, x: float, itmax: int = 200,
            eps: float = 3e-12) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h
