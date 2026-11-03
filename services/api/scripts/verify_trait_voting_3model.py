#!/usr/bin/env python3
"""P-06 / V-01：三路由 Trait 投票模型列表与 min_models 对齐。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.models.entities import CredentialRole
from app.services.scoring_engine import trait_voting


def _cred(cid: int, role: CredentialRole):
    c = MagicMock()
    c.id = cid
    c.role = role
    return c


def main() -> None:
    assert settings.trait_llm_voting_min_models >= 3, settings.trait_llm_voting_min_models
    db = MagicMock()
    p, co, r = _cred(1, CredentialRole.primary), _cred(2, CredentialRole.consensus), _cred(3, CredentialRole.reviewer)

    def _get(db_, user_id, role):
        return {CredentialRole.primary: p, CredentialRole.consensus: co, CredentialRole.reviewer: r}.get(role)

    with patch("app.services.scoring_engine.trait_voting.get_credential", side_effect=_get):
        models = trait_voting._distinct_voting_models(db, "user-1")
    assert len(models) == 3, models
    labels = [m[1] for m in models]
    assert labels == ["primary", "consensus", "reviewer"], labels

    with patch("app.services.scoring_engine.trait_voting.get_credential", side_effect=lambda *a, **k: p):
        padded = trait_voting._distinct_voting_models(db, "user-1")
    assert len(padded) == 3, padded

    print("verify_trait_voting_3model: OK")


if __name__ == "__main__":
    main()
