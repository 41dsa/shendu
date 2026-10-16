"""考试目标表单选项与卷种映射（产品级 DEC-11）。"""

from typing import Any

from pydantic import BaseModel, Field

# 与联调库 `material_structured.exam` 对齐
GUOKAO_JOB_OPTIONS = [
    {"value": "shidi", "label": "市地级及以下", "bank_exam": "国考市地级"},
    {"value": "fusheng", "label": "副省级 / 中央机关", "bank_exam": "国考副省级"},
    {"value": "zhifa", "label": "行政执法类", "bank_exam": "国考行政执法类"},
]

SHENGKAO_PROVINCES = [
    "北京",
    "天津",
    "河北",
    "山西",
    "内蒙古",
    "辽宁",
    "吉林",
    "黑龙江",
    "上海",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "广西",
    "海南",
    "重庆",
    "四川",
    "贵州",
    "云南",
    "西藏",
    "陕西",
    "甘肃",
    "青海",
    "宁夏",
    "新疆",
]

SHENGKAO_JOB_OPTIONS = [
    {"value": "xiangzhen", "label": "县乡机关"},
    {"value": "shiji", "label": "省市级机关"},
    {"value": "zhifa", "label": "行政执法"},
]

EXAM_TYPE_OPTIONS = [
    {"value": "guokao", "label": "国考"},
    {"value": "shengkao", "label": "省考"},
]

DEFAULT_YEARS = [2027, 2026, 2025, 2024]


class ExamProfileFormOptions(BaseModel):
    exam_types: list[dict[str, str]]
    guokao_jobs: list[dict[str, str]]
    shengkao_jobs: list[dict[str, str]]
    provinces: list[str]
    years: list[int]
    custom_exam_levels: list[dict[str, str]] = Field(default_factory=list)


def get_exam_profile_form_options() -> ExamProfileFormOptions:
    from app.domain.custom_exam_level import custom_exam_level_form_options

    return ExamProfileFormOptions(
        exam_types=[{"value": o["value"], "label": o["label"]} for o in EXAM_TYPE_OPTIONS],
        guokao_jobs=[{"value": o["value"], "label": o["label"]} for o in GUOKAO_JOB_OPTIONS],
        shengkao_jobs=[{"value": o["value"], "label": o["label"]} for o in SHENGKAO_JOB_OPTIONS],
        provinces=list(SHENGKAO_PROVINCES),
        years=list(DEFAULT_YEARS),
        custom_exam_levels=custom_exam_level_form_options(),
    )


def province_to_bank_exam(province: str) -> str:
    p = (province or "").strip()
    if not p:
        return ""
    if p.endswith("省") or p.endswith("市"):
        return f"{p}考"
    return f"{p}省考"


def normalize_exam_type(raw: str) -> str:
    t = (raw or "").strip()
    if t in ("guokao", "国考"):
        return "guokao"
    if t in ("shengkao", "省考"):
        return "shengkao"
    if "国考" in t:
        return "guokao"
    if "省" in t:
        return "shengkao"
    return t or "shengkao"


def normalize_job_category(exam_type: str, job_category: str) -> str:
    jc = (job_category or "").strip()
    if exam_type == "guokao":
        if jc in ("shidi", "fusheng", "zhifa"):
            return jc
        if any(k in jc for k in ("副省", "中央", "省级")):
            return "fusheng"
        return "shidi"
    if jc in ("xiangzhen", "shiji", "zhifa"):
        return jc
    return "xiangzhen"


def resolve_bank_exam_label(
    *,
    exam_type: str,
    province: str,
    job_category: str,
) -> str | None:
    et = normalize_exam_type(exam_type)
    job = normalize_job_category(et, job_category)
    if et == "guokao":
        for opt in GUOKAO_JOB_OPTIONS:
            if opt["value"] == job:
                return opt["bank_exam"]
        return "国考市地级"
    if et == "shengkao":
        return province_to_bank_exam(province) or None
    return None


def exam_profile_display(
    *,
    exam_type: str,
    province: str,
    year: int,
    job_category: str,
) -> dict[str, Any]:
    et = normalize_exam_type(exam_type)
    job = normalize_job_category(et, job_category)
    bank = resolve_bank_exam_label(exam_type=exam_type, province=province, job_category=job_category)
    type_label = next((o["label"] for o in EXAM_TYPE_OPTIONS if o["value"] == et), exam_type)
    if et == "guokao":
        job_label = next((o["label"] for o in GUOKAO_JOB_OPTIONS if o["value"] == job), job_category)
        summary = f"{type_label} · {job_label} · {year}"
    else:
        job_label = next((o["label"] for o in SHENGKAO_JOB_OPTIONS if o["value"] == job), job_category)
        summary = f"{type_label} · {province} · {job_label} · {year}"
    from app.domain.custom_exam_level import exam_level_from_profile

    return {
        "exam_type": et,
        "province": province,
        "year": year,
        "job_category": job,
        "summary": summary,
        "mapped_bank_exam": bank,
        "mapped_bank_year": year,
        "suggested_custom_exam_level": exam_level_from_profile(exam_type=et, job_category=job),
    }
