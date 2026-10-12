from __future__ import annotations

import re
from typing import Any


def segment_material(material: str | None) -> list[dict[str, Any]]:
    if not material or not material.strip():
        return []
    blocks = re.split(r"\n+", material.replace("\r", ""))
    paras: list[dict[str, Any]] = []
    for i, block in enumerate(blocks, start=1):
        text = block.strip()
        if not text:
            continue
        paras.append({"para_id": i, "text": text, "sentences": _split_sentences(text)})
    return paras


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；])", text)
    return [p.strip() for p in parts if p.strip()]


def material_index(paras: list[dict[str, Any]]) -> dict[int, str]:
    return {int(p["para_id"]): str(p["text"]) for p in paras}
