from __future__ import annotations

import argparse

from server.workers.jd_resume.models import JDResumeRequest
from server.workers.jd_resume.service import generate_resume_tailoring


def main() -> None:
    parser = argparse.ArgumentParser(description="Run JD resume worker.")
    parser.add_argument("--jd", required=True)
    parser.add_argument("--resume", required=True)
    parser.add_argument("--title", default="Sample AI Product Manager")
    args = parser.parse_args()
    request = JDResumeRequest(jd_text=args.jd, resume_text=args.resume, title=args.title)
    result = generate_resume_tailoring(request)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
