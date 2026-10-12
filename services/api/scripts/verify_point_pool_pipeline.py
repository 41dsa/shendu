"""点池流水线 L0–L3 冒烟（stub，无 LLM）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.point_pool_pipeline.build import build_point_pool_bundle_sync_stub, bundle_to_payload_dict
from app.services.scoring_engine.pool_loader import load_point_pool_for_level, atomic_points_to_scoring_points


def main() -> None:
    bundle = build_point_pool_bundle_sync_stub(
        question_id="demo-essay-001",
        prompt="围绕基层治理现代化写一篇文章",
        material="第一段：基层治理面临新挑战。\n第二段：因此需要推进数字化转型。",
        rubric_criteria=[
            {
                "id": "RC1",
                "dimension_id": "D01",
                "core": "基层治理现代化",
                "acceptable_expressions": ["数字化转型", "治理体系"],
                "max_score": 10,
                "confidence": 0.88,
            }
        ],
        focus_points=["扣题", "联系材料"],
        themes=["基层治理"],
    )
    payload = bundle_to_payload_dict(bundle)
    assert payload.get("municipal"), payload
    pool = load_point_pool_for_level({"point_pools": payload}, "municipal", question_id="demo-essay-001")
    assert pool and pool.points, pool
    scoring_pts = atomic_points_to_scoring_points(pool, "municipal")
    assert scoring_pts[0].point_id.startswith("P")
    print("verify_point_pool_pipeline: ok")


if __name__ == "__main__":
    main()
