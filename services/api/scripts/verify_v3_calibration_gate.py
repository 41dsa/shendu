#!/usr/bin/env python3
"""V3-CAL：QWK / ICC / Rasch 与门禁逻辑。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.calibration_metrics import (
    evaluate_calibration_gate,
    icc_one_way_absolute,
    quadratic_weighted_kappa,
    rasch_ability_mle,
)


def main() -> None:
    perfect = ([0, 1, 2, 3, 4] * 4, [0, 1, 2, 3, 4] * 4)
    qwk_p = quadratic_weighted_kappa(*perfect)
    assert qwk_p is not None and qwk_p > 0.95

    noisy_true = [0, 1, 2, 3, 4, 0, 1, 2, 3, 4]
    noisy_pred = [0, 1, 2, 2, 3, 1, 1, 2, 4, 3]
    qwk_n = quadratic_weighted_kappa(noisy_true, noisy_pred)
    assert qwk_n is not None and qwk_n < qwk_p

    gate_ok = evaluate_calibration_gate(*perfect, min_qwk=0.7, min_samples=5)
    assert gate_ok.passed

    gate_skip = evaluate_calibration_gate([0, 1], [0, 1], min_qwk=0.99, min_samples=10)
    assert gate_skip.passed and "样本不足" in gate_skip.reason

    icc = icc_one_way_absolute([[2.0, 2.5, 2.2], [3.0, 3.1, 2.9], [1.0, 1.2, 0.9]])
    assert icc is not None and icc > 0.5

    theta = rasch_ability_mle([(0, 1), (1, 1), (2, 0), (3, 0)])
    assert theta > 0

    print("verify_v3_calibration_gate: OK")


if __name__ == "__main__":
    main()
