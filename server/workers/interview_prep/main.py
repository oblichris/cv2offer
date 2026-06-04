from __future__ import annotations

from server.workers.interview_prep.service import generate_interview_prep


def main() -> None:
    result = generate_interview_prep()
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
