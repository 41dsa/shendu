"""标准生成 Prompt 默认正文（STD-105）；生产环境以 PromptVersion 为准。"""

STANDARD_PROMPT_BODIES: dict[str, str] = {
    "standard_p01": (
        "你是申论大作文命题分析专家。根据题干与作答要求，仅输出一个 JSON 对象，字段："
        "essay_form, proposition_task, thesis_scope{must_address,must_avoid}, "
        "structure_expectation{paragraphs_min,has_thesis_statement,sub_thesis_count_hint}, "
        "answer_scope, abilities_focus, keywords, focus_points。"
        "勿按小题「材料采分点」思路。focus_points 至少 3 条。"
    ),
    "standard_p02": (
        "分析大作文参考背景（非小题阅读），输出 JSON：themes, facts[], viewpoints[], "
        "usable_for_argument[], not_required_to_quote。"
    ),
    "standard_p03": (
        "你是大作文 Rubric 专家。输入含 question_standard、dimension_skeleton(D01～D04)。"
        "输出 JSON：{\"candidates\":[...]}，每条含 id,dimension_id,core,observable_signals,"
        "typical_gaps,issue_tags；每维 2～4 条；勿生成「从材料摘抄要点」类准则。"
    ),
    "standard_p04": (
        "合并 candidates，去重同义准则，输出 JSON：dimensions[{id,label,max_score,ability,required,criteria}], "
        "criteria[完整准则列表], scoring_rules。保证 sum(dimensions.max_score)==total_score。"
    ),
    "standard_p05": "校验 Rubric 与参考解析覆盖，输出 coverage_gaps 等 JSON。",
    "standard_p06": "根据 Rubric 匹配用户作文维度得分（批改侧，可选独立调用）。",
    "standard_p07": "从 typical_gaps 生成 loss_rules JSON。",
}

STANDARD_PROMPT_NAMES: dict[str, str] = {
    "standard_p01": "标准引擎 P01 题目标准",
    "standard_p02": "标准引擎 P02 材料分析",
    "standard_p03": "标准引擎 P03 Rubric 候选",
    "standard_p04": "标准引擎 P04 Rubric 合并",
    "standard_p05": "标准引擎 P05 标准验证辅助",
    "standard_p06": "标准引擎 P06 答案匹配",
    "standard_p07": "标准引擎 P07 失分规则",
}
