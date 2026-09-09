"""Command-line entrypoint for the LangChain agent workflow."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .config import WorkflowConfig
from .engine import WorkflowAborted, WorkflowPaused, WorkflowRunner
from .intervention import ConsoleInterventionHandler
from .observability import CompositeObserver, JsonlObserver, LiveObserver, NullObserver, Observer


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the B.AI LangChain implementation workflow")
    parser.add_argument("objective", nargs="?", help="Implementation objective")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="append", default=[], help="Verification command; repeatable")
    parser.add_argument("--max-parallel", type=int, default=3)
    parser.add_argument("--max-review-rounds", type=int, default=2)
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--head-branch", default="")
    parser.add_argument("--pr-title", default="")
    parser.add_argument("--pr-label", action="append", default=[])
    parser.add_argument("--open-pr", action="store_true", help="Authorize gh pr create after all gates pass")
    parser.add_argument("--no-live", action="store_true", help="Disable live progress output")
    parser.add_argument("--events-file", type=Path, help="Write structured workflow events to JSONL")
    parser.add_argument("--session-id", help="Persist a new run under this session id")
    parser.add_argument(
        "--resume",
        metavar="SESSION_ID",
        help="Resume a paused session from <repo>/.workflow/sessions/<SESSION_ID>",
    )
    args = parser.parse_args()

    if args.resume and args.session_id:
        parser.error("--resume and --session-id cannot be used together")
    if not args.objective and not args.resume:
        parser.error("an objective is required unless --resume is used")

    config = WorkflowConfig.from_environment(
        args.repo,
        checks=tuple(args.check),
        max_parallel=args.max_parallel,
        max_review_rounds=args.max_review_rounds,
        open_pr=args.open_pr,
        base_branch=args.base_branch,
        head_branch=args.head_branch,
        pr_title=args.pr_title,
        pr_labels=tuple(args.pr_label),
    )
    observers: list[Observer] = []
    if not args.no_live:
        observers.append(LiveObserver(sys.stderr))
    if args.events_file:
        observers.append(JsonlObserver(args.events_file))
    observer: Observer = CompositeObserver(observers) if observers else NullObserver()
    runner = WorkflowRunner(
        config,
        observer,
        session_id=args.resume or args.session_id,
        resume=bool(args.resume),
        intervention_handler=ConsoleInterventionHandler(),
    )
    try:
        result = asyncio.run(runner.run(args.objective or ""))
    except WorkflowAborted as exc:
        print(f"Workflow abortado: {exc}", file=sys.stderr)
        return 1
    except WorkflowPaused as exc:
        print(f"Workflow pausado: {exc}", file=sys.stderr)
        print("Corrija a causa e execute novamente com --resume.", file=sys.stderr)
        return 75
    except Exception as exc:
        parser.error(str(exc))

    print(
        json.dumps(
            {
                "session_id": runner.session.session_id,
                "session_path": str(runner.session.path),
                "plan": result.plan.summary,
                "reviews": result.reviews,
                "checks_ok": result.checks_ok,
                "check_evidence": result.check_evidence,
                "pr_draft": result.pr_draft,
                "pr_url": result.pr_url,
            },
            default=str,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
