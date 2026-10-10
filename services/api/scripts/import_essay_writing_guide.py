"""将写作技巧 PDF/TXT 解析为自备批改参考文。用法:

  python scripts/import_essay_writing_guide.py /path/to/guide.pdf
  python scripts/import_essay_writing_guide.py /path/to/guide.txt --out ../../data/guides/essay_writing_technique.txt
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.essay_writing_guide import clear_writing_guide_cache
from app.services.standard_engine.parse_service import parse_file

REPO_DEFAULT = (
    Path(__file__).resolve().parents[3] / "data" / "guides" / "essay_writing_technique.txt"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import essay writing guide for custom grading")
    parser.add_argument("source", type=Path, help="PDF, DOCX, or TXT")
    parser.add_argument("--out", type=Path, default=REPO_DEFAULT, help="Output UTF-8 text path")
    args = parser.parse_args()
    src = args.source.expanduser().resolve()
    if not src.is_file():
        print(f"Not found: {src}")
        sys.exit(1)
    text, quality, _ = parse_file(src)
    if len(text.strip()) < 200:
        print(f"Extracted text too short ({len(text)} chars), quality={quality}")
        sys.exit(1)
    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    header = f"# source: {src.name}\n# parse_quality: {quality}\n\n"
    out.write_text(header + text.strip() + "\n", encoding="utf-8")
    clear_writing_guide_cache()
    print(f"Wrote {len(text)} chars -> {out} (quality={quality})")


if __name__ == "__main__":
    main()
