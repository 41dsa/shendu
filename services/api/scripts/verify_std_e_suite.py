"""验收清单 E1～E5 + V0.2 扩展冒烟（一键）。"""

import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = API_ROOT / "scripts"


def run(name: str, *args: str, env: dict | None = None) -> None:
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    merged = {**os.environ, "STANDARD_AUTO_PUBLISH": "0", **(env or {})}
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=API_ROOT, env=merged, check=True)


def main() -> None:
    run("verify_standard_engine.py")
    run("verify_standard_parse.py")
    run("verify_standard_pipeline_stub.py", env={"STANDARD_GEN_MODE": "stub"})
    run("verify_standard_publish.py", env={"STANDARD_GEN_MODE": "stub"})
    run("standard_regression_smoke.py")
    run("verify_standard_input_cache.py", env={"STANDARD_GEN_MODE": "stub"})
    run("verify_rubric_agreement.py")
    run("verify_ai_gold_seed.py")
    run("verify_exam_standard.py", env={"STANDARD_GEN_MODE": "stub", "STANDARD_AUTO_PUBLISH": "0"})
    run("verify_essay_exam_policy.py", env={"STANDARD_GEN_MODE": "stub", "STANDARD_AUTO_PUBLISH": "0"})
    run("verify_practice_catalog.py", env={"STANDARD_GEN_MODE": "stub", "STANDARD_AUTO_PUBLISH": "0"})
    run("verify_exam_catalog.py")
    print("\nverify_std_e_suite: all ok")


if __name__ == "__main__":
    main()
