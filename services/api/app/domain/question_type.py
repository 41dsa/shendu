import enum


class QuestionType(str, enum.Enum):
    """V1 仅批改申论大作文。"""

    essay = "essay"
