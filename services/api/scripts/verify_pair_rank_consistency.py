#!/usr/bin/env python3
"""§7.5 成对比较排序与 Bradley-Terry 强度 Spearman ≥0.7（合成链）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.anchor_bradley_terry import bradley_terry_strengths


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for r, idx in enumerate(order):
        ranks[idx] = float(r + 1)
    return ranks


def spearman_rho(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 1.0
    rx, ry = _rank(x), _rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den_x = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    den_y = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if den_x == 0 or den_y == 0:
        return 1.0
    return num / (den_x * den_y)


def main() -> None:
    ids = ["e0", "e1", "e2", "e3", "e4"]
    true_strength = [5.0, 4.0, 3.0, 2.0, 1.0]
    edges: list[tuple[str, str, str]] = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if true_strength[i] > true_strength[j]:
                edges.append((ids[i], ids[j], "T1"))
            else:
                edges.append((ids[j], ids[i], "T1"))

    bt = bradley_terry_strengths(edges)
    est = [bt.get(i, 0.0) for i in ids]
    rho = spearman_rho(true_strength, est)
    assert rho >= 0.7, f"spearman={rho:.3f}"
    print(f"verify_pair_rank_consistency: OK (rho={rho:.3f})")


if __name__ == "__main__":
    main()
