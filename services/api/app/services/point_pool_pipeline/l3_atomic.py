from __future__ import annotations

from typing import Any

from app.domain.scoring_engine.embedding import semantic_similarity
from app.domain.scoring_engine.level_config import LEVEL_CONFIG_VERSION
from app.schemas.point_pool import AtomicPointSchema, ExamLevelId, LevelApplicabilitySchema, LevelWeightSchema, PointPoolSchema


def _level_applicability(level_id: ExamLevelId, *, weight: float, required: bool) -> LevelApplicabilitySchema:
    base = LevelWeightSchema(weight=1.0, required=False)
    high = LevelWeightSchema(weight=weight, required=required)
    low = LevelWeightSchema(weight=max(0.5, weight * 0.6), required=False)
    if level_id == "provincial":
        return LevelApplicabilitySchema(provincial=high, municipal=low, enforcement=base)
    if level_id == "municipal":
        return LevelApplicabilitySchema(provincial=low, municipal=high, enforcement=low)
    return LevelApplicabilitySchema(provincial=base, municipal=low, enforcement=high)


def cluster_and_atomize(merged_points: list[dict[str, Any]], *, level_id: ExamLevelId) -> list[AtomicPointSchema]:
    clusters: list[list[dict[str, Any]]] = []
    for item in merged_points:
        text = str(item.get("text") or "")
        placed = False
        for cluster in clusters:
            rep = str(cluster[0].get("text") or "")
            if semantic_similarity(text, rep) >= 0.72:
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])

    atoms: list[AtomicPointSchema] = []
    for idx, cluster in enumerate(clusters, start=1):
        rep = max(cluster, key=lambda x: float(x.get("confidence") or 0))
        text = str(rep.get("text") or "")
        kws = set()
        paras: set[int] = set()
        conf_sum = 0.0
        for c in cluster:
            for k in c.get("keywords") or []:
                kws.add(str(k))
            for p in c.get("source_para") or []:
                paras.add(int(p))
            conf_sum += float(c.get("confidence") or 0.7)
        ptype = str(rep.get("point_type") or "sub")
        is_main = ptype in ("main", "theme") or rep.get("extraction_method") == "focus_point"
        weight = 5.0 if is_main else 3.0 if ptype == "sub" else 2.0
        if level_id == "municipal" and ptype == "sub" and "对策" in text:
            weight += 1.0
        if level_id == "enforcement" and ("依法" in text or "规范" in text):
            weight += 1.0
        conf = min(0.98, conf_sum / max(len(cluster), 1))
        atoms.append(
            AtomicPointSchema(
                point_id=f"P{idx:03d}",
                text=text,
                keywords=sorted(kws)[:12],
                semantic_variants=[text] + sorted(kws)[:6],
                source_para=sorted(paras),
                level_applicability=_level_applicability(level_id, weight=weight, required=is_main),
                is_main_point=is_main,
                point_type=ptype if ptype in ("main", "sub", "evidence", "theme") else "sub",
                confidence=conf,
                extraction_method=str(rep.get("extraction_method") or "consensus"),
                consensus_votes=int(rep.get("consensus_votes") or 0),
                consensus_total=int(rep.get("consensus_total") or 0),
            )
        )
    return atoms


def build_point_pool_document(
    *,
    question_id: str,
    level_id: ExamLevelId,
    merged_points: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> PointPoolSchema:
    atoms = cluster_and_atomize(merged_points, level_id=level_id)
    return PointPoolSchema(
        question_id=question_id,
        level_id=level_id,
        points=atoms,
        version="1.0.0",
        level_config_version=LEVEL_CONFIG_VERSION,
        metadata=metadata or {},
    )
