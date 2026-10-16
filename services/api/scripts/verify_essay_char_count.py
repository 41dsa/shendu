"""计字规则自检（方格纸 + 申论正文汉字）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import (
    count_essay_chars,
    count_shenlun_body_chars,
    count_shenlun_body_han_chars,
    official_essay_char_count,
)

assert count_essay_chars("你好，世界。") == 6
assert count_shenlun_body_han_chars("你好，世界。") == 4
assert count_shenlun_body_chars("你好，世界。") == 6
assert count_shenlun_body_han_chars("2024年GDP") == 1
assert count_shenlun_body_chars("2024年GDP") == 8
assert count_shenlun_body_chars("Hello, world.") == 12

opening = "追寻长期价值，是个人破除浮躁、锚定人生坐标的必然选择\n\n\u3000\u3000风物长宜放眼量。"
assert count_shenlun_body_han_chars(opening) > 20
assert official_essay_char_count(opening) >= count_shenlun_body_han_chars(opening)

assert count_shenlun_body_han_chars("追长期价值\n\n\u3000\u3000风物长宜放眼量。") == 7
assert official_essay_char_count("追长期价值\n\n\u3000\u3000风物长宜放眼量。") == 8
print("verify_essay_char_count: ok")
