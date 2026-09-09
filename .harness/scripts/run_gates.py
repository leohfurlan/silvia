#!/usr/bin/env python3
"""Run configured gates and preserve complete local evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--group",
        choices=("fast", "full", "architecture", "all"),
        default="fast",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute; without this flag only list commands.",
    )
    parser.add_argument("--continue-on-failure", action="store_true")
    return parser.parse_args()


def git_value(root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    config_path = root / ".harness" / "gates.json"
    config: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise SystemExit("Configuração inválida: gates.json deve ser um objeto")
    groups = config.get("groups")
    if not isinstance(groups, dict):
        raise SystemExit("Configuração inválida: groups deve ser um objeto")
    working_value = config.get("working_directory", ".")
    if not isinstance(working_value, str) or not working_value.strip():
        raise SystemExit("Configuração inválida: working_directory deve ser texto não vazio")
    for group in ("fast", "full", "architecture"):
        commands = groups.get(group)
        invalid = not isinstance(commands, list) or any(
            not isinstance(command, str) or not command.strip()
            for command in commands or []
        )
        if invalid:
            raise SystemExit(f"Configuração inválida: grupo {group} deve ser array de strings")
    working_directory = (root / working_value).resolve()
    try:
        working_directory.relative_to(root)
    except ValueError as exc:
        raise SystemExit("Configuração inválida: working_directory sai da raiz") from exc
    selected = (
        ("fast", "full", "architecture")
        if args.group == "all"
        else (args.group,)
    )
    commands = [
        (group, command)
        for group in selected
        for command in groups.get(group, [])
    ]

    if not commands:
        print(f"Nenhum comando configurado para group={args.group}")
        return 0
    for group, command in commands:
        print(f"[{group}] {command}")
    if not args.run:
        print("LIST ONLY: use --run para executar")
        return 0

    started = dt.datetime.now(dt.timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%S.%fZ")
    evidence_dir = root / ".harness" / "evidence-local" / stamp
    evidence_dir.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    failed = False

    for index, (group, command) in enumerate(commands, start=1):
        log_path = evidence_dir / f"{index:02d}-{group}.log"
        command_started = dt.datetime.now(dt.timezone.utc)
        with log_path.open("w", encoding="utf-8", newline="\n") as log:
            completed = subprocess.run(
                command,
                cwd=working_directory,
                shell=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        command_finished = dt.datetime.now(dt.timezone.utc)
        results.append(
            {
                "group": group,
                "command": command,
                "started_at": command_started.isoformat(),
                "finished_at": command_finished.isoformat(),
                "exit_code": completed.returncode,
                "status": "passed" if completed.returncode == 0 else "failed",
                "log": log_path.relative_to(root).as_posix(),
            }
        )
        print(f"[{results[-1]['status']}] {command}")
        if completed.returncode != 0:
            failed = True
            if not args.continue_on_failure:
                break

    finished = dt.datetime.now(dt.timezone.utc)
    status = git_value(root, "status", "--short")
    evidence = {
        "schema_version": 1,
        "project_root": str(root),
        "git_head": git_value(root, "rev-parse", "HEAD"),
        "git_dirty": bool(status),
        "git_status": status,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "requested_group": args.group,
        "status": "failed" if failed else "passed",
        "results": results,
    }
    path = evidence_dir / "evidence.json"
    path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"EVIDENCE={path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
