"""本地校验参考范文排版与分论点锚定（不调用 LLM）。"""

from app.services.reference_sample_service import _format_reference_sample_text, _normalize_reference_sample

sample = """城市建设的辩证法
　　城市建设重有轻无，必然导致空间拥挤而人心疏离。
　　第二分论点段首句说明无不是空无而是容器。
　　第三分论点段首句讲制度设计把公共空间落到日常。
　　第四分论点段首句讲评价标尺应从物的增量转向人的体验。"""

data = {
    "sample_text": sample,
    "target_tier_note": "test",
    "body_theses": [
        {"index": 1, "title": "城市建设重有轻无，必然导致空间拥挤而人心疏离"},
        {"index": 2, "title": "无不是空无而是容器"},
        {"index": 3, "title": "制度设计把公共空间落到日常"},
        {"index": 4, "title": "评价标尺应从物的增量转向人的体验"},
    ],
    "mark_segments": [
        {
            "quote": "第二分论点段首句说明无不是空无而是容器",
            "point_label": "分析",
            "thesis_index": 2,
            "why": "段内分析示范写法",
        },
        {
            "quote": "第三分论点段首句讲制度设计把公共空间落到日常",
            "point_label": "对策",
            "thesis_index": 3,
            "why": "对策写法",
        },
        {
            "quote": "第四分论点段首句讲评价标尺应从物的增量转向人的体验",
            "point_label": "升华",
            "thesis_index": 4,
            "why": "升华写法",
        },
        {
            "quote": "城市建设重有轻无，必然导致空间拥挤而人心疏离",
            "point_label": "立意",
            "thesis_index": 1,
            "why": "段旨扣题",
        },
        {
            "quote": "人心疏离",
            "point_label": "论证",
            "thesis_index": 1,
            "why": "因果论证",
        },
        {
            "quote": "容器",
            "point_label": "概念",
            "thesis_index": 2,
            "why": "概念界定",
        },
    ],
}

formatted = _format_reference_sample_text(data["sample_text"])
data["sample_text"] = formatted
out = _normalize_reference_sample(data, prompt="要求：", max_score=40)
assert len(out["thesis_anchors"]) == 4
assert len(out["mark_segments"]) >= 4
print("verify_reference_sample_layout: ok")
