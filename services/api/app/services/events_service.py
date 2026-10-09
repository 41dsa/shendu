"""产品埋点（BE-608）：轻量写入 analytics_events，不阻塞主流程。"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import AnalyticsEvent


def track_event(db: Session, event_name: str, user_id: str | None = None, **properties: Any) -> None:
    db.add(
        AnalyticsEvent(
            user_id=user_id,
            event_name=event_name,
            properties=properties,
        )
    )
    db.commit()
