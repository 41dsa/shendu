import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.standard_engine.rubric_agreement import rubric_candidates_agreement


def main() -> None:
    a = [{"dimension_id": "D01", "core": "立意准确紧扣主题"}]
    b = [{"dimension_id": "D01", "core": "立意准确紧扣主题"}]
    assert rubric_candidates_agreement(a, b) == 1.0
    c = [{"dimension_id": "D02", "core": "结构完整"}]
    score = rubric_candidates_agreement(a, c)
    assert 0.0 <= score < 1.0
    print("verify_rubric_agreement: ok", score)


if __name__ == "__main__":
    main()
