"""自备大作文批改：可选注入写作技巧参考文本（非考试标准引擎）。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.models.entities import Question, Submission

_DEFAULT_GUIDE = (
    Path(__file__).resolve().parents[3].parent / "data" / "guides" / "essay_writing_technique.txt"
)


def _guide_path() -> Path | None:
    raw = (settings.essay_writing_guide_path or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_file() else None
    return _DEFAULT_GUIDE if _DEFAULT_GUIDE.is_file() else None


@lru_cache(maxsize=1)
def _load_guide_text_cached(resolved: str, mtime_ns: int, max_chars: int) -> str:
    _ = mtime_ns
    text = Path(resolved).read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n…（参考文已截断，完整版见 Admin 资料或 data/guides）"


def get_writing_guide_excerpt() -> str | None:
    if not settings.essay_writing_guide_enabled:
        return None
    path = _guide_path()
    if not path:
        return None
    try:
        st = path.stat()
    except OSError:
        return None
    max_chars = max(2000, int(settings.essay_writing_guide_max_chars))
    return _load_guide_text_cached(str(path.resolve()), st.st_mtime_ns, max_chars)


def uses_custom_essay_submission(submission: Submission, question: Question) -> bool:
    if (submission.user_prompt or "").strip():
        return True
    return question.id == USER_ESSAY_QUESTION_ID


def writing_guide_for_submission(submission: Submission, question: Question) -> str | None:
    if not uses_custom_essay_submission(submission, question):
        return None
    return get_writing_guide_excerpt()


def clear_writing_guide_cache() -> None:
    _load_guide_text_cached.cache_clear()
