from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


@dataclass
class PipelineLogger:
    """Captures a complete, auditable trace of reasoning, planning, and execution."""

    records: List[Dict[str, object]] = field(default_factory=list)

    def log(self, stage: str, payload: Dict[str, object]) -> None:
        self.records.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "payload": payload,
            }
        )

    def render_console_report(self) -> str:
        lines: List[str] = []
        for record in self.records:
            lines.append(f"[{record['stage'].upper()}]")
            lines.append(json.dumps(record["payload"], indent=2, sort_keys=True))
        return "\n".join(lines)

    def write_jsonl(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for record in self.records:
                f.write(json.dumps(record))
                f.write("\n")
