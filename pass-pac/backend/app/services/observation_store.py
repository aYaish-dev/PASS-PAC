from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OBSERVATIONS_FILE_NAME = "live-card-observations.jsonl"


def append_live_card_observation(mock_data_dir: str, observation: dict[str, Any]) -> str:
    output_path = Path(mock_data_dir) / OBSERVATIONS_FILE_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": "proxmark3",
        "mode": "local-read-only",
        **observation,
    }

    with output_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=True))
        file.write("\n")

    return str(output_path)
