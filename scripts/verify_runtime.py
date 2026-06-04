from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services.runtime_checks import runtime_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Check cv2offer provider and audio readiness.")
    parser.add_argument("--require-real", action="store_true", help="Fail unless real provider keys and audio are ready.")
    args = parser.parse_args()

    checks = runtime_readiness()
    summary = {
        "mock": checks["providers"]["mock"],
        "ready_for_mock_demo": checks["ready_for_mock_demo"],
        "ready_for_real_interview_prep": checks["ready_for_real_interview_prep"],
        "ready_for_real_copilot": checks["ready_for_real_copilot"],
        "deepseek_key_present": checks["providers"]["llm"]["api_key_present"],
        "stepfun_key_present": checks["providers"]["asr"]["api_key_present"],
        "audio_configured": checks["audio"]["configured"],
        "audio_selected": checks["audio"].get("selected"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.require_real and not (checks["ready_for_real_interview_prep"] and checks["ready_for_real_copilot"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
