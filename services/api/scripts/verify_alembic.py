"""确认 Alembic 已配置且 revision 001_baseline 存在。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic.config import Config
from alembic.script import ScriptDirectory


def main() -> None:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    assert ini.is_file(), "缺少 alembic.ini"
    script = ScriptDirectory.from_config(Config(str(ini)))
    heads = script.get_heads()
    assert "001_baseline" in heads, f"期望 head 001_baseline，实际 {heads}"
    print("verify_alembic: ok head=001_baseline")


if __name__ == "__main__":
    main()
