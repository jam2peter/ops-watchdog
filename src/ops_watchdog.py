#!/usr/bin/env python3
"""State transition and deduplication engine for JamPeter Ops Watchdog."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEVERITY = {
    "PASS": 0,
    "UNKNOWN": 1,
    "DEGRADED": 2,
    "BLOCKED": 3,
}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_snapshot(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported snapshot schema: {path}")
    if not isinstance(data.get("systems"), list):
        raise ValueError(f"systems must be a list: {path}")
    return data


def normalize_sources(sources: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for source, snapshot in sorted(sources.items()):
        for system in snapshot.get("systems", []):
            system_id = system.get("id")
            status = system.get("status")
            if not isinstance(system_id, str) or status not in SEVERITY:
                continue
            key = f"{source}:{system_id}"
            normalized[key] = {
                "source": source,
                "id": system_id,
                "name": str(system.get("name") or system_id),
                "status": str(status),
            }
    return normalized


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported state schema")
    return data


def classify_transition(previous: str, current: str) -> str:
    if current == previous:
        return "unchanged"
    if previous == "NOT_PRESENT":
        return "appeared"
    if current == "REMOVED":
        return "removed"

    previous_level = SEVERITY.get(previous)
    current_level = SEVERITY.get(current)
    if previous_level is None or current_level is None:
        return "changed"
    if current_level > previous_level:
        return "worsened"
    if current_level < previous_level:
        return "recovered"
    return "changed"


def decide(
    previous_state: dict[str, Any] | None,
    current_systems: dict[str, dict[str, str]],
) -> dict[str, Any]:
    generated_at = utc_now()
    current_state = {
        "schema_version": 1,
        "generated_at": generated_at,
        "systems": current_systems,
    }

    if previous_state is None:
        return {
            "schema_version": 1,
            "kind": "ops-watchdog-decision",
            "generated_at": generated_at,
            "notify": False,
            "reason": "baseline_created",
            "events": [],
            "state": current_state,
        }

    previous_systems = previous_state.get("systems", {})
    if not isinstance(previous_systems, dict):
        raise ValueError("previous state systems must be an object")

    events: list[dict[str, str]] = []
    all_keys = sorted(set(previous_systems) | set(current_systems))

    for key in all_keys:
        previous = previous_systems.get(key)
        current = current_systems.get(key)

        if previous is None and current is not None:
            previous_status = "NOT_PRESENT"
            current_status = current["status"]
            name = current["name"]
            source = current["source"]
        elif current is None and previous is not None:
            previous_status = str(previous.get("status") or "UNKNOWN")
            current_status = "REMOVED"
            name = str(previous.get("name") or key)
            source = str(previous.get("source") or key.split(":", 1)[0])
        elif previous is not None and current is not None:
            previous_status = str(previous.get("status") or "UNKNOWN")
            current_status = current["status"]
            name = current["name"]
            source = current["source"]
        else:
            continue

        transition = classify_transition(previous_status, current_status)
        if transition == "unchanged":
            continue

        events.append(
            {
                "key": key,
                "source": source,
                "name": name,
                "from": previous_status,
                "to": current_status,
                "transition": transition,
            }
        )

    return {
        "schema_version": 1,
        "kind": "ops-watchdog-decision",
        "generated_at": generated_at,
        "notify": bool(events),
        "reason": "state_change" if events else "no_change",
        "events": events,
        "state": current_state,
    }


def parse_source_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("source must use NAME=PATH")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("source name cannot be empty")
    return name, Path(raw_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        type=parse_source_arg,
        help="sanitized snapshot source in NAME=PATH form",
    )
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("watchdog-decision.json"))
    parser.add_argument("--write-state", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = {name: load_snapshot(path) for name, path in args.source}
    current = normalize_sources(sources)
    decision = decide(load_state(args.state), current)

    args.output.write_text(
        json.dumps(decision, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.write_state:
        args.state.write_text(
            json.dumps(
                decision["state"],
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        "OPS_WATCHDOG="
        f"{'NOTIFY' if decision['notify'] else 'SILENT'} "
        f"reason={decision['reason']} events={len(decision['events'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
