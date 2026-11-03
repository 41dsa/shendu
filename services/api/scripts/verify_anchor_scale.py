"""Phase 6：锚作文相对尺度（纯函数）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.anchor_scale_service import _distance, _trait_vector


def main() -> None:
    a = _trait_vector({"T1": "L2", "T3": "L3"})
    b = _trait_vector({"T1": "L3", "T3": "L3"})
    assert abs(_distance(a, b) - 0.5) < 0.01
    c = _trait_vector({"T1": "L0", "T5": "L1"})
    assert _distance(a, c) > 0.5
    print("verify_anchor_scale: ok")


if __name__ == "__main__":
    main()
