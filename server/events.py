from __future__ import annotations

import json
from collections.abc import Iterable


def sse_lines(events: Iterable[dict]) -> Iterable[str]:
    for event in events:
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
