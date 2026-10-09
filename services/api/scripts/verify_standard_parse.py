"""STD-204/205：解析器冒烟。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.standard_engine.parse_service import ParseError, parse_file


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sample.txt"
        p.write_text("2024国考大作文题干示例\n要求800字", encoding="utf-8")
        content, quality, mime = parse_file(p)
        assert "国考" in content
        assert quality == "high"
        assert mime == "text/plain"

        empty_pdf = Path(tmp) / "empty.txt"
        empty_pdf.write_text("", encoding="utf-8")
        c2, q2, _ = parse_file(empty_pdf)
        assert q2 == "high"

    try:
        parse_file(Path("/no/such/file.xyz"))
    except ParseError:
        pass
    else:
        raise AssertionError("expected ParseError")
    print("verify_standard_parse: ok")


if __name__ == "__main__":
    main()
