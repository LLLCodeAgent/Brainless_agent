"""Read-only debug commands for persisted hierarchical-agent audit data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.memory.sqlite_memory import SQLiteMemory


def run_agent_cli(arguments: list[str], database: Path) -> None:
    parser = argparse.ArgumentParser(prog="python run.py agent")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    inspect = commands.add_parser("inspect"); inspect.add_argument("agent_id")
    permissions = commands.add_parser("permissions"); permissions.add_argument("agent_id")
    logs = commands.add_parser("logs"); logs.add_argument("agent_id")
    tree = commands.add_parser("tree"); tree.add_argument("agent_id", nargs="?")
    parsed = parser.parse_args(arguments)
    storage = SQLiteMemory(database)
    try:
        records = storage.agent_records()
        if parsed.command == "list":
            print("\n".join(f"{item['agent_id']} {item['status']} {item['name']}" for item in records))
        elif parsed.command == "inspect":
            print(json.dumps(_record(records, parsed.agent_id), indent=2, default=str))
        elif parsed.command == "permissions":
            print("\n".join(_record(records, parsed.agent_id)["permissions"]))
        elif parsed.command == "logs":
            print(json.dumps(storage.agent_events(parsed.agent_id), indent=2, default=str))
        else:
            root_id = parsed.agent_id or next((item["agent_id"] for item in records if item["parent_agent_id"] is None), None)
            if root_id is None:
                raise SystemExit("No persisted agents found")
            print(json.dumps(_tree(records, root_id), indent=2, default=str))
    finally:
        storage.close()


def _record(records: list[dict[str, object]], agent_id: str) -> dict[str, object]:
    for record in records:
        if record["agent_id"] == agent_id:
            return record
    raise SystemExit(f"Unknown agent: {agent_id}")


def _tree(records: list[dict[str, object]], agent_id: str) -> dict[str, object]:
    record = _record(records, agent_id)
    return {"agent_id": agent_id, "name": record["name"],
            "children": [_tree(records, item["agent_id"]) for item in records if item["parent_agent_id"] == agent_id]}
