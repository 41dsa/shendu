"""V3-CAL：QWK / 简化 ICC / Rasch 能力估计（门禁与离线评估）。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


def _build_confusion(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    labels: list[int],
) -> list[list[float]]:
    idx = {v: i for i, v in enumerate(labels)}
    n = len(labels)
    mat = [[0.0] * n for _ in range(n)]
    for a, b in zip(y_true, y_pred, strict=True):
        if a not in idx or b not in idx:
            continue
        mat[idx[a]][idx[b]] += 1.0
    return mat


def quadratic_weighted_kappa(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    *,
    labels: list[int] | None = None,
) -> float | None:
    """Cohen's quadratic weighted kappa（有序等级，如 L0～L4 → 0～4）。"""
    if len(y_true) != len(y_pred) or len(y_true) < 2:
        return None
    if labels is None:
        labels = sorted(set(y_true) | set(y_pred))
    n_labels = len(labels)
    if n_labels < 2:
        return None
    o = _build_confusion(y_true, y_pred, labels)
    total = sum(sum(row) for row in o)
    if total <= 0:
        return None
    w = [[((i - j) ** 2) / ((n_labels - 1) ** 2) if n_labels > 1 else 0.0 for j in range(n_labels)] for i in range(n_labels)]
    po = sum(w[i][j] * o[i][j] for i in range(n_labels) for j in range(n_labels)) / total
    row_m = [sum(o[i]) / total for i in range(n_labels)]
    col_m = [sum(o[i][j] for i in range(n_labels)) / total for j in range(n_labels)]
    pe = sum(w[i][j] * row_m[i] * col_m[j] for i in range(n_labels) for j in range(n_labels))
    if abs(1.0 - pe) < 1e-9:
        return 1.0 if abs(1.0 - po) < 1e-9 else 0.0
    return 1.0 - po / pe


def icc_one_way_absolute(replicates: Sequence[Sequence[float]]) -> float | None:
    """
    被试 × 评分者 绝对 ICC(1,1) 简化估计。
    replicates: 每个被试一行，多列评分。
    """
    rows = [list(r) for r in replicates if len(r) >= 2]
    if len(rows) < 2:
        return None
    k = len(rows[0])
    n = len(rows)
    grand = sum(sum(r) for r in rows) / (n * k)
    msb = sum(((sum(r) / k - grand) ** 2) * k for r in rows) / max(n - 1, 1)
    msw = sum((x - sum(r) / k) ** 2 for r in rows for x in r) / max(n * (k - 1), 1)
    denom = msb + (k - 1) * msw
    if denom <= 0:
        return None
    return (msb - msw) / denom


def rasch_ability_mle(
    responses: Sequence[tuple[int, int]],
    *,
    iterations: int = 30,
) -> float:
    """
    1PL Rasch：responses 为 (item_difficulty, correct 0/1) 或 (level_index, hit)。
    返回被试能力 theta（logit 尺度）。
    """
    if not responses:
        return 0.0
    theta = 0.0
    for _ in range(iterations):
        num = 0.0
        den = 0.0
        for diff, y in responses:
            p = 1.0 / (1.0 + math.exp(-(theta - diff)))
            num += y - p
            den += p * (1.0 - p)
        if abs(den) < 1e-9:
            break
        theta += num / den
    return theta


@dataclass
class CalibrationGateResult:
    qwk: float | None
    icc: float | None
    sample_count: int
    min_qwk: float
    min_samples: int
    passed: bool
    reason: str


def evaluate_calibration_gate(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    *,
    min_qwk: float,
    min_samples: int,
    icc_replicates: Sequence[Sequence[float]] | None = None,
) -> CalibrationGateResult:
    n = len(y_true)
    qwk = quadratic_weighted_kappa(y_true, y_pred)
    icc = icc_one_way_absolute(icc_replicates) if icc_replicates else None
    if n < min_samples:
        return CalibrationGateResult(
            qwk=qwk,
            icc=icc,
            sample_count=n,
            min_qwk=min_qwk,
            min_samples=min_samples,
            passed=True,
            reason=f"样本不足 ({n}<{min_samples})，门禁跳过",
        )
    if qwk is None:
        return CalibrationGateResult(
            qwk=None,
            icc=icc,
            sample_count=n,
            min_qwk=min_qwk,
            min_samples=min_samples,
            passed=False,
            reason="无法计算 QWK",
        )
    ok = qwk >= min_qwk
    return CalibrationGateResult(
        qwk=qwk,
        icc=icc,
        sample_count=n,
        min_qwk=min_qwk,
        min_samples=min_samples,
        passed=ok,
        reason="QWK 达标" if ok else f"QWK {qwk:.3f} 低于门槛 {min_qwk}",
    )
